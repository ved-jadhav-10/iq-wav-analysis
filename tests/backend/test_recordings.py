"""Opening a recording and fetching its tiles over the API (PLAN §5 M2)."""

from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from dsp.ingest.formats import SampleFormat
from dsp.synth.chain import Scene, SignalSpec, generate, write_sigmf


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>Sanket</title>")
    return dist


@pytest.fixture
def client(dist: Path) -> TestClient:
    return TestClient(create_app(dist))


@pytest.fixture
def sigmf_path(tmp_path: Path) -> Path:
    spec = SignalSpec("qpsk", sps=8.0, frame=None, offset=0.2, power_db=0.0)
    scene = Scene(1 << 16, (spec,), noise_db=-20.0, sample_rate=1e6, center_frequency=1e8)
    g = generate(scene, seed=1)
    meta = write_sigmf(tmp_path / "rec", g, scene, "cf32_le")
    return meta


def test_opening_a_recording_returns_its_assumptions_and_pyramid_shape(
    client: TestClient, sigmf_path: Path
) -> None:
    response = client.post("/api/v1/recordings", json={"path": str(sigmf_path)})
    assert response.status_code == 200
    body = response.json()
    assert body["container"] == "SigMF"
    assert body["numSamples"] == 1 << 16
    assert body["real"] is False
    assert body["assumptions"]["sampleRate"]["value"] == 1e6
    assert len(body["levels"]) >= 1
    assert body["levels"][0]["rowSpan"] == 1
    assert body["dbMax"] > body["dbMin"]
    assert body["sampleRate"] == 1e6
    assert len(body["psdDb"]) == len(body["freqsHz"]) == body["levels"][0]["cols"]
    assert body["hop"] == body["fftSize"] // 2


def test_an_unknown_sample_rate_omits_hz_rather_than_guessing_one(
    client: TestClient, tmp_path: Path
) -> None:
    """A raw file with no metadata states no sample rate; the API must say so (None), never
    default one just so freqsHz has units (PLAN's "never assume a sample rate" rule)."""
    fmt = SampleFormat.parse("cf32_le")
    x = np.exp(2j * np.pi * 0.1 * np.arange(20_000))
    path = tmp_path / "capture.bin"
    path.write_bytes(fmt.encode(x))
    body = client.post("/api/v1/recordings", json={"path": str(path)}).json()
    assert body["sampleRate"] is None
    assert body["freqsHz"] is None
    assert len(body["psdDb"]) == body["levels"][0]["cols"]  # still reported, unitless


def test_a_missing_path_is_a_client_error_not_a_500(client: TestClient, tmp_path: Path) -> None:
    response = client.post("/api/v1/recordings", json={"path": str(tmp_path / "nope.sigmf-meta")})
    assert response.status_code == 422


def test_getting_a_recording_again_returns_the_same_info(
    client: TestClient, sigmf_path: Path
) -> None:
    opened = client.post("/api/v1/recordings", json={"path": str(sigmf_path)}).json()
    fetched = client.get(f"/api/v1/recordings/{opened['id']}").json()
    assert fetched == opened


def test_getting_an_unknown_recording_id_is_404(client: TestClient) -> None:
    assert client.get("/api/v1/recordings/does-not-exist").status_code == 404


def test_a_tile_has_the_right_shape_and_matches_the_pyramid(
    client: TestClient, sigmf_path: Path
) -> None:
    opened = client.post("/api/v1/recordings", json={"path": str(sigmf_path)}).json()
    response = client.get(f"/api/v1/tiles/{opened['id']}/0/0/0")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    rows, cols = int(response.headers["x-tile-rows"]), int(response.headers["x-tile-cols"])
    tile = np.frombuffer(response.content, np.uint8).reshape(rows, cols)
    assert rows == min(256, opened["levels"][0]["rows"])
    assert cols == min(256, opened["levels"][0]["cols"])
    assert tile.dtype == np.uint8


def test_an_unknown_level_or_recording_is_404_not_a_500(
    client: TestClient, sigmf_path: Path
) -> None:
    opened = client.post("/api/v1/recordings", json={"path": str(sigmf_path)}).json()
    assert client.get(f"/api/v1/tiles/{opened['id']}/99/0/0").status_code == 404
    assert client.get("/api/v1/tiles/does-not-exist/0/0/0").status_code == 404


def test_a_tile_past_the_grid_edge_is_empty_not_an_error(
    client: TestClient, sigmf_path: Path
) -> None:
    opened = client.post("/api/v1/recordings", json={"path": str(sigmf_path)}).json()
    response = client.get(f"/api/v1/tiles/{opened['id']}/0/9999/9999")
    assert response.status_code == 200
    assert response.headers["x-tile-rows"] == "0"
    assert response.content == b""
