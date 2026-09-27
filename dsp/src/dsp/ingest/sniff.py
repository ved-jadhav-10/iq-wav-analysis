"""Propose the sample format of a raw file that has no metadata, ranked, never picked silently.

Every SigMF datatype is scored by how compactly it explains the bytes. The file is read as that
format, an order-8 linear predictor is fitted, and the prediction residual gives an estimated
code length in bits per byte: an integer component costs the entropy of its residual in LSBs; a
float component costs its sign, the entropy of its exponents and the mantissa bits the predictor
leaves unexplained, and NaN, infinite or denormal values cost their full width. The right reading
leaves the least unexplained. A wrong byte order, width or signedness scrambles bits and looks
close to random (8 bits/byte), and reading two narrow components as one wide one pays for the
channel the predictor can't follow.

Complex and real readings of the same components hold the same numbers, so they are compared on
prediction gain: how many bits per component the complex predictor saves over the real one. The
decision is asymmetric. Complex needs only a small gain. Real needs a large one and no sign of
pairs (`period2`), because improper I/Q (BPSK, repeated bits, idle patterns: components of
unequal size or moving together) also favours the real reading, by up to ~0.3 bits on the
bench, while real signals won by ~0.4. Anything in between is complex by a stated convention,
listed for review, never real by default.

Limits: noise, and real signals read as I/Q pairs, fit the complex and real readings equally
well; complex is then proposed by a stated convention. So are weakly structured real signals,
which the asymmetric margin can't separate from improper I/Q. IQ versus QI order only mirrors the
spectrum and is not scored. The data is assumed to start at byte 0 unless a known header is
found. The code lengths are model estimates for ranking, not the output of a real compressor.

A recorder's file extension (`.cu8`, `.cs16`, `.cfile`, ...) is only a hint: it orders the
candidates of an UNKNOWN tie, hinted format first, and is warned about when it disagrees with the
proposal. It never decides a format, raises a level or breaks a tie.
"""

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Literal

import numpy as np
from numpy.typing import NDArray

from dsp.evidence import Alternative, EvidenceLevel, Parameter
from dsp.ingest.assumptions import FORMAT_HINT
from dsp.ingest.formats import ALL_DATATYPES, SampleFormat
from dsp.ingest.wav import W64_RIFF, W64_WAVE

ORDER = 8
BLOCK_BYTES = 1 << 16
BLOCKS = 4
# Tie margins, set from the bench (bench/results/sniffer.md). Between formats whose components
# differ, in bits/byte: wrong readings came within ~0.02 of the truth. Between the real and
# complex readings of the same components, in bits of prediction gain per component: the wrong
# layout never won by more than ~0.01.
TIE_MARGIN = 0.05
LAYOUT_MARGIN = 0.02
# Deciding real takes more (bench v0 null set): improper complex signals favoured the real
# reading by up to 0.30 bits per component; real signals by 0.38 or more. And a real sequence
# shows no pair structure: period2 stayed below 0.06 on every real bench signal.
REAL_MARGIN = 0.34
PERIOD2_LIMIT = 0.08
# A double-width integer reading (ci32 for ci16 data) beat the true format by up to 0.052
# bits/byte on bench v0 (BPSK below 2 samples per symbol), and the reverse happened too; within
# this the width is reported UNKNOWN with both candidates.
WIDTH_MARGIN = 0.1
# A best score this close to 8 bits/byte means the bytes look random under every format.
RANDOM_BITS = 7.9
# Fewer bytes than this can't be scored meaningfully.
MIN_BYTES = 1024

_ALIGN = 16  # the largest sample size (cf64), so every format stays aligned to byte 0
_MANTISSA = {32: 23, 64: 52}
_EXPONENT = {32: 8, 64: 11}
_GAUSS = 0.5 * math.log2(2 * math.pi * math.e)  # a Gaussian's entropy beyond log2(sigma), bits

