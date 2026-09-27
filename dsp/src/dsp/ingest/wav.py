"""WAV recordings: RIFF, RIFX, RF64/BW64 and Sony Wave64 containers, read chunk by chunk.

The header states the sample rate, channel count and sample encoding, so those are MEASURED:
integer PCM (8-bit unsigned; 16-, 24- and 32-bit signed) and IEEE float (32, 64 bits), plain or
WAVE_FORMAT_EXTENSIBLE. The `auxi` chunk that SpectraVue, Winrad, HDSDR, SDR# and SDRuno write
gives the centre frequency and start time, also MEASURED; it may sit before or after the data.

A mono file is real-valued. A stereo file is either I/Q or two audio channels, and the header
doesn't say which, so the quadrature check looks at the samples. Read as left + j·right, I/Q is
a proper complex signal: its mirror frequencies are uncorrelated, and unless it is centred its
spectrum is asymmetric. Two audio channels of one sound correlate their mirror frequencies,
whatever the delay between them. A significant asymmetry is proposed as I/Q; improper,
identical or silent channels leave the format UNKNOWN for the analyst; anything else is I/Q by
a stated convention, listed for review.

Limits: compressed encodings (ADPCM, A-law, mu-law) and more than two channels are reported
UNKNOWN, not decoded. A data chunk whose stated size overruns the file is clamped to the file,
with a warning. Two unrelated audio channels are proper too, and are told apart from I/Q only
by the symmetry of their spectrum. I/Q that is itself improper (BPSK exactly at 0 Hz) or has
image rejection worse than about 18 dB looks like audio, and is left to the analyst.
"""

import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Literal, cast

import numpy as np
from numpy.typing import NDArray

from dsp.evidence import Alternative, EvidenceLevel, Parameter
from dsp.ingest.assumptions import iq_order
from dsp.ingest.formats import SampleFormat
from dsp.ingest.rate import center_frequency_parameter, rate_candidates, sample_rate_parameter
from dsp.ingest.reader import SampleReader
from dsp.results import Assumptions

Container = Literal["RIFF", "RIFX", "RF64", "BW64", "Wave64"]

W64_RIFF = bytes.fromhex("72696666 2e91cf11 a5d628db 04c10000".replace(" ", ""))
_W64_TAIL = bytes.fromhex("f3acd311 8cd100c0 4f8edb8a".replace(" ", ""))
W64_WAVE = b"wave" + _W64_TAIL
_W64_FMT = b"fmt " + _W64_TAIL
_W64_DATA = b"data" + _W64_TAIL
_EXTENSIBLE_TAIL = bytes.fromhex("0000 0000 1000 8000 00aa 0038 9b71".replace(" ", ""))
_PCM, _FLOAT, _EXTENSIBLE = 0x0001, 0x0003, 0xFFFE
_TAG_NAMES = {
    0x0002: "Microsoft ADPCM",
    0x0006: "A-law",
    0x0007: "mu-law",
    0x0011: "IMA ADPCM",
    _EXTENSIBLE: "an unrecognised WAVE_FORMAT_EXTENSIBLE sub-format",
}
_UNSET = 0xFFFFFFFF
# fmt and auxi bodies are tens of bytes; a larger stated size is corruption, not data to load.
_MAX_META = 1 << 16

# Quadrature check: frames read per block, blocks spread across the file, FFT size.
CHECK_FRAMES = 1 << 16
CHECK_BLOCKS = 4
CHECK_NFFT = 1024
# Impropriety above this looks like two audio channels, not I/Q: an I/Q recording reaches it
# only with image rejection worse than about 18 dB (2e/(1 + e^2) for image amplitude e).
AUDIO_IMPROPRIETY = 0.25
# A channel this much weaker than the other is taken as silent.
SILENT_DB = 40.0
# Spectral asymmetry must exceed its null mean by this many null standard deviations.
ASYMMETRY_Z = 6.0


