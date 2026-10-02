"""Opening a recording and fetching its tiles over the API (PLAN §5 M2)."""

import csv
import hashlib
import io
import json
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient
from numpy.typing import NDArray

from backend import cli
from backend.app import create_app
from dsp.ingest.formats import SampleFormat

RATE = 1e6  # the fixtures' sample rate, and the synth signal's offset from the centre
OFFSET = 0.2


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>Sanket</title>")
    return dist


@pytest.fixture
def client(dist: Path) -> TestClient:
    return TestClient(create_app(dist))


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


def test_a_complex_recording_reports_its_capture_quality(
    client: TestClient, sigmf_path: Path
) -> None:
    body = client.post("/api/v1/recordings", json={"path": str(sigmf_path)}).json()
    quality = {p["id"]: p for p in body["captureQuality"]}
    assert list(quality) == [
        "clipping",
        "dc_offset",
        "iq_gain_imbalance",
        "iq_phase_imbalance",
        "gaps",
    ]
    assert quality["clipping"]["level"] == "MEASURED" and quality["clipping"]["warnings"] == []
    assert quality["gaps"]["value"] == 0
    assert all(p["method"] and p["evidence"] for p in quality.values())


def test_a_real_recording_has_no_iq_imbalance_in_its_capture_quality(
    client: TestClient, tmp_path: Path, samples: NDArray[np.complex128]
) -> None:
    path = tmp_path / "audio.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48_000)
        w.writeframes(SampleFormat.parse("ri16_le").encode(samples.real / np.max(samples.real)))
    body = client.post("/api/v1/recordings", json={"path": str(path)}).json()
    assert body["real"] is True
    assert [p["id"] for p in body["captureQuality"]] == ["clipping", "dc_offset", "gaps"]


def test_an_unknown_sample_rate_omits_hz_rather_than_guessing_one(
    client: TestClient, tmp_path: Path
) -> None:
    """A raw file with no metadata states no sample rate; the API must say so (None), never
    default one just so freqsHz has units (PLAN's "never assume a sample rate" rule)."""
    fmt = SampleFormat.parse("cf32_le")
    rng = np.random.default_rng(2)
    noise = rng.normal(size=20_000) + 1j * rng.normal(size=20_000)
    x = np.exp(2j * np.pi * 0.1 * np.arange(20_000)) + 0.05 * noise  # a tone has no symbol rate
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


def box_of(body: dict[str, Any]) -> tuple[float, float]:
    (d,) = body["detections"]
    return d["box"]["f0"], d["box"]["f1"]


def test_the_signal_sits_where_the_synth_put_it(client: TestClient, sigmf_path: Path) -> None:
    """Ground truth for the swap tests below: one QPSK signal at +0.2 of the sample rate."""
    f0, f1 = box_of(open_and_finish(client, sigmf_path))
    assert f0 < OFFSET * RATE < f1


def test_swapping_iq_mirrors_the_spectrum_and_says_the_analyst_chose_it(
    client: TestClient, sigmf_path: Path
) -> None:
    opened = open_and_finish(client, sigmf_path)
    assert opened["assumptions"]["iqOrder"]["level"] == "HYPOTHESIS"
    f0, f1 = box_of(opened)

    body = client.put(
        f"/api/v1/recordings/{opened['id']}/assumptions", json={"iqOrder": "QI"}
    ).json()
    order = body["assumptions"]["iqOrder"]
    assert (order["value"], order["level"]) == ("QI", "MEASURED")
    assert order["method"] == "Entered by the analyst"
    assert any("Sanket assumed IQ" in w for w in order["warnings"])  # it overrode the assumption
    # The tiles and the detections were built again from swapped samples: the signal is now at
    # -0.2 of the rate, and so is the spectrum's strongest bin (anywhere in a flat-topped band).
    m0, m1 = box_of(body)
    assert m0 == pytest.approx(-f1, abs=RATE / body["fftSize"])
    assert m1 == pytest.approx(-f0, abs=RATE / body["fftSize"])
    peak = np.argmax(body["psdDb"])
    assert m0 <= body["freqsHz"][peak] <= m1
    events = progress_events(client, body["id"])
    assert events[-1]["state"] == "done"
    done = client.get(f"/api/v1/recordings/{body['id']}").json()
    assert done["detections"][0]["analysis"] is not None

    # Swapping back restores the original picture; entering the convention is no conflict.
    back = client.put(
        f"/api/v1/recordings/{opened['id']}/assumptions", json={"iqOrder": "IQ"}
    ).json()
    assert box_of(back) == pytest.approx((f0, f1))
    assert back["assumptions"]["iqOrder"]["warnings"] == []