Container = Literal["wav"]


@dataclass(frozen=True)
class ExtensionHint:
    extension: str
    datatypes: tuple[str, ...]  # empty for generic extensions that name no format
    source: str


def _hint(extension: str, datatype: str | None, source: str) -> ExtensionHint:
    return ExtensionHint(extension, (datatype,) if datatype else (), source)


# What the recorders that use each extension write. Integer and float widths wider than a byte
# are the host order of the machines those tools run on, which is little-endian.
EXTENSIONS = {
    h.extension: h
    for h in (
        _hint(".cu8", "cu8", "rtl_sdr and rtl_433 write 8-bit unsigned I/Q as .cu8"),
        _hint(".cs8", "ci8", "hackrf_transfer and rtl_433 write 8-bit signed I/Q as .cs8"),
        _hint(".sc8", "ci8", "UHD's sc8 wire format is 8-bit signed I/Q"),
        _hint(".cs16", "ci16_le", "rtl_433 and SoapySDR tools write 16-bit signed I/Q as .cs16"),
        _hint(".sc16", "ci16_le", "UHD's sc16 format is 16-bit signed I/Q"),
        _hint(".cf32", "cf32_le", "rtl_433 and SoapySDR tools write 32-bit float I/Q as .cf32"),
        _hint(".fc32", "cf32_le", "UHD's fc32 format is 32-bit float I/Q"),
        _hint(".cfile", "cf32_le", "GNU Radio's file sink writes complex float32 as .cfile"),
        *(
            _hint(ext, None, f"{ext} is used for recordings of any format")
            for ext in (".raw", ".bin", ".dat", ".iq")
        ),
    )
}


def extension_hint(name: str) -> ExtensionHint | None:
    """What a recording's file extension suggests about its format, or None if nothing."""
    return EXTENSIONS.get(Path(name).suffix.lower())


@dataclass(frozen=True)
class Score:
    bits_per_byte: float  # estimated code length; lower explains more
    residual_bits: float  # log2 of the prediction residual per component, in its own units
    period2: float = 0.0  # real readings: how far even and odd samples differ (0 if stationary)


@dataclass(frozen=True)
class Candidate:
    datatype: str
    score: Score


@dataclass(frozen=True)
class FormatSniff:
    container: Container | None
    candidates: tuple[Candidate, ...]  # best first
    bytes_scored: int
    hint: ExtensionHint | None = None

    @property
    def datatype(self) -> Parameter:
        return _datatype_parameter(self)


def detect_container(head: bytes) -> Container | None:
    """A known container header at the start of the file, or None."""
    if head[:4] in (b"RIFF", b"RIFX", b"RF64", b"BW64") and head[8:12] == b"WAVE":
        return "wav"
    if head[:16] == W64_RIFF and head[24:40] == W64_WAVE:
        return "wav"
    return None


def sniff(path: Path, *, block_bytes: int = BLOCK_BYTES, blocks: int = BLOCKS) -> FormatSniff:
    """Score every datatype on a few blocks spread across the file; memory stays bounded."""
    size = path.stat().st_size
    with path.open("rb") as file:
        container = detect_container(file.read(40))
        if container is not None:
            return FormatSniff(container, (), 0)
        chunks = [
            _read(file, start, block_bytes) for start in _block_starts(size, block_bytes, blocks)
        ]
    return sniff_blocks(chunks, extension_hint(path.name))


