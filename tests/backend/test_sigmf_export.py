"""SigMF annotations and Save as SigMF through the CLI and the API (PLAN M7)."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend import cli
from backend.app import create_app
from dsp.ingest.sigmf import read_sigmf

from .conftest import OFFSET, RATE
from .test_recordings import open_and_finish


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html>")
    return TestClient(create_app(dist))


def raw_copy(sigmf_path: Path, tmp_path: Path) -> Path:
    raw = tmp_path / "capture.cf32"
    raw.write_bytes(sigmf_path.with_suffix(".sigmf-data").read_bytes())
    return raw


def test_analyse_sigmf_annotates_a_sigmf_recording_and_keeps_its_own_metadata(
    tmp_path: Path, sigmf_path: Path
) -> None:
    out = tmp_path / "out"
    assert cli.main(["analyse", str(sigmf_path), "--out", str(out), "--sigmf"]) == 0
    meta: dict[str, Any] = json.loads((out / "rec.sanket.sigmf-meta").read_text(encoding="utf-8"))
    original = json.loads(sigmf_path.read_text(encoding="utf-8"))
    assert meta["global"]["core:sample_rate"] == original["global"]["core:sample_rate"]
    assert meta["captures"] == original["captures"]
    mine = [a for a in meta["annotations"] if a.get("core:generator", "").startswith("Sanket")]
    (note,) = mine
    centre = original["captures"][0]["core:frequency"]
    middle = (note["core:freq_lower_edge"] + note["core:freq_upper_edge"]) / 2
    assert middle == pytest.approx(centre + OFFSET * RATE, abs=2e3)
    results = json.loads((out / "rec.results.json").read_text(encoding="utf-8"))
    detect = next(s for s in results["signals"][0]["stages"] if s["id"] == "detect")
    start = next(p["value"] for p in detect["parameters"] if p["id"] == "start_sample")
    assert note["core:sample_start"] == start
    digest = hashlib.sha256((out / "rec.results.json").read_bytes()).hexdigest()
    assert meta["global"]["sanket:provenance"]["results_sha256"] == digest


def test_save_sigmf_describes_a_raw_file_beside_it_without_touching_it(
    tmp_path: Path, sigmf_path: Path
) -> None:
    raw = raw_copy(sigmf_path, tmp_path)
    before = raw.read_bytes()
    out = tmp_path / "out"
    args = ["analyse", str(raw), "--out", str(out), "--sample-rate", "1M", "--save-sigmf"]
    assert cli.main(args) == 0
    assert raw.read_bytes() == before
    recording = read_sigmf(tmp_path / "capture.sigmf-meta")  # our own reader accepts it
    assert recording.data_path == raw
    assert recording.datatype.value == "cf32_le"
    assert recording.sample_rate.value == RATE
    # A second run refuses to overwrite it, and says so.
    assert cli.main(args) == 1


def test_save_sigmf_leaves_a_guessed_rate_out_of_the_standard_fields(
    tmp_path: Path, sigmf_path: Path
) -> None:
    raw = raw_copy(sigmf_path, tmp_path)
    assert cli.main(["analyse", str(raw), "--out", str(tmp_path / "o"), "--save-sigmf"]) == 0
    meta = json.loads((tmp_path / "capture.sigmf-meta").read_text(encoding="utf-8"))
    assert "core:sample_rate" not in meta["global"]  # no rate was stated or entered
    assumed = meta["global"]["sanket:provenance"]["assumptions"]["sample_rate"]
    assert assumed["level"] in ("UNKNOWN", "HYPOTHESIS")


def test_a_wav_is_not_describable_and_the_cli_says_so(
    tmp_path: Path, samples: Any, write_wav: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    wav = write_wav(tmp_path / "x.wav", samples)
    assert cli.main(["analyse", str(wav), "--out", str(tmp_path / "o"), "--sigmf"]) == 0
    assert "no SigMF annotations" in capsys.readouterr().err
    assert not list((tmp_path / "o").glob("*.sigmf-meta"))
    assert cli.main(["analyse", str(wav), "--out", str(tmp_path / "o"), "--save-sigmf"]) == 1


def test_the_api_serves_the_annotations_and_saves_beside_a_raw_file(
    client: TestClient, tmp_path: Path, sigmf_path: Path
) -> None:
    opened = open_and_finish(client, sigmf_path)
    served = client.get(f"/api/v1/recordings/{opened['id']}/results", params={"format": "sigmf"})
    assert 'filename="rec.sanket.sigmf-meta"' in served.headers["content-disposition"]
    assert served.json()["annotations"][-1]["core:label"]
    assert client.post(f"/api/v1/recordings/{opened['id']}/sigmf").status_code == 422  # not raw

    raw = raw_copy(sigmf_path, tmp_path)
    started = client.post("/api/v1/recordings", json={"path": str(raw)}).json()
    entered = client.put(
        f"/api/v1/recordings/{started['id']}/assumptions", json={"sampleRate": RATE}
    ).json()
    from .test_recordings import progress_events

    assert progress_events(client, entered["id"])[-1]["state"] == "done"
    saved = client.post(f"/api/v1/recordings/{entered['id']}/sigmf")
    assert saved.status_code == 200
    assert Path(saved.json()["path"]) == tmp_path / "capture.sigmf-meta"
    assert read_sigmf(tmp_path / "capture.sigmf-meta").sample_rate.value == RATE
    assert client.post(f"/api/v1/recordings/{entered['id']}/sigmf").status_code == 409
