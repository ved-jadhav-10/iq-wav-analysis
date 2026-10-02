"""Capture quality: what the recording itself says about how it was captured (PLAN M2).

Four checks over the samples, each a `Parameter` so a failed decode can be traced to the capture:
clipping (a plateau at the recording's peak value), DC offset (the mean against the total power),
I/Q imbalance (power ratio and phase of a complex recording) and gaps (runs of one repeated sample
value, the zero fill or hold of a dropped-sample stretch).

The samples are read in chunks, whole up to `FULL_SCAN` samples and otherwise as `PIECES` evenly
spaced pieces (said in every parameter's evidence).

Limits, each also said in the parameter it concerns:
- Clipping is a plateau: the peak value must be reached by at least `PLATEAU_RATIO` times as many
  components as the level just below it. A quantised constant-envelope signal (FM, FSK, CW from an
  8-bit capture) reaches its peak level often, but about as often as the one below; a clipped one
  piles up on the peak. A signal that takes one level only has no level below to compare with.
- The I/Q figures read the whole band, so a real-axis signal (BPSK at the carrier) or one strong
  tone off the image pair biases them; their uncertainty is the scatter of 65,536-sample blocks,
  or, for a shorter file, a white-noise figure that understates the error of a narrowband one.
- DC cannot tell a hardware offset from a carrier at 0 Hz.
- A noise-free signal repeats samples by construction (a rectangular pulse, a tone at DC), and
  those runs read as gaps; a gap filled with noise or interpolated is not seen.
"""

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from dsp.evidence import EvidenceLevel, Parameter

Float = NDArray[np.float64]
CHUNK = 1 << 18
FULL_SCAN = 1 << 26
PIECES = 64
PIECE = 1 << 20
BLOCK = 1 << 16  # samples per I/Q-imbalance estimate, for its scatter
MIN_PEAK_COUNT = 8  # components at the peak value before it can count as a plateau
PLATEAU_RATIO = 4.0  # the peak's count over the next level's, at least, for a plateau
CLIP_WARNING = 1e-4  # share of components on the plateau above which clipping is warned
GAP_MIN = 32  # repeated samples in a row that make a gap
DC_WARNING_DB = -30.0
IMBALANCE_WARNING_DB = 1.0
PHASE_WARNING_DEG = 3.0

E = EvidenceLevel


@dataclass
class _Scan:
    complex_input: bool
    samples: int = 0
    components: int = 0
    end: int = 0  # the index just past the last sample read
    levels: dict[float, int] = field(default_factory=lambda: {})  # the top two levels per chunk
    total: complex = 0j
    energy: float = 0.0
    previous: Any = None  # the last sample read while a run of repeats is open
    run: int = 0  # length of that run
    gaps: int = 0
    gap_samples: int = 0
    first_gap: int | None = None
    blocks: list[tuple[float, float, float, int]] = field(default_factory=lambda: [])
    ii: float = 0.0  # I, Q and cross power summed over every sample, for a short file
    qq: float = 0.0
    iq: float = 0.0


def _pieces(count: int) -> list[tuple[int, int]]:
    """(start, length) pieces to read: everything, or PIECES evenly spaced ones."""
    if count <= FULL_SCAN:
        return [(s, min(CHUNK, count - s)) for s in range(0, count, CHUNK)]
    starts = [round(i * (count - PIECE) / (PIECES - 1)) for i in range(PIECES)]
    return [(s + off, min(CHUNK, PIECE - off)) for s in starts for off in range(0, PIECE, CHUNK)]


def _runs(scan: _Scan, x: NDArray[Any], start: int, contiguous: bool) -> None:
    """Count the runs of at least GAP_MIN repeated samples, across chunk joins: a run still open
    at the end of a chunk is carried (`scan.run`, its samples so far) and counted once it ends,
    which is at the join when the next chunk starts with a different sample."""
    if not contiguous:
        _close_run(scan, scan.end)
    elif scan.previous is not None and x[0] != scan.previous:
        _close_run(scan, start)
    carried = scan.run if scan.previous is not None else 0
    values: NDArray[Any] = (
        x if carried == 0 else np.concatenate((np.asarray([scan.previous], dtype=x.dtype), x))
    )
    same = np.asarray(values[1:] == values[:-1], np.bool_)
    edges = np.diff(np.concatenate(([0], same.astype(np.int8), [0])))
    begins, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    scan.run = 1
    for b, e in zip(begins.tolist(), ends.tolist(), strict=True):
        length = e - b + 1  # samples b..e of `values`
        first = start + b - (1 if carried else 0)
        if b == 0 and carried:
            length += carried - 1  # the carried run's earlier samples
            first -= carried - 1
        if e == len(values) - 1:
            scan.run = length  # open at the end of the chunk: counted when it ends
        else:
            _count(scan, length, first)
    scan.previous = x[-1]