class WavError(ValueError):
    """The file is not a readable WAV container."""


@dataclass(frozen=True)
class Auxi:
    """The SpectraVue `auxi` chunk; times are as written, with no time zone."""

    start_time: str | None
    stop_time: str | None
    center_frequency: int  # Hz
    ad_frequency: int  # A/D rate before any decimation, Hz
    if_frequency: int  # Hz, when an external down-converter is used
    bandwidth: int  # Hz


@dataclass(frozen=True)
class WavHeader:
    container: Container
    format_tag: int  # after resolving WAVE_FORMAT_EXTENSIBLE
    extensible: bool
    channels: int
    sample_rate: int
    bits: int  # container bits per sample
    valid_bits: int | None  # WAVE_FORMAT_EXTENSIBLE only
    block_align: int
    data_offset: int
    data_bytes: int
    auxi: Auxi | None
    warnings: tuple[str, ...]

    @property
    def encoding(self) -> str:
        if self.format_tag == _PCM:
            return f"{self.bits}-bit integer PCM"
        if self.format_tag == _FLOAT:
            return f"{self.bits}-bit float"
        return _TAG_NAMES.get(self.format_tag, f"format tag 0x{self.format_tag:04x}")

    @property
    def sample_format(self) -> SampleFormat | None:
        """The format of one frame, or None if Sanket can't decode this encoding."""
        if self.channels not in (1, 2) or self.block_align != self.channels * self.bits // 8:
            return None
        if self.format_tag == _PCM and self.bits in (8, 16, 24, 32):
            kind = "u" if self.bits == 8 else "i"
        elif self.format_tag == _FLOAT and self.bits in (32, 64):
            kind = "f"
        else:
            return None
        endian = "" if self.bits == 8 else ("_be" if self.container == "RIFX" else "_le")
        return SampleFormat.parse(f"{'c' if self.channels == 2 else 'r'}{kind}{self.bits}{endian}")


def read_header(path: Path) -> WavHeader:
    """Walk the chunks without loading the data; raise WavError if the container is broken."""
    size = path.stat().st_size
    with path.open("rb") as file:
        head = file.read(40)
        if head[:4] in (b"RIFF", b"RIFX", b"RF64", b"BW64") and head[8:12] == b"WAVE":
            return _walk_riff(file, size, cast(Container, head[:4].decode("ascii")))
        if head[:16] == W64_RIFF and head[24:40] == W64_WAVE:
            return _walk_w64(file, size)
    raise WavError(f"{path.name} is not a WAV file")


@dataclass
class _Found:
    fmt: bytes | None = None
    data: tuple[int, int] | None = None  # offset, stated size
    auxi: bytes | None = None


def _walk_riff(file: BinaryIO, size: int, container: Container) -> WavHeader:
    order = ">" if container == "RIFX" else "<"
    found, warnings = _Found(), cast(list[str], [])
    ds64_data: int | None = None
    pos = 12
    while pos + 8 <= size:
        file.seek(pos)
        cid, csize = struct.unpack(order + "4sI", file.read(8))
        body = pos + 8
        if cid == b"ds64" and container in ("RF64", "BW64"):
            payload = file.read(min(csize, 28))
            if len(payload) < 24:
                raise WavError("the RF64 ds64 chunk is too short")
            _, ds64_data, _ = struct.unpack("<QQQ", payload[:24])
        if cid == b"data" and found.data is None:
            stated = ds64_data if csize == _UNSET and ds64_data is not None else csize
            found.data = (body, stated)
            if stated in (0, _UNSET):
                break  # a streaming writer's placeholder: the data runs to the end
            csize = stated
        elif cid == b"fmt " and found.fmt is None:
            found.fmt = file.read(min(csize, _MAX_META))
        elif cid == b"auxi" and found.auxi is None:
            found.auxi = file.read(min(csize, _MAX_META))
        pos = body + csize + (csize & 1)
    return _header(container, found, size, order, warnings)


