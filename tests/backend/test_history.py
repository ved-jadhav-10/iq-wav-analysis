"""Kept analyses (PLAN M7 "Job store"): they survive a restart and download as they were."""

import hashlib
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from dsp.results import Results

from .test_recordings import open_and_finish


def app_client(tmp_path: Path, workspace: Path | None) -> TestClient:
    dist = tmp_path / "dist"
    dist.mkdir(exist_ok=True)
    (dist / "index.html").write_text("<!doctype html>")
    return TestClient(create_app(dist, workspace))


def wait_for_entry(client: TestClient) -> dict[str, object]:
    """The worker keeps the analysis just after it reports done: poll the list briefly."""
    import time

    for _ in range(100):
        listed = client.get("/api/v1/history").json()
        if listed:
            return listed[0]
        time.sleep(0.05)
    raise AssertionError("the finished analysis was not kept")


def test_a_finished_analysis_is_kept_and_survives_a_restart(
    tmp_path: Path, sigmf_path: Path
) -> None:
    workspace = tmp_path / "ws"
    first = app_client(tmp_path, workspace)
    opened = open_and_finish(first, sigmf_path)
    live = first.get(f"/api/v1/recordings/{opened['id']}/results")
    entry = wait_for_entry(first)
    assert entry["name"] == "rec.sigmf-meta" and entry["container"] == "SigMF"
    assert entry["signals"] == 1
    assert entry["resultsSha256"] == hashlib.sha256(live.content).hexdigest()

    # A new server process over the same workspace lists it and serves the same bytes.
    second = app_client(tmp_path, workspace)
    (listed,) = second.get("/api/v1/history").json()
    assert listed == entry
    kept = second.get(f"/api/v1/history/{entry['id']}/results")
    assert kept.content == live.content
    assert Results.model_validate_json(kept.text).recording.files


@pytest.mark.parametrize(
    ("format", "start"),
    [("csv", b"signal,stage"), ("txt", b"Sanket "), ("pdf", b"%PDF"), ("run", b"{")],
)
def test_a_kept_analysis_downloads_in_every_format_but_sigmf(
    tmp_path: Path, sigmf_path: Path, format: str, start: bytes
) -> None:
    client = app_client(tmp_path, tmp_path / "ws")
    open_and_finish(client, sigmf_path)
    entry = wait_for_entry(client)
    got = client.get(f"/api/v1/history/{entry['id']}/results", params={"format": format})
    assert got.status_code == 200 and got.content.startswith(start)
    assert (
        client.get(f"/api/v1/history/{entry['id']}/results", params={"format": "sigmf"}).status_code
        == 422
    )


def test_deleting_an_analysis_removes_it_for_good(tmp_path: Path, sigmf_path: Path) -> None:
    workspace = tmp_path / "ws"
    client = app_client(tmp_path, workspace)
    open_and_finish(client, sigmf_path)
    entry = wait_for_entry(client)
    assert client.delete(f"/api/v1/history/{entry['id']}").status_code == 204
    assert client.get(f"/api/v1/history/{entry['id']}/results").status_code == 404
    assert client.delete(f"/api/v1/history/{entry['id']}").status_code == 404
    assert app_client(tmp_path, workspace).get("/api/v1/history").json() == []
    # Nothing derived from it is left in the file: its hash is not in the database bytes.
    assert str(entry["resultsSha256"]).encode() not in (workspace / "history.sqlite3").read_bytes()


def test_without_a_workspace_nothing_is_written_and_nothing_survives(
    tmp_path: Path, sigmf_path: Path
) -> None:
    client = app_client(tmp_path, None)
    open_and_finish(client, sigmf_path)
    wait_for_entry(client)  # kept for this process
    assert app_client(tmp_path, None).get("/api/v1/history").json() == []


def test_a_history_entry_that_is_not_there_is_refused(tmp_path: Path) -> None:
    client = app_client(tmp_path, None)
    assert client.get("/api/v1/history/nope/results").status_code == 404
    assert io.BytesIO(b"").read() == b""
