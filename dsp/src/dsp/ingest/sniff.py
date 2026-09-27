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
prediction gain alone: how many bits per component the complex predictor saves over the real one.

Limits: noise, and real signals read as I/Q pairs, fit the complex and real readings equally
well; complex is then proposed by a stated convention. IQ versus QI order only mirrors the
spectrum and is not scored. The data is assumed to start at byte 0 unless a known header is
found. The code lengths are model estimates for ranking, not the output of a real compressor.
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

ORDER = 8
BLOCK_BYTES = 1 << 16
BLOCKS = 4
# Tie margins, set from the bench (bench/results/sniffer.md). Between formats whose components
# differ, in bits/byte: wrong readings came within ~0.02 of the truth. Between the real and
# complex readings of the same components, in bits of prediction gain per component: the wrong
# layout never won by more than ~0.01.
TIE_MARGIN = 0.05
LAYOUT_MARGIN = 0.02
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
class Score:
    bits_per_byte: float  # estimated code length; lower explains more
    residual_bits: float  # log2 of the prediction residual per component, in its own units


@dataclass(frozen=True)
class Candidate:
    datatype: str
    score: Score


@dataclass(frozen=True)
class FormatSniff:
    container: Container | None
    candidates: tuple[Candidate, ...]  # best first
    bytes_scored: int

    @property
    def datatype(self) -> Parameter:
        return _datatype_parameter(self)


def detect_container(head: bytes) -> Container | None:
    """A known container header at the start of the file, or None."""
    if head[:4] in (b"RIFF", b"RF64", b"BW64") and head[8:12] == b"WAVE":
        return "wav"
    return None


def sniff(path: Path, *, block_bytes: int = BLOCK_BYTES, blocks: int = BLOCKS) -> FormatSniff:
    """Score every datatype on a few blocks spread across the file; memory stays bounded."""
    size = path.stat().st_size
    with path.open("rb") as file:
        container = detect_container(file.read(12))
        if container is not None:
            return FormatSniff(container, (), 0)
        chunks = [
            _read(file, start, block_bytes) for start in _block_starts(size, block_bytes, blocks)
        ]
    return sniff_blocks(chunks)


def sniff_blocks(chunks: list[bytes]) -> FormatSniff:
    """Rank every datatype by its mean score over blocks that each start sample-aligned."""
    total = sum(len(c) for c in chunks)
    if total < MIN_BYTES:
        return FormatSniff(None, (), 0)
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
                ),
            )
        )
    # Stable order on ties: complex before real, then the SigMF vocabulary order.
    candidates.sort(key=lambda c: (round(c.score.bits_per_byte, 9), c.datatype[0] != "c"))
    return FormatSniff(None, tuple(candidates), total)


def score(raw: bytes, fmt: SampleFormat) -> Score:
    """Score `raw` read as `fmt`."""
    usable = len(raw) - len(raw) % fmt.sample_bytes
    comps: NDArray[Any] = np.frombuffer(raw[:usable], fmt.component_dtype)
    if len(comps) < 4 * ORDER:
        return Score(8.0, math.inf)
    width = float(fmt.bits)
    if fmt.kind != "f":
        sigma = _residual_sigma(comps.astype(np.float64), fmt.is_complex)
        per = min(max(math.log2(math.hypot(sigma, 12**-0.5)) + _GAUSS, 0.0), width)
        return Score(per * 8 / width, _log2(sigma))
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
        sigma = _residual_sigma(x, fmt.is_complex)
        mantissa = _MANTISSA[fmt.bits]
        # Mantissa bits the predictor can't explain: the ULP of |x| is |x| 2^-mantissa.
        need = np.nan_to_num(mantissa + np.log2(sigma / mag[mag > 0]) + _GAUSS, nan=mantissa)
    unexplained = float(np.clip(need, 0, mantissa).sum()) / max(1, int(valid.sum()))
    _, exponent = np.frexp(x[valid])
    per_valid = 1 + min(_entropy(exponent), _EXPONENT[fmt.bits]) + unexplained
    per = (1 - frac_bad) * min(width, per_valid) + frac_bad * width
    return Score(per * 8 / width, _log2(sigma))


def prediction_error(x: NDArray[Any], order: int = ORDER) -> float:
    """Mean-square one-step error of the order-`order` linear predictor (Levinson-Durbin)."""
    x = x - x.mean()
    n = len(x)
    r = [complex(np.vdot(x[: n - k], x[k:])) / n for k in range(order + 1)]
    error = r[0].real
    if not all(map(np.isfinite, r)):
        return math.inf  # overflow: nothing about these values is predictable
    if error <= 0:
        return 0.0
    a: list[complex] = []
    for m in range(1, order + 1):
        k = (r[m] - sum(a[j] * r[m - 1 - j] for j in range(m - 1))) / error
        a = [a[j] - k * a[m - 2 - j].conjugate() for j in range(m - 1)] + [k]
        error *= 1 - abs(k) ** 2
        if error <= 0:
            return 0.0
    return error


def _residual_sigma(x: NDArray[Any], is_complex: bool) -> float:
    """Residual standard deviation per real component."""
    if is_complex:
        return math.sqrt(prediction_error(x[0::2] + 1j * x[1::2]) / 2)
    return math.sqrt(prediction_error(x))


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


def _datatype_parameter(result: FormatSniff) -> Parameter:
    method = f"Format sniffer: code length of each SigMF datatype under an order-{ORDER} predictor"

    def unknown(why: str, alternatives: tuple[Candidate, ...] = ()) -> Parameter:
        return Parameter(
            id="datatype",
            name="Sample format",
            value=None,
            level=EvidenceLevel.UNKNOWN,
            method=method,
            evidence=(why, *_ranking(result)),
            alternatives=tuple(Alternative(value=c.datatype) for c in alternatives),
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
    pair = next(c for c in ranked if c.datatype == twin(best.datatype))
    rest = [c for c in ranked[1:] if c is not pair]
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
        f"{gain:+.3f} bits per component.",
        *_ranking(result),
        "IQ and QI order are not scored: swapping I and Q only mirrors the spectrum.",
    )
    convention = None
    if gain >= LAYOUT_MARGIN:
        value = complex_.datatype
    elif gain <= -LAYOUT_MARGIN:
        value = real.datatype
    else:
        value = complex_.datatype
        convention = (
            f"The complex ({complex_.datatype}) and real ({real.datatype}) readings fit equally "
            "well, so the samples can't tell them apart. Complex is proposed because raw SDR "
            f"recordings are usually complex I/Q; choose {real.datatype} if this is a real-valued "
            "recording."
        )
    alternatives = [c for c in ranked if c.datatype != value][:3]
    return Parameter(
        id="datatype",
        name="Sample format",
        value=value,
        level=EvidenceLevel.HYPOTHESIS,
        method=method,
        evidence=evidence,
        alternatives=tuple(Alternative(value=c.datatype) for c in alternatives),
        convention=convention,
    )


def _ranking(result: FormatSniff) -> tuple[str, ...]:
    if not result.candidates:
        return ()
    top = ", ".join(f"{c.datatype} {c.score.bits_per_byte:.3f}" for c in result.candidates[:6])
    return (
        f"Scored {len(result.candidates)} datatypes on {result.bytes_scored // 1024} KiB sampled "
        f"across the file, in bits/byte (lower explains more; random bytes cost 8): {top}, ...",
    )
