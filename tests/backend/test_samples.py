import json
import shutil
import wave
from pathlib import Path

import numpy as np
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


def _write_other_samples(folder: Path) -> None:
    """A headerless raw file and a stereo WAV, and a SigMF sample the catalogue lists first."""
    g = generate(
        Scene(samples=1 << 15, signals=(SignalSpec(modulation="qpsk", sps=8),), noise_db=-20.0), 1
    )
    write_sigmf(folder / "scene", g, Scene(samples=1 << 15, signals=()), "cf32_le")
    (folder / "scene_raw.cf32").write_bytes(g.samples.astype("<c8").tobytes())
    pcm = np.empty(2 * len(g.samples), "<i2")
    pcm[0::2] = np.round(g.samples.real / 4 * 32767)
    pcm[1::2] = np.round(g.samples.imag / 4 * 32767)
    with wave.open(str(folder / "scene_wav.wav"), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(48_000)
        w.writeframes(pcm.tobytes())
    (folder / "scene_raw.truth.json").write_text(json.dumps([{"label": "x"}]))


def test_raw_and_wav_samples_are_listed_in_catalogue_order_with_their_own_file(
    sample_dir: Path,
) -> None:
    _write_other_samples(sample_dir)
    listed = samples.list_samples()
    assert [s.id for s in listed] == ["scene", "scene_fsk", "scene_wav", "scene_raw"]
    by_id = {s.id: s for s in listed}
    assert by_id["scene"].path.name == "scene.sigmf-meta"
    assert by_id["scene_raw"].path == sample_dir / "scene_raw.cf32"
    assert by_id["scene_raw"].size_bytes == (sample_dir / "scene_raw.cf32").stat().st_size
    assert by_id["scene_raw"].signals == 1
    assert by_id["scene_wav"].path == sample_dir / "scene_wav.wav"
    assert by_id["scene_wav"].signals == 0  # no truth file beside it


def test_the_catalogue_has_unique_ids_and_lists_coverage_second() -> None:
    ids = [sample_id for sample_id, _, _ in samples.CATALOGUE]
    assert len(set(ids)) == len(ids)
    assert ids[:2] == ["scene", "scene_coverage"]
    assert {"scene_fsk4", "scene_wav", "scene_raw"} <= set(ids)


def test_a_raw_sample_opens_with_its_sample_rate_unknown_and_a_wav_with_it_measured(
    client: TestClient, sample_dir: Path
) -> None:
    _write_other_samples(sample_dir)
    raw = client.post("/api/v1/samples/scene_raw/open").json()
    assert raw["container"] != "SigMF" and raw["sampleRate"] is None
    assert raw["assumptions"]["sampleRate"]["level"] == "UNKNOWN"
    wav = client.post("/api/v1/samples/scene_wav/open").json()
    assert wav["sampleRate"] == 48_000
    assert wav["assumptions"]["sampleRate"]["level"] == "MEASURED"
