"""Recordings of known content for the backend tests: a QPSK signal at a known offset."""

import math
import wave
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from dsp.ingest.formats import SampleFormat
from dsp.synth.bits import FrameSpec, to_bytes
from dsp.synth.chain import Scene, SignalSpec, generate, write_sigmf

RATE = 1e6
OFFSET = 0.2  # of the sample rate: the signal's ground-truth centre
CI16 = SampleFormat.parse("ci16_le")

Complex = NDArray[np.complex128]
WriteWav = Callable[..., Path]
WriteRawBpsk = Callable[..., Path]


def scene() -> Scene:
    spec = SignalSpec("qpsk", sps=8.0, frame=None, offset=OFFSET, power_db=0.0)
    return Scene(1 << 16, (spec,), noise_db=-20.0, sample_rate=RATE, center_frequency=1e8)


@pytest.fixture
def samples() -> Complex:
    """The QPSK scene's samples: one signal at +0.2 of the sample rate, 8 samples per symbol."""
    return np.asarray(generate(scene(), seed=1).samples, dtype=np.complex128)


@pytest.fixture
def sigmf_path(tmp_path: Path) -> Path:
    """The same samples as a SigMF recording that states its sample rate and centre frequency."""
    return write_sigmf(tmp_path / "rec", generate(scene(), seed=1), scene(), "cf32_le")


@pytest.fixture
def write_wav() -> WriteWav:
    """A stereo 16-bit WAV (I left, Q right) that states its sample rate. `peak` is the value
    that maps to half of full scale (default: the samples' own), so the parts of one recording
    can be scaled alike."""

    def write(path: Path, x: Complex, rate: int = int(RATE), peak: float | None = None) -> Path:
        scaled = 0.5 * x / (peak or np.max(np.abs(x)))
        with wave.open(str(path), "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(CI16.encode(scaled))
        return path

    return write


FRAME = FrameSpec()


def framed_scene() -> Scene:
    """CRC-framed QPSK at 15 dB Es/N0: the chain decodes it to VERIFIED frames."""
    power = -20.0 + 15.0 - 10 * math.log10(8)
    spec = SignalSpec("qpsk", sps=8.0, frame=FRAME, offset=OFFSET, power_db=power)
    return Scene(1 << 17, (spec,), noise_db=-20.0, sample_rate=RATE, center_frequency=1e8)


@pytest.fixture
def framed_path(tmp_path: Path) -> Path:
    return write_sigmf(
        tmp_path / "framed", generate(framed_scene(), seed=7), framed_scene(), "cf32_le"
    )


@pytest.fixture
def transmitted() -> set[str]:
    """Hex of every transmitted frame between its sync word and its CRC (the report's payload)."""
    g = generate(framed_scene(), seed=7)
    rows = g.signals[0].framed.reshape(-1, FRAME.length)
    return {to_bytes(r[len(FRAME.sync_bits) : -16]).hex().upper() for r in rows}


@pytest.fixture
def write_raw_bpsk() -> WriteRawBpsk:
    """A raw 8-bit capture of BPSK at `baud` sampled at `rate`: a file that states no rate."""

    def write(path: Path, *, baud: float, rate: float, swapped: bool = False) -> Path:
        sps = int(rate / baud)
        spec = SignalSpec(
            "bpsk", sps=sps, frame=None, offset=0.1, power_db=-5 - 10 * math.log10(sps)
        )
        x = generate(Scene(1 << 20, (spec,), noise_db=-20.0), seed=5).samples
        x = np.conj(x) if swapped else x  # Q first: the spectrum is mirrored
        path.write_bytes(SampleFormat.parse("cu8").encode(0.5 * x / np.max(np.abs(x))))
        return path

    return write