def test_entering_iq_order_on_a_real_recording_is_refused(
    client: TestClient, tmp_path: Path, samples: NDArray[np.complex128]
) -> None:
    path = tmp_path / "audio.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48_000)
        w.writeframes(SampleFormat.parse("ri16_le").encode(samples.real / np.max(samples.real)))
    opened = client.post("/api/v1/recordings", json={"path": str(path)}).json()
    assert opened["real"] is True and opened["assumptions"]["iqOrder"] is None
    response = client.put(f"/api/v1/recordings/{opened['id']}/assumptions", json={"iqOrder": "QI"})
    assert response.status_code == 422 and "complex" in response.json()["detail"]
    assert (
        client.put(
            f"/api/v1/recordings/{opened['id']}/assumptions", json={"iqOrder": "XY"}
        ).status_code
        == 422
    )


def test_an_entered_centre_frequency_replaces_the_files_and_warns(
    client: TestClient, sigmf_path: Path
) -> None:
    opened = client.post("/api/v1/recordings", json={"path": str(sigmf_path)}).json()
    assert opened["assumptions"]["centerFrequency"]["value"] == 1e8
    body = client.put(
        f"/api/v1/recordings/{opened['id']}/assumptions", json={"centerFrequency": 433.92e6}
    ).json()
    centre = body["assumptions"]["centerFrequency"]
    assert (centre["value"], centre["level"]) == (433.92e6, "MEASURED")
    assert centre["method"] == "Entered by the analyst"
    assert any("the file gives" in w.lower() for w in centre["warnings"])
    assert body["assumptions"]["sampleRate"]["value"] == 1e6  # the rest is untouched


def test_a_numbered_sequence_opens_as_one_recording_with_the_boxes_of_the_whole(
    client: TestClient,
    tmp_path: Path,
    samples: NDArray[np.complex128],
    write_wav: Callable[..., Path],
) -> None:
    peak = float(np.max(np.abs(samples)))
    whole = write_wav(tmp_path / "whole.wav", samples, peak=peak)
    for i, part in enumerate(np.array_split(samples, 4)):
        write_wav(tmp_path / f"cap_{i}.wav", part, peak=peak)
    truth = open_and_finish(client, whole)

    opened = client.post(
        "/api/v1/recordings", json={"path": str(tmp_path / "cap_2.wav"), "sequence": True}
    ).json()
    assert opened["container"] == "Numbered sequence"
    assert opened["name"] == "cap_0.wav (+3 files)"
    assert opened["numSamples"] == len(samples)
    assert box_of(opened) == pytest.approx(box_of(truth))
    assert opened["detections"][0]["box"] == truth["detections"][0]["box"]


def test_a_sequence_without_numbered_siblings_is_a_client_error(
    client: TestClient, sigmf_path: Path
) -> None:
    response = client.post("/api/v1/recordings", json={"path": str(sigmf_path), "sequence": True})
    assert response.status_code == 422 and "numbered siblings" in response.json()["detail"]


def test_a_folder_is_listed_as_inputs_and_is_not_itself_a_recording(
    client: TestClient,
    tmp_path: Path,
    samples: NDArray[np.complex128],
    write_wav: Callable[..., Path],
) -> None:
    for i in (0, 1):
        write_wav(tmp_path / f"cap_{i}.wav", samples)
    write_wav(tmp_path / "solo.wav", samples)
    (tmp_path / "notes.txt").write_text("not a recording")
    listed = client.post("/api/v1/inputs", json={"path": str(tmp_path)}).json()
    assert [i["name"] for i in listed] == ["cap_0.wav", "cap_1.wav", "solo.wav"]
    assert all(i["files"] == 1 and not i["sequence"] for i in listed)
    joined = client.post("/api/v1/inputs", json={"path": str(tmp_path), "sequence": True}).json()
    assert [(i["name"], i["files"], i["sequence"]) for i in joined] == [
        ("cap_0.wav (+1 files)", 2, True),
        ("solo.wav", 1, False),
    ]
    # Each listed input opens as the recording it names.
    first = client.post(
        "/api/v1/recordings", json={"path": joined[0]["path"], "sequence": joined[0]["sequence"]}
    )
    assert first.status_code == 200 and first.json()["numSamples"] == 2 * len(samples)

    response = client.post("/api/v1/recordings", json={"path": str(tmp_path)})
    assert response.status_code == 422 and "holds 3 recordings" in response.json()["detail"]
    assert client.post("/api/v1/inputs", json={"path": str(tmp_path / "no")}).status_code == 422