def _walk_w64(file: BinaryIO, size: int) -> WavHeader:
    found, pos = _Found(), 40
    while pos + 24 <= size:
        file.seek(pos)
        guid, csize = struct.unpack("<16sQ", file.read(24))
        if csize < 24:
            raise WavError(f"a Wave64 chunk at byte {pos} states an impossible size ({csize})")
        if guid == _W64_DATA and found.data is None:
            found.data = (pos + 24, csize - 24)
        elif guid == _W64_FMT and found.fmt is None:
            found.fmt = file.read(min(csize - 24, _MAX_META))
        elif guid[:4] == b"auxi" and found.auxi is None:
            found.auxi = file.read(min(csize - 24, _MAX_META))
        pos += (csize + 7) // 8 * 8
    return _header("Wave64", found, size, "<", [])


def _header(
    container: Container, found: _Found, size: int, order: str, warnings: list[str]
) -> WavHeader:
    if found.fmt is None or len(found.fmt) < 16:
        raise WavError("the WAV file has no complete fmt chunk")
    if found.data is None:
        raise WavError("the WAV file has no data chunk")
    tag, channels, rate, _, block_align, bits = struct.unpack(order + "HHIIHH", found.fmt[:16])
    extensible, valid_bits = False, None
    if tag == _EXTENSIBLE:
        if len(found.fmt) < 40:
            raise WavError("the WAVE_FORMAT_EXTENSIBLE fmt chunk is too short")
        extensible = True
        valid_bits = struct.unpack(order + "H", found.fmt[18:20])[0]
        sub = found.fmt[24:40]
        if sub[2:] == _EXTENSIBLE_TAIL:
            tag = struct.unpack(order + "H", sub[:2])[0]
        if valid_bits and valid_bits < bits:
            warnings.append(
                f"Only {valid_bits} of each sample's {bits} bits are valid; the rest are padding."
            )
    offset, stated = found.data
    available = size - offset
    if stated == _UNSET or (stated == 0 and available > 0):
        warnings.append(
            f"The data chunk doesn't state its size ({stated}); the samples are taken to run to "
            "the end of the file, as when a recorder stops without finishing the header."
        )
        stated = available
    elif stated > available:
        warnings.append(
            f"The data chunk states {stated} bytes but the file holds only {available} after its "
            "header: the recording is truncated, and only the bytes present are read."
        )
        stated = available
    if block_align and stated % block_align:
        warnings.append(
            f"The data ends with {stated % block_align} byte(s) that don't form a whole frame."
        )
    return WavHeader(
        container=container,
        format_tag=tag,
        extensible=extensible,
        channels=channels,
        sample_rate=rate,
        bits=bits,
        valid_bits=valid_bits,
        block_align=block_align,
        data_offset=offset,
        data_bytes=stated,
        auxi=_auxi(found.auxi, order) if found.auxi else None,
        warnings=tuple(warnings),
    )


def _auxi(body: bytes, order: str) -> Auxi | None:
    if len(body) < 48:
        return None
    start = struct.unpack(order + "8H", body[0:16])
    stop = struct.unpack(order + "8H", body[16:32])
    center, ad, if_, bandwidth = struct.unpack(order + "4I", body[32:48])
    return Auxi(_systemtime(start), _systemtime(stop), center, ad, if_, bandwidth)


def _systemtime(t: tuple[int, ...]) -> str | None:
    year, month, _, day, hour, minute, second, ms = t
    if not (1980 <= year <= 9999 and 1 <= month <= 12 and 1 <= day <= 31):
        return None
    if hour > 23 or minute > 59 or second > 59 or ms > 999:
        return None
    return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}.{ms:03d}"


Verdict = Literal["iq", "audio", "inconclusive"]