def sniff_blocks(chunks: list[bytes], hint: ExtensionHint | None = None) -> FormatSniff:
    """Rank every datatype by its mean score over blocks that each start sample-aligned."""
    total = sum(len(c) for c in chunks)
    if total < MIN_BYTES:
        return FormatSniff(None, (), 0, hint)
    candidates: list[Candidate] = []
    for datatype in ALL_DATATYPES:
        fmt = SampleFormat.parse(datatype)
        scores = [score(c, fmt) for c in chunks]
        candidates.append(
            Candidate(
                datatype,
                Score(
                    float(np.mean([s.bits_per_byte for s in scores])),
                    float(np.mean([s.residual_bits for s in scores])),
                    float(np.mean([s.period2 for s in scores])),
                ),
            )
        )
    # Stable order on ties: complex before real, then the SigMF vocabulary order.
    candidates.sort(key=lambda c: (round(c.score.bits_per_byte, 9), c.datatype[0] != "c"))
    return FormatSniff(None, tuple(candidates), total, hint)


def score(raw: bytes, fmt: SampleFormat) -> Score:
    """Score `raw` read as `fmt`."""
    usable = len(raw) - len(raw) % fmt.sample_bytes
    comps: NDArray[Any] = np.frombuffer(raw[:usable], fmt.component_dtype)
    if len(comps) < 4 * ORDER:
        return Score(8.0, math.inf)
    width = float(fmt.bits)
    if fmt.kind != "f":
        x = comps.astype(np.float64)
        sigma, spread = _residual(x, fmt.is_complex)
        per = min(max(spread + _GAUSS, 0.0), width)
        return Score(per * 8 / width, _log2(sigma), 0.0 if fmt.is_complex else period2(x))
    # Wrong readings produce NaN, infinities and overflow; they are costed, not reported.
    with np.errstate(all="ignore"):
        x = comps.astype(np.float64)
        mag = np.abs(x)
        valid = np.isfinite(x) & ((mag == 0) | (mag >= np.finfo(fmt.component_dtype).tiny))
        frac_bad = 1.0 - float(valid.mean())
        if frac_bad > 0.5:
            return Score(8.0, math.inf)
        x = np.where(valid, x, 0.0)
        mag = np.abs(x)
        sigma, _ = _residual(x, fmt.is_complex)
        # Each value against its own component's residual: an improper signal's weak component
        # (Q of BPSK) needs fewer mantissa bits than the strong one.
        own = _component_sigma(x, fmt.is_complex)
        mantissa = _MANTISSA[fmt.bits]
        # Mantissa bits the predictor can't explain: the ULP of |x| is |x| 2^-mantissa.
        nonzero = mag > 0
        need = np.nan_to_num(mantissa + np.log2(own[nonzero] / mag[nonzero]) + _GAUSS, nan=mantissa)
    unexplained = float(np.clip(need, 0, mantissa).sum()) / max(1, int(valid.sum()))
    _, exponent = np.frexp(x[valid])
    per_valid = 1 + min(_entropy(exponent), _EXPONENT[fmt.bits]) + unexplained
    per = (1 - frac_bad) * min(width, per_valid) + frac_bad * width
    return Score(per * 8 / width, _log2(sigma), 0.0 if fmt.is_complex else period2(x))


def prediction_error(x: NDArray[Any], order: int = ORDER) -> float:
    """Mean-square one-step error of the order-`order` linear predictor (Levinson-Durbin)."""
    return _lpc(x, order)[1]


def _lpc(x: NDArray[Any], order: int = ORDER) -> tuple[list[complex], float]:
    """Predictor coefficients (x[t] ~ sum a[j] x[t-1-j], mean removed) and the error power."""
    x = x - x.mean()
    n = len(x)
    r = [complex(np.vdot(x[: n - k], x[k:])) / n for k in range(order + 1)]
    error = r[0].real
    if not all(map(np.isfinite, r)):
        return [], math.inf  # overflow: nothing about these values is predictable
    if error <= 0:
        return [], 0.0
    a: list[complex] = []
    for m in range(1, order + 1):
        k = (r[m] - sum(a[j] * r[m - 1 - j] for j in range(m - 1))) / error
        a = [a[j] - k * a[m - 2 - j].conjugate() for j in range(m - 1)] + [k]
        error *= 1 - abs(k) ** 2
        if error <= 0:
            return a, 0.0
    return a, error