def test_an_unknown_format_offers_the_sniffers_candidates_and_takes_the_analysts_choice(
    client: TestClient, tmp_path: Path
) -> None:
    """All-zero bytes fit every width: the sniffer can't choose, and says which it can't."""
    path = tmp_path / "silence.bin"
    path.write_bytes(bytes(1 << 16))
    refused = client.post("/api/v1/recordings", json={"path": str(path)})
    assert refused.status_code == 422
    assert set(refused.json()["formatCandidates"]) == {"ci32_le", "ri32_le", "ci16_le", "ri16_le"}
    assert "unknown" in refused.json()["detail"]

    complex_ = client.post(
        "/api/v1/recordings", json={"path": str(path), "datatype": "ci16_le"}
    ).json()
    datatype = complex_["assumptions"]["datatype"]
    assert (datatype["value"], datatype["level"]) == ("ci16_le", "MEASURED")
    assert datatype["method"] == "Entered by the analyst"
    assert any("candidates offered" in e for e in datatype["evidence"])
    assert complex_["real"] is False and complex_["numSamples"] == (1 << 16) // 4
    real = client.post("/api/v1/recordings", json={"path": str(path), "datatype": "ri16_le"}).json()
    assert real["real"] is True and real["numSamples"] == (1 << 16) // 2


def test_a_datatype_that_is_not_one_or_that_a_container_already_states_is_refused(
    client: TestClient, tmp_path: Path, sigmf_path: Path
) -> None:
    path = tmp_path / "silence.bin"
    path.write_bytes(bytes(1 << 16))
    bad = client.post("/api/v1/recordings", json={"path": str(path), "datatype": "bogus"})
    assert bad.status_code == 422 and "not a sample format" in bad.json()["detail"]
    stated = client.post("/api/v1/recordings", json={"path": str(sigmf_path), "datatype": "cu8"})
    assert stated.status_code == 422 and "state their own sample format" in stated.json()["detail"]


def test_the_frame_table_downloads_in_every_format_and_matches_what_was_sent(
    client: TestClient, framed_path: Path, transmitted: set[str]
) -> None:
    opened = open_and_finish(client, framed_path)
    url = f"/api/v1/recordings/{opened['id']}/detections/0/frames"
    reported = opened["detections"][0]["analysis"]["frames"]
    passing = [f["payloadHex"] for f in reported if f["crc"] == "pass"]
    assert len(passing) >= 30 and set(passing) <= transmitted

    as_json = client.get(url, params={"format": "json"})
    assert as_json.headers["content-type"] == "application/json"
    assert 'filename="framed.signal_0.frames.json"' in as_json.headers["content-disposition"]
    assert as_json.json()["frames"] == reported

    as_csv = client.get(url, params={"format": "csv"})
    assert as_csv.headers["content-type"].startswith("text/csv")
    assert len(as_csv.text.splitlines()) == 1 + len(reported)

    as_hex = client.get(url, params={"format": "hex"})
    assert as_hex.text.split() == passing
    assert 'frames.hex.txt"' in as_hex.headers["content-disposition"]
    as_bits = client.get(url, params={"format": "bits"})
    assert [int(line, 2) for line in as_bits.text.split()] == [int(h, 16) for h in passing]
    assert client.get(url).text == as_json.text  # JSON is the default