@dataclass(frozen=True)
class QuadratureCheck:
    """Whether a stereo file's channels behave like I and Q."""

    verdict: Verdict
    correlation: float  # zero-lag Pearson correlation of the two channels
    power_ratio_db: float  # left over right
    impropriety: float  # circularity coefficient: sum |E[X(f)X(-f)]| over mean mirror power
    asymmetry: float  # mean squared log power ratio of +f to -f, over its null mean
    threshold: float  # the asymmetry that counts as significant
    identical: bool
    frames: int

    @property
    def evidence(self) -> tuple[str, ...]:
        head = f"Quadrature check on {self.frames:,} frames sampled across the file: "
        if self.identical:
            return (
                head + "the two channels are identical, as when a mono signal is stored twice.",
            )
        return (
            head + f"channel correlation {self.correlation:+.3f}, left/right power "
            f"{self.power_ratio_db:+.1f} dB.",
            f"Impropriety of left + j·right {self.impropriety:.3f} (I/Q is near 0, two audio "
            f"channels near 1; above {AUDIO_IMPROPRIETY} looks like audio).",
            f"Spectral asymmetry {self.asymmetry:.2f} times what a symmetric spectrum gives "
            f"(significant above {self.threshold:.2f}).",
        )


def quadrature_check(reader: SampleReader) -> QuadratureCheck:
    """Run the quadrature check on a few blocks spread across a stereo recording."""
    n = reader.num_samples
    starts = (
        [0]
        if n <= CHECK_FRAMES
        else [int(i * (n - CHECK_FRAMES) / (CHECK_BLOCKS - 1)) for i in range(CHECK_BLOCKS)]
    )
    x = np.concatenate([reader.read(s, CHECK_FRAMES) for s in starts]).astype(np.complex128)
    x -= x.mean()
    left, right = x.real, x.imag
    pl, pr = float(np.mean(left**2)), float(np.mean(right**2))
    identical = bool(np.array_equal(left, right))
    ratio = 10 * math.log10(pl / pr) if pl > 0 and pr > 0 else (math.inf if pl else -math.inf)
    corr = float(np.mean(left * right) / math.sqrt(pl * pr)) if pl > 0 and pr > 0 else 0.0
    impropriety, asymmetry, threshold = _spectral(x)
    if identical or abs(ratio) > SILENT_DB or impropriety > AUDIO_IMPROPRIETY:
        verdict: Verdict = "audio"
    elif asymmetry > threshold:
        verdict = "iq"
    else:
        verdict = "inconclusive"
    return QuadratureCheck(
        verdict, corr, ratio, impropriety, asymmetry, threshold, identical, len(x)
    )


