"""Uploading a recording from the browser into the workspace (PLAN §5 M7)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from dsp.synth.chain import Scene, SignalSpec, generate, write_sigmf

BATCH = "0123456789abcdef0123456789abcdef"


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>Sanket</title>")
    return dist


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path / "workspace"


@pytest.fixture
def client(dist: Path, workspace: Path) -> TestClient:
    return TestClient(create_app(dist, workspace, max_upload_bytes=1 << 20))


def put(client: TestClient, name: str, content: bytes, batch: str = BATCH):
    return client.put(f"/api/v1/uploads/{batch}/{name}", content=content)


def test_an_uploaded_file_lands_in_the_workspace_and_is_reported(
    client: TestClient, workspace: Path
) -> None:
    response = put(client, "capture.bin", b"\x01\x02\x03\x04")
    assert response.status_code == 200
    body = response.json()
    assert body["size"] == 4
    landed = Path(body["path"])
    assert landed == workspace / "uploads" / BATCH / "capture.bin"
    assert landed.read_bytes() == b"\x01\x02\x03\x04"


def test_a_sigmf_pair_uploaded_as_two_files_opens_like_the_original(
    client: TestClient, tmp_path: Path
) -> None:
    spec = SignalSpec("qpsk", sps=8.0, frame=None, offset=0.2, power_db=0.0)
    scene = Scene(1 << 14, (spec,), noise_db=-20.0, sample_rate=1e6, center_frequency=1e8)
    meta = write_sigmf(tmp_path / "rec", generate(scene, seed=1), scene, "cf32_le")
    data = meta.with_suffix(".sigmf-data")

    first = put(client, "rec.sigmf-data", data.read_bytes()).json()
    second = put(client, "rec.sigmf-meta", meta.read_bytes()).json()
    opened = client.post("/api/v1/recordings", json={"path": second["path"]})
    assert Path(first["path"]).parent == Path(second["path"]).parent
    assert opened.status_code == 200
    body = opened.json()
    assert body["container"] == "SigMF"
    assert body["numSamples"] == 1 << 14
    assert body["sampleRate"] == 1e6


@pytest.mark.parametrize(
    "name",
    [
        "..",
        ".hidden",
        "..%5Csecret.bin",  # ..\secret.bin
        "a%5Cb.bin",
        "%2E%2E%2Fsecret.bin",  # ../secret.bin
        "con.txt",
        "NUL",
        "lpt1.bin",
        "trailing.",
        "x" * 201,
        "semi;colon.bin",
    ],
)
def test_an_unsafe_file_name_is_refused_and_writes_nothing_outside_the_batch(
    client: TestClient, workspace: Path, tmp_path: Path, name: str
) -> None:
    response = put(client, name, b"data")
    assert response.status_code in (404, 405, 422)
    written = {p for p in tmp_path.rglob("*") if p.is_file()}
    assert not any(p.name == "secret.bin" for p in written)
    assert not (workspace / "uploads" / BATCH).exists() or not any(
        (workspace / "uploads" / BATCH).iterdir()
    )


@pytest.mark.parametrize("batch", ["short", "G" * 32, "../" * 8, BATCH.upper()])
def test_a_batch_id_must_be_32_lowercase_hex_digits(client: TestClient, batch: str) -> None:
    assert put(client, "a.bin", b"data", batch=batch).status_code in (404, 405, 422)


def test_a_file_over_the_limit_is_refused_and_leaves_no_partial_file(
    client: TestClient, workspace: Path
) -> None:
    response = put(client, "big.bin", b"\x00" * ((1 << 20) + 1))
    assert response.status_code == 413
    assert not (workspace / "uploads" / BATCH / "big.bin").exists()


def test_a_name_cannot_be_sent_twice_and_the_first_copy_survives(
    client: TestClient, workspace: Path
) -> None:
    assert put(client, "a.bin", b"first").status_code == 200
    assert put(client, "a.bin", b"second").status_code == 409
    assert (workspace / "uploads" / BATCH / "a.bin").read_bytes() == b"first"


def test_an_empty_file_is_refused(client: TestClient, workspace: Path) -> None:
    assert put(client, "empty.bin", b"").status_code == 422
    assert not (workspace / "uploads" / BATCH / "empty.bin").exists()