def test_the_frame_table_of_something_that_is_not_there_is_refused(
    client: TestClient, sigmf_path: Path
) -> None:
    opened = open_and_finish(client, sigmf_path)
    base = f"/api/v1/recordings/{opened['id']}/detections"
    assert client.get("/api/v1/recordings/nope/detections/0/frames").status_code == 404
    assert client.get(f"{base}/5/frames").status_code == 404
    assert client.get(f"{base}/-1/frames").status_code == 404
    assert client.get(f"{base}/0/frames", params={"format": "xml"}).status_code == 422
    # This scene carries no frames: an empty table, not an error.
    assert client.get(f"{base}/0/frames", params={"format": "hex"}).text == ""


def test_a_symbol_rate_that_fits_one_file_name_rate_makes_it_a_hypothesis_and_analyses(
    client: TestClient, tmp_path: Path, write_raw_bpsk: Callable[..., Path]
) -> None:
    """9,600 Bd over 2.4 MS/s: the name offers 2.4 MS/s and AIS's rate fits it, so the rate is a
    HYPOTHESIS that says so, listed for review, and the analysis runs in hertz."""
    path = write_raw_bpsk(tmp_path / "ais_fs=2.4M.cu8", baud=9600, rate=2.4e6)
    body = client.post("/api/v1/recordings", json={"path": str(path)}).json()
    rate = body["assumptions"]["sampleRate"]
    assert body["sampleRate"] == 2.4e6 and rate["value"] == 2.4e6
    assert rate["level"] == "HYPOTHESIS" and rate["method"].startswith("Structural match")
    assert "9600 Bd" in " ".join(rate["evidence"])
    assert rate["convention"]  # so it is listed under needsReview
    assert body["analysis"]["total"] == len(body["detections"]) >= 1
    events = progress_events(client, body["id"])
    assert events[-1]["state"] == "done"
    done = client.get(f"/api/v1/recordings/{body['id']}").json()
    estimate = next(s for s in done["detections"][0]["analysis"]["stages"] if s["id"] == "estimate")
    symbol_rate = next(p for p in estimate["parameters"] if p["id"] == "symbol_rate")
    assert symbol_rate["unit"] == "Bd" and symbol_rate["level"] == "ESTIMATED"
    assert any("sample rate, which is a HYPOTHESIS" in w for w in symbol_rate["warnings"])
    assert any("does not confirm that rate independently" in w for w in symbol_rate["warnings"])


def test_ambiguous_rates_stay_unknown_with_the_test_in_the_evidence(
    client: TestClient, tmp_path: Path, write_raw_bpsk: Callable[..., Path]
) -> None:
    """9,600 Bd at 2.4 MS/s and 4,800 Bd at 1.2 MS/s look alike; with no name to choose, the
    rate stays UNKNOWN and the prompt can say why."""
    path = write_raw_bpsk(tmp_path / "capture.cu8", baud=9600, rate=2.4e6)
    body = client.post("/api/v1/recordings", json={"path": str(path)}).json()
    rate = body["assumptions"]["sampleRate"]
    assert body["sampleRate"] is None and rate["level"] == "UNKNOWN"
    assert "different sample rates" in rate["evidence"][-1]
    assert body["detections"] == []


def test_an_entered_rate_replaces_the_structural_one(
    client: TestClient, tmp_path: Path, write_raw_bpsk: Callable[..., Path]
) -> None:
    path = write_raw_bpsk(tmp_path / "ais_fs=2.4M.cu8", baud=9600, rate=2.4e6)
    opened = client.post("/api/v1/recordings", json={"path": str(path)}).json()
    body = client.put(
        f"/api/v1/recordings/{opened['id']}/assumptions", json={"sampleRate": 2.048e6}
    ).json()
    rate = body["assumptions"]["sampleRate"]
    assert body["sampleRate"] == 2.048e6 and rate["level"] == "MEASURED"
    assert any("Sanket inferred 2400000.0" in w and "HYPOTHESIS" in w for w in rate["warnings"])


def test_noise_alone_never_yields_a_hypothesis_rate(client: TestClient, tmp_path: Path) -> None:
    """The structural test's null case: a file named for a rate, holding only noise."""
    rng = np.random.default_rng(3)
    noise = 0.2 * (rng.normal(size=1 << 18) + 1j * rng.normal(size=1 << 18))
    path = tmp_path / "noise_fs=2.4M.cu8"
    path.write_bytes(SampleFormat.parse("cu8").encode(noise))
    body = client.post("/api/v1/recordings", json={"path": str(path)}).json()
    assert body["sampleRate"] is None
    assert body["assumptions"]["sampleRate"]["level"] == "UNKNOWN"


