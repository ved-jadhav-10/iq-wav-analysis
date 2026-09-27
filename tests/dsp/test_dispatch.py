"""The reader dispatcher: picks the right reader from a file's header and name."""

from pathlib import Path

import numpy as np
import pytest

from dsp.ingest.dispatch import NeedsDecompression, open_path
from dsp.ingest.formats import SampleFormat
from dsp.synth.chain import Scene, SignalSpec, generate, write_sigmf


def test_sigmf_meta_is_opened_as_sigmf(tmp_path: Path) -> None:
    g = generate(Scene(2048, (SignalSpec("qpsk", frame=None),), sample_rate=1000.0), seed=1)
    stem = tmp_path / "rec"
    write_sigmf(stem, g, Scene(2048, (), sample_rate=1000.0), "cf32_le")
    (opened,) = open_path(stem.with_suffix(".sigmf-meta"))
    assert opened.container == "SigMF"
    assert opened.recording.assumptions.datatype.value == "cf32_le"


def test_wav_header_is_opened_as_wav(tmp_path: Path) -> None:
    import wave

    path = tmp_path / "audio.wav"
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(8000)
        f.writeframes((np.zeros(100, np.int16)).tobytes())
    (opened,) = open_path(path)
    assert opened.container == "WAV"


def test_npy_header_is_opened_as_npy(tmp_path: Path) -> None:
    path = tmp_path / "samples.npy"
    np.save(path, np.zeros(10, np.complex64))
    (opened,) = open_path(path)
    assert opened.container == "NumPy .npy"


def test_unrecognised_file_falls_back_to_raw_and_the_sniffer(tmp_path: Path) -> None:
    path = tmp_path / "capture.bin"
    fmt = SampleFormat.parse("cf32_le")
    path.write_bytes(fmt.encode(np.exp(2j * np.pi * 0.1 * np.arange(4000))))
    (opened,) = open_path(path)
    assert opened.container == "Raw samples (format sniffer)"
    assert opened.recording.sample_format is not None


def test_compressed_files_are_refused_with_a_clear_reason(tmp_path: Path) -> None:
    path = tmp_path / "capture.raw.gz"
    path.write_bytes(b"\x1f\x8b\x00\x00")
    with pytest.raises(NeedsDecompression, match="decompress"):
        open_path(path)


def test_real_or_complex_tie_names_the_other_reading(tmp_path: Path) -> None:
    """A raw file the sniffer can't tell complex from real names the other reading, so the
    caller can carry both forward (PLAN M2 "Real/complex ties")."""
    path = tmp_path / "ambiguous.bin"
    rng = np.random.default_rng(0)
    path.write_bytes(rng.integers(0, 256, 4000, dtype=np.uint8).tobytes())
    (opened,) = open_path(path)
    tie = opened.real_or_complex_tie
    if tie is not None:
        value = opened.recording.assumptions.datatype.value
        assert isinstance(value, str)
        assert tie[0] != value[0]
