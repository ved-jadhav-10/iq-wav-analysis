import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import samples
from backend.app import create_app
from dsp.synth.chain import Scene, SignalSpec, generate, write_sigmf


@pytest.fixture
def sample_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "samples"
    folder.mkdir()
    g = generate(
        Scene(samples=1 << 15, signals=(SignalSpec(modulation="qpsk", sps=8),), noise_db=-20.0), 1
    )
    write_sigmf(folder / "scene_fsk", g, Scene(samples=1 << 15, signals=()), "cf32_le")
    (folder / "scene_fsk.truth.json").write_text(json.dumps([{"label": "x"}, {"label": "y"}]))
    monkeypatch.setenv("SANKET_SAMPLES", str(folder))
    return folder


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>Sanket</title>")
    return TestClient(create_app(dist))


def test_only_present_samples_are_listed_with_their_truth_count(
    client: TestClient, sample_dir: Path
) -> None:
    listed = client.get("/api/v1/samples").json()
    assert [s["id"] for s in listed] == ["scene_fsk"]
    only = listed[0]
    assert only["synthetic"] is True and only["signals"] == 2
    assert only["sizeBytes"] == sum(
        (sample_dir / f"scene_fsk.sigmf-{k}").stat().st_size for k in ("meta", "data")
    )


def test_a_sample_opens_like_any_recording(client: TestClient, sample_dir: Path) -> None:
    response = client.post("/api/v1/samples/scene_fsk/open")
    assert response.status_code == 200
    body = response.json()
    assert body["container"] == "SigMF" and body["synthetic"] is True


def test_unknown_sample_is_a_404(client: TestClient, sample_dir: Path) -> None:
    assert client.post("/api/v1/samples/nope/open").status_code == 404


def test_no_samples_folder_lists_nothing(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SANKET_SAMPLES", str(tmp_path / "missing"))
    assert client.get("/api/v1/samples").json() == []
    assert samples.find("scene") is None
    shutil.rmtree(tmp_path / "missing", ignore_errors=True)