def test_the_results_download_is_the_document_sanket_analyse_writes(
    client: TestClient, framed_path: Path, tmp_path: Path
) -> None:
    opened = open_and_finish(client, framed_path)
    url = f"/api/v1/recordings/{opened['id']}/results"

    as_json = client.get(url)
    assert as_json.headers["content-type"] == "application/json"
    assert 'filename="framed.results.json"' in as_json.headers["content-disposition"]
    assert cli.main(["analyse", str(framed_path), "--out", str(tmp_path / "cli")]) == 0
    written = (tmp_path / "cli" / "framed.results.json").read_text(encoding="utf-8")
    assert as_json.text == written  # the UI's export and the CLI's file are the same bytes
    data = as_json.json()
    assert data["signals"][0]["level"] == "VERIFIED"
    assert data["signals"][0]["frames"] == opened["detections"][0]["analysis"]["frames"]

    as_csv = client.get(url, params={"format": "csv"})
    assert as_csv.headers["content-type"].startswith("text/csv")
    assert 'filename="framed.results.csv"' in as_csv.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(as_csv.text)))
    assert [r["stage"] for r in rows if r["id"] == "headline"] == ["headline"]
    verified = [r for r in rows if r["level"] == "VERIFIED"]
    assert verified and all(r["proof"] for r in verified)

    as_text = client.get(url, params={"format": "txt"})
    assert as_text.headers["content-type"].startswith("text/plain")
    assert 'filename="framed.summary.txt"' in as_text.headers["content-disposition"]
    assert "Signal 1 (signal_0), VERIFIED:" in as_text.text
    assert "pass their CRC" in as_text.text

    as_run = client.get(url, params={"format": "run"})
    assert as_run.headers["content-type"] == "application/json"
    assert 'filename="framed.run.json"' in as_run.headers["content-disposition"]
    record = as_run.json()
    assert record["resultsSha256"] == hashlib.sha256(as_json.content).hexdigest()
    names = [p["name"] for p in record["phases"]]
    assert names[:3] == ["tiles", "detect", "capture-quality"] and "signal_0" in names

    as_pdf = client.get(url, params={"format": "pdf"})
    assert as_pdf.headers["content-type"] == "application/pdf"
    assert 'filename="framed.report.pdf"' in as_pdf.headers["content-disposition"]
    assert as_pdf.content.startswith(b"%PDF")
    # It cites the hash of the JSON the download above returned, so the two are one analysis.
    digest = hashlib.sha256(as_json.content).hexdigest()
    assert pdf_text(as_pdf.content).replace(chr(10), "").find(digest[:16]) >= 0


def test_results_of_something_that_is_not_there_or_not_a_format_are_refused(
    client: TestClient, sigmf_path: Path
) -> None:
    assert client.get("/api/v1/recordings/nope/results").status_code == 404
    opened = open_and_finish(client, sigmf_path)
    url = f"/api/v1/recordings/{opened['id']}/results"
    assert client.get(url, params={"format": "xml"}).status_code == 422


def pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    return "".join(page.extract_text() for page in PdfReader(io.BytesIO(data)).pages)


def test_a_recording_says_which_sigmf_output_it_supports(
    client: TestClient,
    sigmf_path: Path,
    samples: NDArray[np.complex128],
    write_wav: Callable[..., Path],
    tmp_path: Path,
) -> None:
    raw = tmp_path / "capture_fs=1M.cf32"
    raw.write_bytes(sigmf_path.with_suffix(".sigmf-data").read_bytes())
    wav = write_wav(tmp_path / "audio.wav", samples)
    # A raw file can be annotated and saved beside; a SigMF recording only annotated; a WAV neither.
    assert open_and_finish(client, raw)["sigmf"] == "save"
    assert open_and_finish(client, sigmf_path)["sigmf"] == "annotate"
    wav_info = open_and_finish(client, wav)
    assert wav_info["sigmf"] == "none"
    url = f"/api/v1/recordings/{wav_info['id']}/results"
    assert client.get(url, params={"format": "sigmf"}).status_code == 422