def _count(scan: _Scan, length: int, first: int) -> None:
    if length >= GAP_MIN:
        scan.gaps += 1
        scan.gap_samples += length
        if scan.first_gap is None:
            scan.first_gap = first


def _close_run(scan: _Scan, position: int) -> None:
    """End the open run at `position`, the index just past its last sample."""
    if scan.previous is not None:
        _count(scan, scan.run, position - scan.run)
    scan.run = 0
    scan.previous = None


def capture_quality(reader: Any) -> tuple[Parameter, ...]:
    """The capture-quality parameters of an open reader (`num_samples`, `read(start, count)`), or
    a single UNKNOWN when it holds no samples. Deterministic for a given recording."""
    count = int(reader.num_samples)
    if count == 0:
        return (
            Parameter(
                id="capture_quality",
                name="Capture quality",
                value=None,
                level=E.UNKNOWN,
                method="Sample statistics (dsp.quality)",
                evidence=("The recording holds no samples.",),
                resolve_hint="Open a recording that holds samples.",
            ),
        )
    scan: _Scan | None = None
    for start, length in _pieces(count):
        x = np.asarray(reader.read(start, length))
        if len(x) == 0:
            continue
        if scan is None:
            scan = _Scan(complex_input=bool(np.iscomplexobj(x)))
        _absorb(scan, x, start, start == scan.end)
    assert scan is not None
    _close_run(scan, scan.end)
    return _parameters(scan, count)


def _split(x: NDArray[Any]) -> tuple[Float, Float | None]:
    """The real and imaginary components of `x` (None for a real recording)."""
    if np.iscomplexobj(x):
        z = np.asarray(x, np.complex128)
        return np.asarray(z.real, np.float64), np.asarray(z.imag, np.float64)
    return np.asarray(x, np.float64), None


def _absorb(scan: _Scan, x: NDArray[Any], start: int, contiguous: bool) -> None:
    re, im = _split(x)
    components = re if im is None else np.concatenate((re, im))
    magnitude = np.abs(components)
    # The top two distinct levels and how often each occurs here: the global peak and the level
    # below it are always among a chunk's own top two wherever they occur.
    top = float(magnitude.max())
    below = magnitude[magnitude < top]
    seen = [top] + ([float(below.max())] if below.size else [])
    for level in seen:
        scan.levels[level] = scan.levels.get(level, 0) + int(np.count_nonzero(magnitude == level))
    scan.samples += len(x)
    scan.components += len(components)
    scan.total += complex(np.sum(x))
    scan.energy += float(np.sum(np.abs(x) ** 2))
    if im is not None:
        scan.ii += float(re @ re)
        scan.qq += float(im @ im)
        scan.iq += float(re @ im)
        for b in range(0, len(x) - BLOCK + 1, BLOCK):
            i, q = re[b : b + BLOCK], im[b : b + BLOCK]
            scan.blocks.append((float(i @ i), float(q @ q), float(i @ q), BLOCK))
    _runs(scan, x, start, contiguous)
    scan.end = start + len(x)


def _scatter(values: list[float], fallback: float) -> float:
    """Standard error of the mean of per-block values; `fallback` when there are too few blocks."""
    if len(values) < 4:
        return fallback
    return float(np.std(values, ddof=1) / math.sqrt(len(values)))


def _clipping(scan: _Scan, read: str) -> Parameter:
    ranked = sorted(scan.levels, reverse=True)
    peak, at_peak = ranked[0], scan.levels[ranked[0]]
    second = ranked[1] if len(ranked) > 1 else None
    at_second = scan.levels[second] if second is not None else 0
    if at_peak < MIN_PEAK_COUNT:
        verdict = (
            f"reached by {at_peak} component(s), fewer than {MIN_PEAK_COUNT}: a clean signal "
            "touches its peak once or twice."
        )
        plateau = False
    elif second is None:
        verdict = (
            f"reached by {at_peak:,} components, and the recording takes no other level, so "
            "there is no plateau to tell from the signal itself."
        )
        plateau = False
    elif at_peak >= PLATEAU_RATIO * at_second:
        verdict = (
            f"reached by {at_peak:,} components against {at_second:,} at the level below "
            f"({second:.6g}): a plateau."
        )
        plateau = True
    else:
        verdict = (
            f"reached by {at_peak:,} components against {at_second:,} at the level below "
            f"({second:.6g}): no plateau (a quantised or constant-envelope signal reaches its "
            "peak level about as often as the one under it)."
        )
        plateau = False
    share = at_peak / scan.components if plateau else 0.0
    return Parameter(
        id="clipping",
        name="Clipping",
        value=100 * share,
        unit="% of components on the plateau",
        level=E.MEASURED,
        method="A plateau at the largest magnitude in the recording: the peak level's count "
        f"against the next level's (at least {PLATEAU_RATIO:g} times it)",
        evidence=(f"Read {read}; the peak component is {peak:.6g}, {verdict}",),
        warnings=(
            (
                "A plateau at the peak means the capture saturated: amplitude-dependent "
                "decisions (QAM) and the noise floor are distorted.",
            )
            if share > CLIP_WARNING
            else ()
        ),
    )


