"""Opening a recording and fetching its tiles over the API (PLAN §5 M2)."""

import json
from pathlib import Path
from typing import Any

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


def progress_events(client: TestClient, recording_id: str) -> list[dict[str, Any]]:
    """Every `progress` event the analysis stream sends, until it ends (after `done`)."""
    events: list[dict[str, Any]] = []
    with client.stream("GET", f"/api/v1/recordings/{recording_id}/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        for line in response.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line.removeprefix("data: ")))
    return events


def open_and_finish(client: TestClient, path: Path) -> dict[str, Any]:
    """Open a recording, wait for its background analysis to end, and return it fetched again."""
    opened = client.post("/api/v1/recordings", json={"path": str(path)}).json()
    events = progress_events(client, opened["id"])
    assert events[-1]["state"] == "done"
    return client.get(f"/api/v1/recordings/{opened['id']}").json()


def test_opening_a_recording_returns_its_assumptions_and_pyramid_shape(
    client: TestClient, sigmf_path: Path
) -> None:
    response = client.post("/api/v1/recordings", json={"path": str(sigmf_path)})
    assert response.status_code == 200
    body = response.json()
    assert body["container"] == "SigMF"
    assert body["numSamples"] == 1 << 16
    assert body["real"] is False
    assert body["synthetic"] is True and body["recorder"].startswith("sanket dsp.synth")
    assert body["assumptions"]["sampleRate"]["value"] == 1e6
    assert len(body["levels"]) >= 1
    assert body["levels"][0]["rowSpan"] == 1
    assert body["dbMax"] > body["dbMin"]
    assert body["sampleRate"] == 1e6
    assert len(body["psdDb"]) == len(body["freqsHz"]) == body["levels"][0]["cols"]
    # Every level-0 row stands for its true duration: together they span the recording.
    rows = body["levels"][0]["rows"]
    assert abs(body["hop"] * rows - body["numSamples"]) <= body["fftSize"]


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
    # ... but the axis is still there as fractions of the rate, so the UI can draw it.
    assert len(body["freqsNorm"]) == body["levels"][0]["cols"]
    assert all(-0.5 <= f <= 0.5 for f in body["freqsNorm"])
    assert len(body["psdDb"]) == body["levels"][0]["cols"]  # still reported, unitless
    assert body["detections"] == []  # a box in seconds/Hz needs a known rate, same as freqsHz


def test_a_detection_reports_a_box_in_seconds_and_hz_with_its_own_evidence(
    client: TestClient, sigmf_path: Path
) -> None:
    body = open_and_finish(client, sigmf_path)
    assert len(body["detections"]) == 1
    d = body["detections"][0]
    assert d["id"] == "signal_0"
    assert 0 <= d["box"]["t0"] < d["box"]["t1"]
    assert d["box"]["f0"] < d["box"]["f1"]
    params = {p["id"]: p for p in d["parameters"]}
    assert set(params) == {"center_frequency", "bandwidth", "start_sample", "stop_sample", "snr_db"}
    for p in params.values():
        assert p["level"] == "ESTIMATED"
    # The per-detection analysis (PLAN M3-M6): the real chain runs here (detect through
    # FEC), but this fixture's signal is uncoded and unframed (`frame=None`), so it can never
    # decode - no VERIFIED, no frames, and the honest reason is stated.
    analysis = d["analysis"]
    assert analysis["level"] != "VERIFIED"
    assert analysis["frames"] == []
    assert analysis["noFramesReason"]
    assert analysis["search"] is not None
    assert {"detect", "estimate", "sync", "classify", "demod"} <= {
        s["id"] for s in analysis["stages"]
    }


def test_a_missing_path_is_a_client_error_not_a_500(client: TestClient, tmp_path: Path) -> None:
    response = client.post("/api/v1/recordings", json={"path": str(tmp_path / "nope.sigmf-meta")})
    assert response.status_code == 422


def test_getting_a_recording_again_returns_the_same_info(
    client: TestClient, sigmf_path: Path
) -> None:
    opened = client.post("/api/v1/recordings", json={"path": str(sigmf_path)}).json()
    progress_events(client, opened["id"])  # let the background analysis finish first
    fetched = client.get(f"/api/v1/recordings/{opened['id']}").json()
    assert fetched["id"] == opened["id"]
    assert fetched == client.get(f"/api/v1/recordings/{opened['id']}").json()
    assert {k: v for k, v in fetched.items() if k not in ("analysis", "detections")} == {
        k: v for k, v in opened.items() if k not in ("analysis", "detections")
    }


def test_opening_returns_before_the_analysis_and_the_stream_counts_it_to_done(
    client: TestClient, sigmf_path: Path
) -> None:
    opened = client.post("/api/v1/recordings", json={"path": str(sigmf_path)}).json()
    # The boxes are there from the start; the chain's report for each is not necessarily.
    assert len(opened["detections"]) == 1
    assert opened["analysis"]["total"] == 1
    assert opened["analysis"]["state"] in ("running", "done")
    if opened["analysis"]["state"] == "running":
        assert opened["detections"][0]["analysis"] is None
    events = progress_events(client, opened["id"])
    assert events[-1] == {"state": "done", "done": 1, "total": 1}
    dones = [e["done"] for e in events]
    assert dones == sorted(dones)  # progress only moves forward
    assert all(e["state"] == "running" for e in events[:-1])
    finished = client.get(f"/api/v1/recordings/{opened['id']}").json()
    assert finished["analysis"] == events[-1]
    assert finished["detections"][0]["analysis"] is not None


def test_a_recording_with_nothing_to_analyse_is_done_at_once(
    client: TestClient, tmp_path: Path
) -> None:
    """No rate means no boxes are shown, so there is nothing for the job to do."""
    fmt = SampleFormat.parse("cf32_le")
    path = tmp_path / "capture.bin"
    path.write_bytes(fmt.encode(np.exp(2j * np.pi * 0.1 * np.arange(20_000))))
    opened = client.post("/api/v1/recordings", json={"path": str(path)}).json()
    assert opened["analysis"] == {"state": "done", "done": 0, "total": 0}
    assert progress_events(client, opened["id"]) == [{"state": "done", "done": 0, "total": 0}]


def test_the_event_stream_of_an_unknown_recording_is_404(client: TestClient) -> None:
    assert client.get("/api/v1/recordings/does-not-exist/events").status_code == 404


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


def test_entering_the_sample_rate_gives_hz_boxes_and_starts_the_analysis(
    client: TestClient, sigmf_path: Path, tmp_path: Path
) -> None:
    """A raw copy of a synth capture has no rate; entering the true one must give the same
    boxes as the SigMF, marked as analyst-entered rather than as something the file said."""
    truth = open_and_finish(client, sigmf_path)
    raw = tmp_path / "capture.bin"
    raw.write_bytes(sigmf_path.with_suffix(".sigmf-data").read_bytes())
    unknown = client.post("/api/v1/recordings", json={"path": str(raw)}).json()
    assert unknown["sampleRate"] is None and unknown["detections"] == []

    response = client.put(
        f"/api/v1/recordings/{unknown['id']}/assumptions", json={"sampleRate": 1e6}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == unknown["id"]
    assert body["sampleRate"] == 1e6
    rate = body["assumptions"]["sampleRate"]
    assert rate["level"] == "MEASURED" and rate["method"] == "Entered by the analyst"
    assert len(body["freqsHz"]) == len(body["psdDb"])
    assert body["analysis"]["total"] == len(truth["detections"]) == 1
    assert body["detections"][0]["box"]["f0"] == pytest.approx(
        truth["detections"][0]["box"]["f0"], abs=1e-3
    )
    events = progress_events(client, body["id"])
    assert events[-1] == {"state": "done", "done": 1, "total": 1}
    done = client.get(f"/api/v1/recordings/{body['id']}").json()
    assert done["detections"][0]["analysis"] is not None


def test_an_entered_rate_that_contradicts_the_file_warns_and_wins(
    client: TestClient, sigmf_path: Path
) -> None:
    opened = client.post("/api/v1/recordings", json={"path": str(sigmf_path)}).json()
    assert opened["assumptions"]["sampleRate"]["warnings"] == []
    body = client.put(
        f"/api/v1/recordings/{opened['id']}/assumptions", json={"sampleRate": 2e6}
    ).json()
    rate = body["assumptions"]["sampleRate"]
    assert body["sampleRate"] == 2e6 and rate["value"] == 2e6
    assert rate["level"] == "MEASURED" and rate["method"] == "Entered by the analyst"
    assert any("file gives 1000000.0" in w and "2000000.0" in w for w in rate["warnings"])
    # Entering what the file already says is not a conflict.
    same = client.put(
        f"/api/v1/recordings/{opened['id']}/assumptions", json={"sampleRate": 1e6}
    ).json()
    assert same["assumptions"]["sampleRate"]["warnings"] == []


def test_a_candidate_chosen_from_the_offered_list_says_the_analyst_chose_it(
    client: TestClient, tmp_path: Path
) -> None:
    raw = tmp_path / "capture.bin"
    raw.write_bytes(
        SampleFormat.parse("cf32_le").encode(np.exp(2j * np.pi * 0.1 * np.arange(20_000)))
    )
    opened = client.post("/api/v1/recordings", json={"path": str(raw)}).json()
    candidates = opened["assumptions"]["sampleRate"]["alternatives"]
    assert candidates
    chosen = candidates[0]["value"]
    typed = chosen * 1.5 + 1  # not on the list
    from_list = client.put(
        f"/api/v1/recordings/{opened['id']}/assumptions", json={"sampleRate": chosen}
    ).json()["assumptions"]["sampleRate"]
    assert any("candidates offered" in e for e in from_list["evidence"])
    assert from_list["warnings"] == []  # the file gave nothing to contradict
    typed_in = client.put(
        f"/api/v1/recordings/{opened['id']}/assumptions", json={"sampleRate": typed}
    ).json()["assumptions"]["sampleRate"]
    assert not any("candidates offered" in e for e in typed_in["evidence"])


def test_a_non_positive_or_non_finite_rate_is_refused(client: TestClient, sigmf_path: Path) -> None:
    opened = client.post("/api/v1/recordings", json={"path": str(sigmf_path)}).json()
    for bad in (0, -1e6):
        response = client.put(
            f"/api/v1/recordings/{opened['id']}/assumptions", json={"sampleRate": bad}
        )
        assert response.status_code == 422
    assert client.put("/api/v1/recordings/nope/assumptions", json={}).status_code == 404