def _spectral(x: NDArray[Any]) -> tuple[float, float, float]:
    """Impropriety, spectral asymmetry over its null mean, and the asymmetry threshold.

    Mirror bins X(f), X(-f) of an I/Q signal are uncorrelated (it is proper), so the averaged
    complementary spectrum X(f)X(-f) is near zero; two real audio channels make it as large as
    the power, whatever their delay. With K independent Hann segments averaged, each bin's power
    is Gamma(K) under a Gaussian symmetric null, so the log ratio of mirror bins has variance
    2 psi'(K). Neighbouring bins overlap, so the threshold counts a third as many pairs.
    """
    segments = x[: len(x) // CHECK_NFFT * CHECK_NFFT].reshape(-1, CHECK_NFFT)
    k = len(segments)
    if k < 8:
        return 0.0, 0.0, math.inf
    spectra = np.fft.fft(segments * np.hanning(CHECK_NFFT), axis=1)
    half = CHECK_NFFT // 2
    pos_x, neg_x = spectra[:, 1:half], spectra[:, CHECK_NFFT - 1 : half : -1]
    pos, neg = np.mean(np.abs(pos_x) ** 2, axis=0), np.mean(np.abs(neg_x) ** 2, axis=0)
    keep = (pos > 0) & (neg > 0)
    if not keep.any():
        return 0.0, 0.0, math.inf
    complementary = np.abs(np.mean(pos_x * neg_x, axis=0))[keep]
    impropriety = float(complementary.sum() / ((pos[keep] + neg[keep]) / 2).sum())
    null_var = 2 * (1 / k + 1 / (2 * k**2) + 1 / (6 * k**3))  # 2 psi'(K), asymptotic series
    asymmetry = float(np.mean(np.log(pos[keep] / neg[keep]) ** 2)) / null_var
    independent = max(1, int(keep.sum()) // 3)
    return impropriety, asymmetry, 1 + ASYMMETRY_Z * math.sqrt(2 / independent)


@dataclass(frozen=True)
class WavRecording:
    data_path: Path
    header: WavHeader
    datatype: Parameter
    quadrature: QuadratureCheck | None
    start_time: Parameter | None  # from the auxi chunk

    @property
    def sample_format(self) -> SampleFormat | None:
        value = self.datatype.value
        return SampleFormat.parse(value) if isinstance(value, str) else None

    def reader(self, *, swap_iq: bool = False) -> SampleReader:
        """Chunked reads of the samples; the datatype must be settled first."""
        fmt = self.sample_format
        if fmt is None:
            raise ValueError("the sample format is UNKNOWN; settle it before reading samples")
        return _reader(self.data_path, self.header, fmt, swap_iq)

    @property
    def assumptions(self) -> Assumptions:
        h = self.header
        fmt = self.sample_format
        method = f"{h.container} WAV fmt chunk"
        if h.sample_rate > 0:
            rate = Parameter(
                id="sample_rate",
                name="Sample rate",
                value=float(h.sample_rate),
                unit="S/s",
                level=EvidenceLevel.MEASURED,
                method=f"{method}: samples per second",
            )
        else:
            rate = sample_rate_parameter(
                rate_candidates(self.data_path.name, fmt.datatype if fmt else None),
                fmt.datatype if fmt else None,
                "Sample-rate candidates: file name and standard SDR device rates",
                "The WAV header states a sample rate of 0.",
            )
        if h.auxi is not None:
            a = h.auxi
            center = Parameter(
                id="center_frequency",
                name="Centre frequency",
                value=float(a.center_frequency),
                unit="Hz",
                level=EvidenceLevel.MEASURED,
                method="auxi chunk (SpectraVue, HDSDR, SDR#, SDRuno)",
                evidence=(
                    f"The auxi chunk also states an A/D rate of {a.ad_frequency:,} Hz, an IF of "
                    f"{a.if_frequency:,} Hz and a bandwidth of {a.bandwidth:,} Hz.",
                ),
            )
        else:
            center = center_frequency_parameter(
                self.data_path.name,
                "Centre-frequency candidates: file name",
                "The WAV file has no auxi chunk, so it doesn't record a centre frequency.",
            )
        return Assumptions(
            datatype=self.datatype,
            data_offset=Parameter(
                id="data_offset",
                name="Data offset",
                value=h.data_offset,
                unit="B",
                level=EvidenceLevel.MEASURED,
                method=f"{h.container} data chunk",
            ),
            sample_rate=rate,
            center_frequency=center,
            iq_order=iq_order(
                fmt,
                "Convention for stereo I/Q WAV: I on the left channel",
                convention="SDR software records I on the left channel and Q on the right, but "
                "the file doesn't say. Swap if a known carrier sits on the wrong side of the "
                "spectrum.",
            ),
        )


def read_wav(path: Path) -> WavRecording:
    header = read_header(path)
    quadrature = None
    fmt = header.sample_format
    facts = (
        f"{header.container} WAV fmt chunk: {header.channels} channel(s), {header.encoding}"
        f"{' (WAVE_FORMAT_EXTENSIBLE)' if header.extensible else ''}, "
        f"{header.sample_rate:,} samples/s."
    )
    method = f"{header.container} WAV fmt chunk"
    if fmt is None:
        datatype = _unsupported(header, facts, method)
    elif not fmt.is_complex:
        datatype = Parameter(
            id="datatype",
            name="Sample format",
            value=fmt.datatype,
            level=EvidenceLevel.MEASURED,
            method=method,
            evidence=(facts, "One channel: real-valued samples."),
            warnings=header.warnings,
        )
    else:
        with _reader(path, header, fmt, False) as reader:
            quadrature = quadrature_check(reader)
        datatype = _stereo(fmt, quadrature, header, facts)
    start = None
    if header.auxi is not None and header.auxi.start_time is not None:
        start = Parameter(
            id="start_time",
            name="Start time",
            value=header.auxi.start_time,
            level=EvidenceLevel.MEASURED,
            method="auxi chunk (SpectraVue, HDSDR, SDR#, SDRuno)",
            warnings=("The auxi chunk doesn't record a time zone.",),
        )
    return WavRecording(path, header, datatype, quadrature, start)


def _reader(path: Path, header: WavHeader, fmt: SampleFormat, swap_iq: bool) -> SampleReader:
    return SampleReader(
        path,
        fmt,
        offset_bytes=header.data_offset,
        length_bytes=header.data_bytes,
        swap_iq=swap_iq,
    )


def _unsupported(header: WavHeader, facts: str, method: str) -> Parameter:
    if header.channels not in (1, 2):
        why = f"The file has {header.channels} channels; Sanket reads mono (real) or stereo (I/Q)."
        hint = "Extract one channel, or the two that carry I and Q, into a mono or stereo file."
    elif header.format_tag not in (_PCM, _FLOAT):
        why = f"The samples are {header.encoding}, which Sanket doesn't decode."
        hint = "Convert the recording to integer or float PCM."
    else:
        why = (
            f"The fmt chunk's {header.encoding} with a {header.block_align}-byte frame isn't a "
            "consistent PCM layout."
        )
        hint = "Convert the recording to 8-, 16-, 24- or 32-bit integer or float PCM."
    return Parameter(
        id="datatype",
        name="Sample format",
        value=None,
        level=EvidenceLevel.UNKNOWN,
        method=method,
        evidence=(facts, why),
        resolve_hint=hint,
    )


def _stereo(fmt: SampleFormat, check: QuadratureCheck, header: WavHeader, facts: str) -> Parameter:
    method = "WAV fmt chunk and quadrature check"
    real = SampleFormat(False, fmt.kind, fmt.bits, fmt.endian).datatype
    if check.verdict == "audio":
        why = "The two channels look like stereo audio, not I and Q: " + (
            "they are identical."
            if check.identical
            else "one is silent."
            if abs(check.power_ratio_db) > SILENT_DB
            else f"their mirror frequencies are correlated (impropriety {check.impropriety:.2f}), "
            "as in two recordings of one sound; in I/Q they are independent."
        )
        return Parameter(
            id="datatype",
            name="Sample format",
            value=None,
            level=EvidenceLevel.UNKNOWN,
            method=method,
            evidence=(facts, *check.evidence, why),
            alternatives=(Alternative(value=fmt.datatype),),
            warnings=header.warnings,
            resolve_hint=f"Confirm whether the channels carry I and Q (the format is then "
            f"{fmt.datatype}) or audio; for audio, save one channel as a mono {real} file.",
        )
    convention = None
    if check.verdict == "inconclusive":
        convention = (
            "The channels are uncorrelated but the spectrum is symmetric, so the samples can't "
            "tell I/Q from two independent channels. I/Q is proposed because stereo recordings "
            "from SDR software are I/Q; if the channels are separate signals, save one as a "
            "mono file."
        )
    return Parameter(
        id="datatype",
        name="Sample format",
        value=fmt.datatype,
        level=EvidenceLevel.HYPOTHESIS,
        method=method,
        evidence=(facts, *check.evidence, "Two channels read as I and Q."),
        warnings=header.warnings,
        convention=convention,
    )
