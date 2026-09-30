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
from dsp.results import SCHEMA_PATH


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
    assert [s["id"] for s in data["stages"]] == ["ingest", "detect"]
    assert data["stages"][1]["summary"] == "1 signal(s) found"
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
    assert "sample rate is UNKNOWN" in unknown["stages"][1]["summary"]

    entered = tmp_path / "entered"
    assert cli.main(["analyse", str(raw), "--out", str(entered), "--sample-rate", "1M"]) == 0
    data = load(entered / "capture.results.json")
    rate = data["assumptions"]["sampleRate"]
    assert (rate["value"], rate["level"]) == (RATE, "MEASURED")
    assert rate["method"] == "Entered by the analyst"
    assert abs(signal_centre(data) - OFFSET_HZ) < TOLERANCE_HZ


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
