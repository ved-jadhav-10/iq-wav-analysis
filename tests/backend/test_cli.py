import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from jsonschema import Draft202012Validator
from numpy.typing import NDArray

from backend import cli
from dsp.report import DetectionReport
from dsp.results import SCHEMA_PATH, SCHEMA_VERSION, Results


@pytest.fixture
def dist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "index.html").write_text("<!doctype html>")
    monkeypatch.setenv("SANKET_FRONTEND_DIST", str(tmp_path))
    return tmp_path


@pytest.fixture
def served(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    calls: dict[str, Any] = {}
    monkeypatch.setattr(cli.uvicorn, "run", lambda app, **kw: calls.update(kw))
    return calls


def test_binds_loopback_by_default(dist: Path, served: dict[str, Any]) -> None:
    assert cli.main([]) == 0
    assert served == {"host": "127.0.0.1", "port": 8765}


def test_warns_when_binding_beyond_loopback(
    dist: Path, served: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["--host", "0.0.0.0"]) == 0
    assert "exposes Sanket beyond this machine" in capsys.readouterr().err


def test_missing_frontend_build_fails_with_instructions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    served: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("SANKET_FRONTEND_DIST", str(tmp_path / "missing"))
    assert cli.main([]) == 1
    assert "npm run build" in capsys.readouterr().err
    assert served == {}


# -- sanket analyse ----------------------------------------------------------------------------

RATE = 1e6
OFFSET_HZ = 0.2 * RATE  # where the synth put the signal, from the capture centre
TOLERANCE_HZ = 1e3  # the carrier estimate is good to well under this on this scene
RESULTS_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator(RESULTS_SCHEMA).validate(data)
    return data


def signal_centre(data: dict[str, Any]) -> float:
    """The signal's carrier in Hz from the centre, as the estimate stage reports it."""
    (signal,) = data["signals"]
    estimate = next(s for s in signal["stages"] if s["id"] == "estimate")
    return next(p["value"] for p in estimate["parameters"] if p["id"] == "carrier")


def test_analyse_writes_the_results_document_for_a_recording(
    tmp_path: Path, sigmf_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out"
    assert cli.main(["analyse", str(sigmf_path), "--out", str(out)]) == 0
    data = load(out / "rec.results.json")
    assert data["assumptions"]["sampleRate"]["value"] == RATE
    assert [s["id"] for s in data["stages"]] == ["ingest", "capture", "detect"]
    assert data["stages"][2]["summary"] == "1 signal(s) found"
    capture = data["stages"][1]
    assert {p["id"] for p in capture["parameters"]} == {
        "clipping",
        "dc_offset",
        "iq_gain_imbalance",
        "iq_phase_imbalance",
        "gaps",
    }
    assert all(p["level"] in ("MEASURED", "ESTIMATED") for p in capture["parameters"])
    assert data["signals"][0]["id"] == "signal_0"
    assert {"detect", "estimate", "sync", "classify", "demod"} <= {
        s["id"] for s in data["signals"][0]["stages"]
    }
    assert abs(signal_centre(data) - OFFSET_HZ) < TOLERANCE_HZ
    printed = capsys.readouterr().out
    assert "rec.sigmf-meta: 1 signal(s)" in printed and "signal_0:" in printed


def test_analyse_is_deterministic(tmp_path: Path, sigmf_path: Path) -> None:
    for name in ("a", "b"):
        assert cli.main(["analyse", str(sigmf_path), "--out", str(tmp_path / name)]) == 0
    assert (tmp_path / "a" / "rec.results.json").read_bytes() == (
        tmp_path / "b" / "rec.results.json"
    ).read_bytes()


def test_analyse_takes_entries_for_what_the_file_lacks(tmp_path: Path, sigmf_path: Path) -> None:
    raw = tmp_path / "capture.bin"
    raw.write_bytes(sigmf_path.with_suffix(".sigmf-data").read_bytes())
    without = tmp_path / "without"
    assert cli.main(["analyse", str(raw), "--out", str(without)]) == 0
    unknown = load(without / "capture.results.json")
    # No rate: the bands are found and not analysed, and the results say so.
    assert unknown["assumptions"]["sampleRate"]["value"] is None
    assert unknown["signals"] == []
    assert "sample rate is UNKNOWN" in unknown["stages"][-1]["summary"]

    entered = tmp_path / "entered"
    assert cli.main(["analyse", str(raw), "--out", str(entered), "--sample-rate", "1M"]) == 0
    data = load(entered / "capture.results.json")
    rate = data["assumptions"]["sampleRate"]
    assert (rate["value"], rate["level"]) == (RATE, "MEASURED")
    assert rate["method"] == "Entered by the analyst"
    assert abs(signal_centre(data) - OFFSET_HZ) < TOLERANCE_HZ


def test_analyse_infers_a_raw_files_rate_from_a_recognised_symbol_rate(
    tmp_path: Path, write_raw_bpsk: Callable[..., Path]
) -> None:
    raw = write_raw_bpsk(tmp_path / "ais_fs=2.4M.cu8", baud=9600, rate=2.4e6)
    assert cli.main(["analyse", str(raw), "--out", str(tmp_path / "out")]) == 0
    data = load(tmp_path / "out" / "ais_fs=2.4M.results.json")
    rate = data["assumptions"]["sampleRate"]
    assert (rate["value"], rate["level"]) == (2.4e6, "HYPOTHESIS")
    assert data["signals"]  # analysed, in hertz
    assert "sample_rate" in [item["parameter"] for item in data["needsReview"]]


def test_analyse_infers_the_rate_from_a_file_whose_iq_order_is_swapped(
    tmp_path: Path, write_raw_bpsk: Callable[..., Path]
) -> None:
    raw = write_raw_bpsk(tmp_path / "ais_fs=2.4M.cu8", baud=9600, rate=2.4e6, swapped=True)
    out = tmp_path / "out"
    assert cli.main(["analyse", str(raw), "--out", str(out), "--iq-order", "QI"]) == 0
    rate = load(out / "ais_fs=2.4M.results.json")["assumptions"]["sampleRate"]
    assert (rate["value"], rate["level"]) == (2.4e6, "HYPOTHESIS")


def test_analyse_iq_order_qi_mirrors_the_signal(tmp_path: Path, sigmf_path: Path) -> None:
    assert cli.main(["analyse", str(sigmf_path), "--out", str(tmp_path), "--iq-order", "QI"]) == 0
    data = load(tmp_path / "rec.results.json")
    order = data["assumptions"]["iqOrder"]
    assert (order["value"], order["level"]) == ("QI", "MEASURED")
    assert abs(signal_centre(data) + OFFSET_HZ) < TOLERANCE_HZ


def test_analyse_a_folder_is_a_batch_and_one_bad_file_does_not_stop_it(
    tmp_path: Path,
    samples: NDArray[np.complex128],
    write_wav: Callable[..., Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    batch = tmp_path / "batch"
    batch.mkdir()
    write_wav(batch / "one.wav", samples)
    write_wav(batch / "two.wav", samples)
    (batch / "broken.cu8.gz").write_bytes(b"\x1f\x8b" + bytes(30))
    (batch / "notes.txt").write_text("not a recording")
    out = tmp_path / "out"
    assert cli.main(["analyse", str(batch), "--out", str(out)]) == 1  # the .gz is refused
    assert sorted(p.name for p in out.iterdir()) == ["one.results.json", "two.results.json"]
    assert signal_centre(load(out / "one.results.json")) == pytest.approx(
        signal_centre(load(out / "two.results.json"))
    )
    assert "broken.cu8.gz" in capsys.readouterr().err


def test_analyse_sequence_reads_numbered_files_as_one_recording(
    tmp_path: Path, samples: NDArray[np.complex128], write_wav: Callable[..., Path]
) -> None:
    peak = float(np.max(np.abs(samples)))
    whole = write_wav(tmp_path / "whole.wav", samples, peak=peak)
    parts = tmp_path / "parts"
    parts.mkdir()
    for i, part in enumerate(np.array_split(samples, 3)):
        write_wav(parts / f"cap_{i}.wav", part, peak=peak)
    out = tmp_path / "out"
    assert cli.main(["analyse", str(whole), str(parts), "--out", str(out), "--sequence"]) == 0
    assert sorted(p.name for p in out.iterdir()) == ["cap_0.results.json", "whole.results.json"]
    joined, single = load(out / "cap_0.results.json"), load(out / "whole.results.json")
    assert joined["stages"][0]["summary"] == "Numbered sequence: 65,536 samples"
    assert signal_centre(joined) == signal_centre(single)
    assert joined["signals"] == single["signals"]


def test_analyse_refuses_what_is_not_a_path_and_a_real_recording_with_an_iq_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["analyse", str(tmp_path / "missing.cu8"), "--out", str(tmp_path)]) == 1
    assert "not a file or a folder" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        cli.main(["analyse", "x", "--iq-order", "XY"])


def test_rates_take_si_suffixes() -> None:
    assert [cli._rate(t) for t in ("2.4M", "250k", "48000", "1e6", "1G")] == [  # pyright: ignore[reportPrivateUsage]
        2.4e6,
        250e3,
        48e3,
        1e6,
        1e9,
    ]
    for bad in ("abc", "M", "nan", "infM"):
        with pytest.raises(argparse.ArgumentTypeError):
            cli._rate(bad)  # pyright: ignore[reportPrivateUsage]


def test_analyse_asks_for_a_datatype_when_the_format_is_unknown_and_takes_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    silence = tmp_path / "silence.bin"
    silence.write_bytes(bytes(1 << 16))
    assert cli.main(["analyse", str(silence), "--out", str(tmp_path / "a")]) == 1
    err = capsys.readouterr().err
    assert "ci16_le" in err and "--datatype" in err
    args = ["analyse", str(silence), "--out", str(tmp_path / "b"), "--sample-rate", "1M"]
    assert cli.main([*args, "--datatype", "ci16_le"]) == 0
    datatype = load(tmp_path / "b" / "silence.results.json")["assumptions"]["datatype"]
    assert (datatype["value"], datatype["method"]) == ("ci16_le", "Entered by the analyst")


def test_analyse_writes_each_signals_frame_table_in_the_formats_asked_for(
    tmp_path: Path, framed_path: Path, transmitted: set[str]
) -> None:
    out = tmp_path / "out"
    args = ["analyse", str(framed_path), "--out", str(out)]
    assert cli.main([*args, "--frames", "hex", "--frames", "json", "--frames", "hex"]) == 0
    assert sorted(p.name for p in out.iterdir()) == [
        "framed.results.json",
        "framed.signal_0.frames.hex.txt",
        "framed.signal_0.frames.json",
    ]
    hexed = (out / "framed.signal_0.frames.hex.txt").read_text().split()
    assert len(hexed) >= 30 and set(hexed) <= transmitted
    frames = json.loads((out / "framed.signal_0.frames.json").read_text())["frames"]
    assert [f["payloadHex"] for f in frames if f["crc"] == "pass"] == hexed


def test_analyse_results_carry_each_signals_headline_ledger_and_frames(
    tmp_path: Path,
    framed_path: Path,
    transmitted: set[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reports: list[DetectionReport] = []
    analyse_recording = cli.analyse_recording

    def capture(*args: Any, **kwargs: Any) -> Any:
        results, found = analyse_recording(*args, **kwargs)
        reports[:] = found
        return results, found

    monkeypatch.setattr(cli, "analyse_recording", capture)
    for name in ("a", "b"):
        args = ["analyse", str(framed_path), "--out", str(tmp_path / name), "--frames", "json"]
        assert cli.main(args) == 0
    # The same input gives the same bytes: the ledger's p-values and the frames included.
    names = ["framed.results.json", "framed.signal_0.frames.json"]
    for file in names:
        assert (tmp_path / "a" / file).read_bytes() == (tmp_path / "b" / file).read_bytes()

    data = load(tmp_path / "a" / "framed.results.json")
    assert data["schemaVersion"] == SCHEMA_VERSION
    (report,) = reports
    (signal,) = data["signals"]
    # What the document holds is what the report concluded.
    assert (signal["label"], signal["kind"]) == (report.label, report.kind)
    assert (signal["level"], signal["headline"]) == (report.level.value, report.headline)
    assert signal["level"] == "VERIFIED"
    assert report.search is not None and signal["noSearchReason"] is None
    assert signal["search"] == report.search.model_dump(mode="json", by_alias=True)
    assert signal["search"]["tried"] > 0 and signal["search"]["rows"]
    assert any(row["outcome"] == "accepted" for row in signal["search"]["rows"])
    assert signal["noFramesReason"] is None
    assert signal["frames"] == [f.model_dump(mode="json", by_alias=True) for f in report.frames]
    passing = [f["payloadHex"] for f in signal["frames"] if f["crc"] == "pass"]
    assert len(passing) >= 30 and set(passing) <= transmitted
    assert [f["crc"] for f in signal["frames"]] == [f.crc for f in report.frames]
    # The frame-table export is the same table.
    table = json.loads((tmp_path / "a" / "framed.signal_0.frames.json").read_text())
    assert table["frames"] == signal["frames"]
    # And the document reads back as the model, and writes the same bytes.
    text = (tmp_path / "a" / "framed.results.json").read_text(encoding="utf-8")
    assert Results.model_validate_json(text).to_json() == text


def test_analyse_states_why_a_signal_has_no_frames_or_search(
    tmp_path: Path, sigmf_path: Path
) -> None:
    assert cli.main(["analyse", str(sigmf_path), "--out", str(tmp_path)]) == 0
    (signal,) = load(tmp_path / "rec.results.json")["signals"]
    assert signal["frames"] == [] and signal["noFramesReason"]
    assert (signal["search"] is None) == bool(signal["noSearchReason"])
    assert signal["level"] != "VERIFIED"  # nothing was decoded, so nothing is proven


def test_analyse_csv_writes_the_values_table_beside_the_results(
    tmp_path: Path, sigmf_path: Path
) -> None:
    out = tmp_path / "out"
    assert cli.main(["analyse", str(sigmf_path), "--out", str(out)]) == 0
    assert not (out / "rec.results.csv").exists()  # only when asked
    assert cli.main(["analyse", str(sigmf_path), "--out", str(out), "--csv"]) == 0
    table = (out / "rec.results.csv").read_text(encoding="utf-8").splitlines()
    assert table[0].startswith("signal,stage,id,name,value")
    assert any(line.startswith(",assumptions,sample_rate,") for line in table)
    assert any(line.startswith("signal_0,estimate,carrier,") for line in table)


def test_analyse_summary_writes_plain_text_beside_the_results(
    tmp_path: Path, sigmf_path: Path
) -> None:
    out = tmp_path / "out"
    assert cli.main(["analyse", str(sigmf_path), "--out", str(out)]) == 0
    assert not (out / "rec.summary.txt").exists()  # only when asked
    assert cli.main(["analyse", str(sigmf_path), "--out", str(out), "--summary"]) == 0
    text = (out / "rec.summary.txt").read_text(encoding="utf-8")
    assert text.startswith("Sanket ") and "Signal 1 (signal_0)" in text


def test_the_results_name_the_recordings_files_by_content_and_the_rule_sets(
    tmp_path: Path, sigmf_path: Path
) -> None:
    import hashlib

    out = tmp_path / "out"
    assert cli.main(["analyse", str(sigmf_path), "--out", str(out), "--csv", "--summary"]) == 0
    data = load(out / "rec.results.json")
    assert data["schemaVersion"] == SCHEMA_VERSION == "0.6.0"
    identity = data["recording"]
    assert identity["container"] and identity["samples"] > 0
    # The metadata file and the dataset it names, by name only, with the hash of each file's bytes.
    files = {f["name"]: f for f in identity["files"]}
    assert set(files) == {"rec.sigmf-meta", "rec.sigmf-data"}
    for name, f in files.items():
        raw = (sigmf_path.parent / name).read_bytes()
        assert f["sizeBytes"] == len(raw)
        assert f["sha256"] == hashlib.sha256(raw).hexdigest()
    assert all("/" not in f["name"] and "\\" not in f["name"] for f in identity["files"])
    assert {c["name"] for c in data["catalogues"]} == {
        "fec-interleaver",
        "framing",
        "known-systems",
    }
    # Every export carries the hash of the JSON it was made from.
    digest = hashlib.sha256((out / "rec.results.json").read_bytes()).hexdigest()
    assert digest in (out / "rec.results.csv").read_text(encoding="utf-8")
    assert f"Results SHA-256 {digest}" in (out / "rec.summary.txt").read_text(encoding="utf-8")


def test_a_sequence_hashes_every_file(tmp_path: Path, sigmf_path: Path) -> None:
    import hashlib

    raw = sigmf_path.with_suffix(".sigmf-data").read_bytes()
    half = len(raw) // 2 // 8 * 8
    first, second = tmp_path / "cap_1.cf32", tmp_path / "cap_2.cf32"
    first.write_bytes(raw[:half])
    second.write_bytes(raw[half:])
    out = tmp_path / "out"
    assert (
        cli.main(["analyse", str(first), "--sequence", "--sample-rate", "1M", "--out", str(out)])
        == 0
    )
    (results,) = list(out.glob("*.results.json"))
    names = [f["name"] for f in load(results)["recording"]["files"]]
    assert names == ["cap_1.cf32", "cap_2.cf32"]
    hashes = {f["name"]: f["sha256"] for f in load(results)["recording"]["files"]}
    assert hashes["cap_2.cf32"] == hashlib.sha256(second.read_bytes()).hexdigest()