def _imbalance(scan: _Scan) -> tuple[Parameter, Parameter] | None:
    if not scan.complex_input:
        return None
    if scan.blocks:
        pi = [b[0] / b[3] for b in scan.blocks]
        pq = [b[1] / b[3] for b in scan.blocks]
        pc = [b[2] / b[3] for b in scan.blocks]
        how = f"{len(scan.blocks)} blocks of {BLOCK:,} samples; uncertainty from their scatter"
    else:  # a file shorter than one block: one estimate over all of it
        pi, pq, pc = [scan.ii / scan.samples], [scan.qq / scan.samples], [scan.iq / scan.samples]
        how = (
            f"one estimate over all {scan.samples:,} samples (fewer than one block of {BLOCK:,})"
            "; its uncertainty assumes independent samples"
        )
    if len(pi) < 4:
        how += ", which understates it for a narrowband recording"
    gain = [10 * math.log10(max(a, 1e-30) / max(b, 1e-30)) for a, b in zip(pi, pq, strict=True)]
    phase = [
        math.degrees(math.asin(max(-1.0, min(1.0, c / math.sqrt(max(a * b, 1e-60))))))
        for a, b, c in zip(pi, pq, pc, strict=True)
    ]
    note = (
        "Read as hardware imbalance only for a signal that fills I and Q alike: a real-axis "
        "signal such as BPSK at the carrier, or one strong tone, biases both."
    )
    g, g_err = float(np.mean(gain)), _scatter(gain, 8.7 / math.sqrt(scan.samples))
    p, p_err = float(np.mean(phase)), _scatter(phase, 50.0 / math.sqrt(scan.samples))
    return (
        Parameter(
            id="iq_gain_imbalance",
            name="I/Q gain imbalance",
            value=round(g, 3),
            unit="dB (I over Q)",
            uncertainty=round(g_err, 3),
            level=E.ESTIMATED,
            method="Ratio of the I and Q powers, per block",
            evidence=(f"{how}. {note}",),
            warnings=(
                ("The imbalance leaves an image of every signal mirrored about 0 Hz.",)
                if abs(g) > IMBALANCE_WARNING_DB
                else ()
            ),
        ),
        Parameter(
            id="iq_phase_imbalance",
            name="I/Q phase imbalance",
            value=round(p, 2),
            unit="degrees from quadrature",
            uncertainty=round(p_err, 2),
            level=E.ESTIMATED,
            method="arcsin of the I-Q correlation over the I and Q powers, per block",
            evidence=(f"{how}. {note}",),
            warnings=(
                ("The I and Q branches are not in quadrature; images appear.",)
                if abs(p) > PHASE_WARNING_DEG
                else ()
            ),
        ),
    )


def _parameters(scan: _Scan, count: int) -> tuple[Parameter, ...]:
    read = (
        f"all {count:,} samples"
        if scan.samples == count
        else f"{scan.samples:,} of {count:,} samples, in {PIECES} evenly spaced pieces"
    )
    out: list[Parameter] = [_clipping(scan, read)]

    mean = scan.total / scan.samples
    rms = math.sqrt(scan.energy / scan.samples)  # of the whole sample, I and Q together
    dc_db = 20 * math.log10(max(abs(mean), 1e-30) / max(rms, 1e-30))
    out.append(
        Parameter(
            id="dc_offset",
            name="DC offset",
            value=round(dc_db, 2),
            unit="dB relative to the total power",
            level=E.MEASURED,
            method="Power of the mean sample over the mean power of the samples",
            evidence=(
                f"Read {read}; mean {mean.real:.4g}{mean.imag:+.4g}j against an RMS sample of "
                f"{rms:.4g}. A carrier sitting at 0 Hz cannot be told from a hardware offset.",
            ),
            warnings=(
                ("A DC spike this strong can be taken for a signal by the detector.",)
                if dc_db > DC_WARNING_DB
                else ()
            ),
        )
    )

    out += _imbalance(scan) or ()

    where = f", the first at sample {scan.first_gap:,}" if scan.first_gap is not None else ""
    out.append(
        Parameter(
            id="gaps",
            name="Dropped-sample gaps",
            value=scan.gaps,
            unit=f"runs of {GAP_MIN}+ repeated samples",
            level=E.MEASURED,
            method="Runs of one repeated sample value (a zero fill or a hold)",
            evidence=(
                f"Read {read}: {scan.gaps} run(s), {scan.gap_samples:,} samples in all{where}. "
                "A gap filled with noise or interpolated is not seen, and a noise-free signal "
                "repeats samples by construction (a rectangular pulse, a tone at DC).",
            ),
            warnings=(
                ("Stretches of repeated samples look like dropped samples (a buffer overrun).",)
                if scan.gaps
                else ()
            ),
        )
    )
    return tuple(out)