def _residual(x: NDArray[Any], is_complex: bool) -> tuple[float, float]:
    """Residual standard deviation per real component, and log2 of the spread it costs.

    A real reading's spread is its residual with the quantisation floor. A complex reading's is
    the better of two models. One is the complex predictor's joint I/Q residual: a quarter of
    log2 det of their 2 x 2 covariance (with the floor), so components of unequal size or moving
    together (improper signals: BPSK, repeated bits) are costed at what they carry, not at their
    average. The other gives I and Q a predictor each, which suits a weak component the complex
    predictor would amplify (the noise in BPSK's Q).
    """
    floor = 1 / 12
    if not is_complex:
        error = prediction_error(x)
        if not math.isfinite(error):
            return math.inf, 64.0
        return math.sqrt(error), 0.5 * math.log2(error + floor)
    z = x[0::2] + 1j * x[1::2]
    a, error = _lpc(z)
    if not math.isfinite(error):
        return math.inf, 64.0
    e = _innovations(z, a)
    cov = np.cov(np.vstack([e.real, e.imag])) + floor * np.eye(2)
    det = float(np.linalg.det(cov))
    joint = 0.25 * math.log2(det) if det > 0 and math.isfinite(det) else 64.0
    separate = [prediction_error(x[k::2]) for k in (0, 1)]
    own = (
        0.25 * sum(math.log2(v + floor) for v in separate)
        if all(math.isfinite(v) for v in separate)
        else 64.0
    )
    return math.sqrt(error / 2), min(joint, own)


def _component_sigma(x: NDArray[Any], is_complex: bool) -> NDArray[np.float64]:
    """The residual standard deviation of each value's own component."""
    if not is_complex:
        return np.full(len(x), math.sqrt(prediction_error(x)))
    z = x[0::2] + 1j * x[1::2]
    a, error = _lpc(z)
    if not math.isfinite(error):
        return np.full(len(x), math.inf)
    e = _innovations(z, a)
    out = np.empty(len(x))
    for k, joint in ((0, float(np.std(e.real))), (1, float(np.std(e.imag)))):
        own = math.sqrt(prediction_error(x[k::2]))
        out[k::2] = min(joint, own) if math.isfinite(own) else joint
    return out


def _innovations(z: NDArray[Any], a: list[complex]) -> NDArray[np.complex128]:
    z = z - z.mean()
    order = len(a)
    if order == 0:
        return z.astype(np.complex128)
    predicted = sum(a[j] * z[order - 1 - j : len(z) - 1 - j] for j in range(order))
    return np.asarray(z[order:] - predicted, dtype=np.complex128)


def period2(x: NDArray[Any]) -> float:
    """Evidence that a stream is interleaved pairs rather than one real sequence.

    For a stationary real sequence, neighbours within a pair (x[2n], x[2n+1]) and across pairs
    (x[2n+1], x[2n+2]) are correlated alike, and even and odd samples have equal power. Returned
    is the larger of the absolute difference of the two correlations on Fisher's z scale and the
    absolute log ratio of the even and odd powers: about 0 for a real sequence, large for I/Q
    pairs whose components move together or differ in size (BPSK, repeated bits).
    """
    with np.errstate(all="ignore"):  # wrong float readings overflow; they score as infinite
        x = x - x.mean()
        n = len(x) // 2 * 2
        even, odd = x[0:n:2], x[1:n:2]
        pe, po = float(np.mean(even**2)), float(np.mean(odd**2))
        if not (math.isfinite(pe) and math.isfinite(po)):
            return math.inf
        if pe <= 0 or po <= 0:
            return 0.0 if pe == po else math.inf
        within = float(np.mean(even * odd)) / math.sqrt(pe * po)
        across = float(np.mean(odd[:-1] * even[1:])) / math.sqrt(pe * po)
    clip = 1 - 1e-9
    z = abs(math.atanh(max(-clip, min(clip, within))) - math.atanh(max(-clip, min(clip, across))))
    return max(z, abs(math.log(pe / po)))


