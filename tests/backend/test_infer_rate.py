"""`infer_sample_rate`: a raw file's rate from structural matches across its signals (PLAN M2)."""

from pathlib import Path

import numpy as np
import pytest

import backend.analysis as analysis
from backend.analysis import infer_sample_rate
from dsp.detect import Detection
from dsp.evidence import EvidenceLevel
from dsp.ingest.dispatch import AnyRecording, open_path
from dsp.ingest.formats import SampleFormat


def signal(low: float = 0.0, high: float = 0.05) -> Detection:
    return Detection(
        start=0, stop=100_000, low=low, high=high, nfft=1024, snr_db=20.0, score=50.0, cells=100
    )


def raw(tmp_path: Path, name: str, datatype: str = "cu8") -> AnyRecording:
    x = np.exp(2j * np.pi * 0.1 * np.arange(4096)) * 0.3 + 0.5
    if not SampleFormat.parse(datatype).is_complex:
        x = x.real
    path = tmp_path / name
    path.write_bytes(SampleFormat.parse(datatype).encode(x))
    (opened,) = open_path(path)
    return opened.recording


def measuring(monkeypatch: pytest.MonkeyPatch, *rates: float | None) -> None:
    """Each call to the measurement returns the next value, with a 1 ppm uncertainty."""
    queue = list(rates)
    monkeypatch.setattr(
        analysis,
        "measure_symbol_rate",
        lambda reader, detection: None if (r := queue.pop(0)) is None else (r, 1e-6),
    )


def test_signals_that_agree_give_one_hypothesis_that_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = raw(tmp_path, "x_fs=2.4M.cu8")
    measuring(monkeypatch, 9600 / 2.4e6, 19200 / 2.4e6)
    param = infer_sample_rate(source, [signal(), signal(0.1, 0.2)])
    assert param is not None
    assert (param.value, param.level) == (2.4e6, EvidenceLevel.HYPOTHESIS)
    assert any("All 2 signals tested agree" in e for e in param.evidence)


def test_signals_that_imply_different_rates_decide_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = raw(tmp_path, "x_fs=2.4M_fs=2.048M.cu8")  # both named, so each signal can decide
    measuring(monkeypatch, 9600 / 2.4e6, 9600 / 2.048e6)
    param = infer_sample_rate(source, [signal(), signal(0.1, 0.2)])
    assert param is not None and param.value is None and param.level is EvidenceLevel.UNKNOWN
    text = " ".join(param.evidence)
    assert "Signal 1:" in text and "Signal 2:" in text
    assert "none is preferred" in text


def test_undecided_signals_keep_their_findings_in_the_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = raw(
        tmp_path, "capture.cu8"
    )  # 9,600 Bd at 2.4 MS/s and 4,800 Bd at 1.2 MS/s look alike
    measuring(monkeypatch, 9600 / 2.4e6, 0.0123457)
    param = infer_sample_rate(source, [signal(), signal(0.1, 0.2)])
    assert param is not None and param.level is EvidenceLevel.UNKNOWN
    text = " ".join(param.evidence)
    assert "Signal 1: " in text and "Signal 2: No structural match" in text


def test_a_signal_with_no_symbol_rate_is_reported_as_untested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = raw(tmp_path, "x_fs=2.4M.cu8")
    measuring(monkeypatch, 9600 / 2.4e6, None)
    param = infer_sample_rate(source, [signal(), signal(0.1, 0.2)])
    assert param is not None and param.level is EvidenceLevel.HYPOTHESIS
    assert param.value == 2.4e6
    # The budget is divided over both signals tried, though only one had a rate to test.
    assert "0.005" in " ".join(param.evidence)


def test_nothing_measurable_leaves_the_rate_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    measuring(monkeypatch, None)
    assert infer_sample_rate(raw(tmp_path, "x_fs=2.4M.cu8"), [signal()]) is None


def test_a_real_valued_recording_is_not_inferred(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    measuring(monkeypatch, 9600 / 2.4e6)
    assert infer_sample_rate(raw(tmp_path, "x_fs=2.4M.rf32", "rf32_le"), [signal()]) is None


def test_a_mirror_image_detection_is_not_measured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    measuring(monkeypatch, 9600 / 2.4e6)
    image = Detection(0, 100_000, -0.05, 0.0, 1024, 20.0, 50.0, 100, image_of=0)
    assert infer_sample_rate(raw(tmp_path, "x_fs=2.4M.cu8"), [image]) is None
