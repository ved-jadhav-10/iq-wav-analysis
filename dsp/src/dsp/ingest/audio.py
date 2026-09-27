"""Compressed audio (FLAC, MP3, Ogg Vorbis/Opus), decoded chunk by chunk through libsndfile.

The stream header states the sample rate, channel count and, for FLAC, the PCM precision, so
those are MEASURED. Samples come from the decoder, not from byte offsets, so this reader
decodes on demand rather than reading byte segments; it offers the same chunked interface.
Stereo files get the same quadrature check as WAV.

Lossy codecs (MP3, Vorbis, Opus) discard what the ear won't miss, including phase detail that
digital demodulation needs: the datatype carries a warning, and `lossy` tells later stages to
cap digital labels at HYPOTHESIS. FLAC is lossless.

Limits: MP3 decoders can pad the start and end of a stream, so sample positions near the ends
may be offset by up to a frame (1152 samples). No centre frequency is recorded; it comes from
file-name candidates.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

import numpy as np
import soundfile as sf  # pyright: ignore[reportMissingTypeStubs]
from numpy.typing import NDArray

from dsp.evidence import EvidenceLevel, Parameter
from dsp.ingest.assumptions import iq_order
from dsp.ingest.formats import SampleFormat
from dsp.ingest.rate import center_frequency_parameter
from dsp.ingest.reader import DEFAULT_CHUNK
from dsp.ingest.recording import stated, unknown
from dsp.ingest.wav import QuadratureCheck, quadrature_check, stereo_datatype
from dsp.results import Assumptions

CONTAINERS = ("FLAC", "MP3", "OGG")
_LOSSY = {"MPEG_LAYER_III", "MPEG_LAYER_II", "MPEG_LAYER_I", "VORBIS", "OPUS"}
# Decoded precision by libsndfile subtype; lossy codecs decode to float.
_PRECISION = {
    "PCM_S8": ("i", 8),
    "PCM_U8": ("u", 8),
    "PCM_16": ("i", 16),
    "PCM_24": ("i", 24),
    "PCM_32": ("i", 32),
    "FLOAT": ("f", 32),
    "DOUBLE": ("f", 64),
}


class AudioReader:
    """Decodes frames on demand: float32 for mono, complex64 (left + j·right) for stereo."""

    def __init__(self, path: Path, *, swap_iq: bool = False) -> None:
        self._file = sf.SoundFile(str(path))
        self.channels = self._file.channels
        self.swap_iq = swap_iq
        self.num_samples = int(self._file.frames)

    def read(self, start: int, count: int) -> NDArray[Any]:
        if start < 0 or count < 0:
            raise ValueError("start and count must be non-negative")
        count = max(0, min(count, self.num_samples - start))
        if count == 0:
            dtype = np.complex64 if self.channels == 2 else np.float32
            return np.zeros(0, dtype=dtype)
        self._file.seek(start)
        frames = np.asarray(self._file.read(count, dtype="float32", always_2d=True), np.float32)
        if self.channels == 1:
            return frames[:, 0]
        i, q = (frames[:, 1], frames[:, 0]) if self.swap_iq else (frames[:, 0], frames[:, 1])
        return (i + 1j * q).astype(np.complex64)

    def chunks(self, size: int = DEFAULT_CHUNK) -> Iterator[NDArray[Any]]:
        for start in range(0, self.num_samples, size):
            yield self.read(start, size)

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


@dataclass(frozen=True)
class AudioRecording:
    path: Path
    container: str
    subtype: str
    channels: int
    lossy: bool
    datatype: Parameter
    sample_rate: Parameter
    quadrature: QuadratureCheck | None

    @property
    def sample_format(self) -> SampleFormat | None:
        value = self.datatype.value
        return SampleFormat.parse(value) if isinstance(value, str) else None

    def reader(self, *, swap_iq: bool = False) -> AudioReader:
        if self.sample_format is None:
            raise ValueError("the sample format is UNKNOWN; settle it before reading samples")
        return AudioReader(self.path, swap_iq=swap_iq)

    @property
    def assumptions(self) -> Assumptions:
        return Assumptions(
            datatype=self.datatype,
            data_offset=Parameter(
                id="data_offset",
                name="Data offset",
                value=0,
                unit="frames",
                level=EvidenceLevel.MEASURED,
                method=f"{self.container} decoder: samples start at its first frame",
            ),
            sample_rate=self.sample_rate,
            center_frequency=center_frequency_parameter(
                self.path.name,
                "Centre-frequency candidates: file name",
                f"A {self.container} file doesn't record a centre frequency.",
            ),
            iq_order=iq_order(
                self.sample_format,
                "Convention for stereo I/Q audio: I on the left channel",
                convention="SDR software records I on the left channel and Q on the right, but "
                "the file doesn't say. Swap if a known carrier sits on the wrong side of the "
                "spectrum.",
            ),
        )


def read_audio(path: Path) -> AudioRecording:
    try:
        info = sf.info(str(path))
    except (sf.LibsndfileError, RuntimeError) as error:
        raise ValueError(f"{path.name} can't be decoded as audio: {error}") from error
    if info.format not in CONTAINERS:
        raise ValueError(f"{path.name} is {info.format}, not compressed audio (FLAC, MP3, Ogg)")
    method = f"{info.format} stream header (decoded by libsndfile)"
    lossy = info.subtype in _LOSSY
    facts = (
        f"{info.format} {info.subtype}: {info.channels} channel(s), {info.samplerate:,} samples/s, "
        f"{info.frames:,} frames."
    )
    warnings = (
        (
            f"{info.subtype} is lossy: it distorts the phase that digital demodulation relies "
            "on, so digital labels from this recording are capped at HYPOTHESIS.",
        )
        if lossy
        else ()
    )
    kind, bits = _PRECISION.get(info.subtype, ("f", 32))
    if info.subtype not in _PRECISION:
        facts += " It stores no PCM precision; the decoder produces 32-bit floats."
    endian = "" if bits == 8 else "_le"
    quadrature = None
    if info.channels == 1:
        datatype = stated(
            "datatype",
            f"r{kind}{bits}{endian}",
            method,
            evidence=(facts, "One channel: real-valued samples."),
            warnings=warnings,
        )
    elif info.channels == 2:
        fmt = SampleFormat.parse(f"c{kind}{bits}{endian}")
        with AudioReader(path) as reader:
            quadrature = quadrature_check(reader)
        datatype = stereo_datatype(fmt, quadrature, facts, method, warnings)
    else:
        datatype = unknown(
            "datatype",
            method,
            f"{facts} Sanket reads mono (real) or stereo (I/Q).",
            "Extract one channel, or the two that carry I and Q, into a mono or stereo file.",
        )
    return AudioRecording(
        path=path,
        container=info.format,
        subtype=info.subtype,
        channels=info.channels,
        lossy=lossy,
        datatype=datatype,
        sample_rate=stated("sample_rate", float(info.samplerate), method),
        quadrature=quadrature,
    )