def _log2(sigma: float) -> float:
    return math.log2(sigma) if sigma > 0 else -math.inf


def _entropy(values: NDArray[Any]) -> float:
    _, counts = np.unique(values, return_counts=True)
    p = counts / counts.sum()
    return float(-(p * np.log2(p)).sum())


def _block_starts(size: int, block_bytes: int, blocks: int) -> list[int]:
    if size <= block_bytes * blocks:
        return list(range(0, size, block_bytes))
    step = (size - block_bytes) / (blocks - 1)
    return [int(i * step) // _ALIGN * _ALIGN for i in range(blocks)]


def _read(file: BinaryIO, start: int, count: int) -> bytes:
    file.seek(start)
    return file.read(count)


def twin(datatype: str) -> str:
    """The same components read with the other layout: ci16_le <-> ri16_le."""
    return ("r" if datatype[0] == "c" else "c") + datatype[1:]


def _narrower(best: Candidate, ranked: tuple[Candidate, ...]) -> Candidate | None:
    """The same integer format at half the width, if it scores within WIDTH_MARGIN of `best`."""
    fmt = SampleFormat.parse(best.datatype)
    if fmt.kind == "f" or fmt.bits not in (16, 32):
        return None
    half = fmt.bits // 2
    name = f"{best.datatype[0]}{fmt.kind}{half}" + ("" if half == 8 else f"_{fmt.endian}")
    narrow = next(c for c in ranked if c.datatype == name)
    close = narrow.score.bits_per_byte - best.score.bits_per_byte < WIDTH_MARGIN
    return narrow if close else None


def _datatype_parameter(result: FormatSniff) -> Parameter:
    method = f"Format sniffer: code length of each SigMF datatype under an order-{ORDER} predictor"

    hint = result.hint

    def unknown(why: str, alternatives: tuple[Candidate, ...] = ()) -> Parameter:
        tied = [c.datatype for c in alternatives]
        return Parameter(
            id="datatype",
            name="Sample format",
            value=None,
            level=EvidenceLevel.UNKNOWN,
            method=method,
            evidence=(why, *_ranking(result), *_hint_evidence(hint, tied)),
            # Only the order of the tied candidates follows the extension, never their number.
            alternatives=tuple(
                Alternative(value=d)
                for d in sorted(tied, key=lambda d: not hint or d not in hint.datatypes)
            ),
            resolve_hint=FORMAT_HINT,
        )

    if result.container is not None:
        return unknown(
            f"The file is a {result.container.upper()} container; its header states the format."
        )
    if not result.candidates:
        return unknown(f"The file is too short to score: fewer than {MIN_BYTES} bytes.")
    ranked = result.candidates
    best = ranked[0]
    if best.score.bits_per_byte >= RANDOM_BITS:
        return unknown(
            f"The bytes look random under every format (best {best.score.bits_per_byte:.2f} "
            "bits/byte): the file may be compressed, encrypted, or not a sample recording."
        )
    narrow = _narrower(best, ranked)
    if narrow is not None:
        return unknown(
            f"{best.datatype} scores only "
            f"{narrow.score.bits_per_byte - best.score.bits_per_byte:.3f} bits/byte better than "
            f"{narrow.datatype} (within {WIDTH_MARGIN}); on the bench, readings this close went "
            "wrong in both directions, so the width is left to the analyst.",
            tuple(c for c in ranked if c.datatype in {best.datatype, twin(best.datatype),
                                                       narrow.datatype, twin(narrow.datatype)}),
        )  # fmt: skip
    pair = next(c for c in ranked if c.datatype == twin(best.datatype))
    rest = [c for c in ranked if c not in (best, pair)]
    close = [c for c in rest if c.score.bits_per_byte - best.score.bits_per_byte < TIE_MARGIN]
    if close:
        return unknown(
            f"{len(close) + 1} formats with different components explain the bytes about equally "
            f"well (within {TIE_MARGIN} bits/byte).",
            (best, *close),
        )
    complex_, real = sorted((best, pair), key=lambda c: c.datatype[0] != "c")
    gain = real.score.residual_bits - complex_.score.residual_bits  # > 0 favours complex
    evidence = (
        f"Best {best.datatype} at {best.score.bits_per_byte:.3f} bits/byte; the best reading "
        f"with different components, {rest[0].datatype}, costs "
        f"{rest[0].score.bits_per_byte - best.score.bits_per_byte:.3f} bits/byte more.",
        f"Reading the components as complex rather than real changes the prediction gain by "
        f"{gain:+.3f} bits per component; the real reading's pair structure is "
        f"{real.score.period2:.3f} (a real sequence stays below {PERIOD2_LIMIT}).",
        *_ranking(result),
        "IQ and QI order are not scored: swapping I and Q only mirrors the spectrum.",
    )
    convention = None
    if gain >= LAYOUT_MARGIN:
        value = complex_.datatype
    elif gain <= -REAL_MARGIN and real.score.period2 <= PERIOD2_LIMIT:
        value = real.datatype
    elif gain <= -LAYOUT_MARGIN:
        value = complex_.datatype
        convention = (
            f"The real reading ({real.datatype}) predicts the samples slightly better, but not by "
            "enough to rule out I/Q whose components are unequal or move together (BPSK, "
            "repeated bits, idle patterns), which does the same. Complex is proposed because raw "
            f"SDR recordings are usually complex I/Q; choose {real.datatype} if this is a "
            "real-valued recording."
        )
    else:
        value = complex_.datatype
        convention = (
            f"The complex ({complex_.datatype}) and real ({real.datatype}) readings fit equally "
            "well, so the samples can't tell them apart. Complex is proposed because raw SDR "
            f"recordings are usually complex I/Q; choose {real.datatype} if this is a real-valued "
            "recording."
        )
    alternatives = [c for c in ranked if c.datatype != value][:3]
    disagrees = hint is not None and bool(hint.datatypes) and value not in hint.datatypes
    return Parameter(
        id="datatype",
        name="Sample format",
        value=value,
        level=EvidenceLevel.HYPOTHESIS,
        method=method,
        evidence=evidence,
        alternatives=tuple(Alternative(value=c.datatype) for c in alternatives),
        convention=convention,
        warnings=(
            f"The file extension {hint.extension} suggests {', '.join(hint.datatypes)} "
            f"({hint.source}), but the samples score {value} better. The extension may be "
            "wrong, or the file converted; check the recording tool.",
        )
        if hint and disagrees
        else (),
    )


def _hint_evidence(hint: ExtensionHint | None, tied: list[str]) -> tuple[str, ...]:
    if hint is None:
        return ()
    if not hint.datatypes:
        return (f"The file extension {hint.extension} names no format ({hint.source}).",)
    named = ", ".join(hint.datatypes)
    if any(d in hint.datatypes for d in tied):
        return (
            f"The file extension {hint.extension} suggests {named} ({hint.source}), so it is "
            "listed first among the tied candidates; an extension is a hint, not evidence.",
        )
    return (
        f"The file extension {hint.extension} suggests {named} ({hint.source}), but the samples "
        "don't support it" + (": it is not among the tied candidates." if tied else "."),
    )


def _ranking(result: FormatSniff) -> tuple[str, ...]:
    if not result.candidates:
        return ()
    top = ", ".join(f"{c.datatype} {c.score.bits_per_byte:.3f}" for c in result.candidates[:6])
    return (
        f"Scored {len(result.candidates)} datatypes on {result.bytes_scored // 1024} KiB sampled "
        f"across the file, in bits/byte (lower explains more; random bytes cost 8): {top}, ...",
    )
