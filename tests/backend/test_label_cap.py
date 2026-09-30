"""Which recordings cap a digital signal's labels at HYPOTHESIS, and that the cap reaches the
report (PLAN M2 gate: mono or lossy audio)."""

from pathlib import Path

import numpy as np
import soundfile as sf

from backend.analysis import analyse_detection, label_cap_reason
from dsp.detect import detect
from dsp.evidence import EvidenceLevel
from dsp.ingest.audio import read_audio
from dsp.ingest.dispatch import open_path
from tests.backend.conftest import Complex, WriteWav


def test_stereo_iq_is_not_capped(tmp_path: Path, samples: Complex, write_wav: WriteWav) -> None:
    (opened,) = open_path(write_wav(tmp_path / "iq.wav", samples))
    assert label_cap_reason(opened.recording) is None


def test_a_real_valued_recording_is_capped(tmp_path: Path, samples: Complex) -> None:
    path = tmp_path / "mono.flac"
    sf.write(path, 0.4 * np.real(samples) / np.abs(samples).max(), 48_000, subtype="PCM_16")
    reason = label_cap_reason(read_audio(path))
    assert reason is not None and "no quadrature" in reason


def test_lossy_audio_is_capped(tmp_path: Path) -> None:
    path = tmp_path / "x.ogg"
    sf.write(path, 0.5 * np.sin(2 * np.pi * 1000 / 48_000 * np.arange(48_000)), 48_000,
             format="OGG", subtype="VORBIS")  # fmt: skip
    reason = label_cap_reason(read_audio(path))
    assert reason is not None and "Lossy" in reason


def test_a_digital_signal_in_a_real_recording_reports_nothing_firmer_than_hypothesis(
    tmp_path: Path, samples: Complex
) -> None:
    path = tmp_path / "mono.wav"
    sf.write(path, 0.4 * np.real(samples) / np.abs(samples).max(), 1_000_000, subtype="PCM_16")
    (opened,) = open_path(path)
    source = opened.recording
    with source.reader() as reader:
        detections = detect(reader, real=True).detections
    assert detections
    report = analyse_detection(source, detections[0], sample_rate=1e6)
    assert report.kind in ("psk", "fsk")
    assert report.level is EvidenceLevel.HYPOTHESIS
    for stage in report.stages:
        if stage.id != "detect":
            assert all(
                p.level in (EvidenceLevel.HYPOTHESIS, EvidenceLevel.UNKNOWN)
                for p in stage.parameters
            )
