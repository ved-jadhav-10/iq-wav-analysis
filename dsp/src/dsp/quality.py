"""Capture quality: what the recording itself says about how it was captured (PLAN M2).

Four checks over the samples, each a `Parameter` so a failed decode can be traced to the capture:
clipping (the share of components sitting at the recording's peak value, which a clean signal
reaches once or twice), DC offset (the mean against the RMS), I/Q imbalance (power ratio and
phase of a complex recording) and gaps (runs of one repeated sample value, the zero fill or hold
of a dropped-sample stretch).

The samples are read in chunks, whole up to `FULL_SCAN` samples and otherwise as `PIECES` evenly
spaced pieces (said in every parameter's evidence). Limits: the I/Q figures read the whole band, so
a strong real-axis signal (BPSK at the carrier) or a single strong tone off the image pair biases
them, and the figures say so; DC cannot tell a hardware offset from a carrier at 0 Hz; a gap
filled with noise or interpolated is not seen.
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
MIN_PEAK_COUNT = 8  # components at the peak value before it counts as a plateau
CLIP_WARNING = 1e-4  # share of components at the peak above which clipping is warned
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
    peak: float = 0.0
    at_peak: int = 0
    total: complex = 0j
    energy: float = 0.0
    previous: Any = None  # the last sample of the previous chunk, for runs across the join
    run: int = 0  # length of the run of repeated samples ending at the last sample
    gaps: int = 0
    gap_samples: int = 0
    first_gap: int | None = None
    blocks: list[tuple[float, float, float, int]] = field(default_factory=lambda: [])


def _pieces(count: int) -> list[tuple[int, int]]:
    """(start, length) pieces to read: everything, or PIECES evenly spaced ones."""
    if count <= FULL_SCAN:
        return [(s, min(CHUNK, count - s)) for s in range(0, count, CHUNK)]
    starts = [round(i * (count - PIECE) / (PIECES - 1)) for i in range(PIECES)]
    return [(s + off, min(CHUNK, PIECE - off)) for s in starts for off in range(0, PIECE, CHUNK)]


def _runs(scan: _Scan, x: NDArray[Any], start: int, contiguous: bool) -> None:
    """Count the runs of at least GAP_MIN repeated samples, across chunk joins: a run still open
    at the end of a chunk is carried (`scan.run`, its samples so far) and counted once it ends."""
    if not contiguous:
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
    """End the open run at `position` (the next sample's index, or the end of the data)."""
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
    expected = -1
    for start, length in _pieces(count):
        x = np.asarray(reader.read(start, length))
        if scan is None:
            scan = _Scan(complex_input=bool(np.iscomplexobj(x)))
        contiguous = start == expected
        expected = start + len(x)
        _absorb(scan, x, start, contiguous)
    assert scan is not None
    _close_run(scan, expected)
    return _parameters(scan, count)


def _split(x: NDArray[Any]) -> tuple[Float, Float | None]:
    """The real and imaginary components of `x` (None for a real recording)."""
    if np.iscomplexobj(x):
        z = np.asarray(x, np.complex128)
        return np.asarray(z.real, np.float64), np.asarray(z.imag, np.float64)
    return np.asarray(x, np.float64), None


def _absorb(scan: _Scan, x: NDArray[Any], start: int, contiguous: bool) -> None:
    if len(x) == 0:
        return
    re, im = _split(x)
    components = re if im is None else np.concatenate((re, im))
    magnitude = np.abs(components)
    top = float(magnitude.max())
    if top > scan.peak:
        scan.peak, scan.at_peak = top, int(np.count_nonzero(magnitude == top))
    elif top == scan.peak:
        scan.at_peak += int(np.count_nonzero(magnitude == top))
    else:
        scan.at_peak += int(np.count_nonzero(magnitude == scan.peak))
    scan.samples += len(x)
    scan.components += len(components)
    scan.total += complex(np.sum(x))
    scan.energy += float(np.sum(np.abs(x) ** 2))
    if im is not None:
        for b in range(0, len(x) - BLOCK + 1, BLOCK):
            i, q = re[b : b + BLOCK], im[b : b + BLOCK]
            scan.blocks.append((float(i @ i), float(q @ q), float(i @ q), BLOCK))
    _runs(scan, x, start, contiguous)


def _scatter(values: list[float], fallback: float) -> float:
    """Standard error of the mean of per-block values; `fallback` when there are too few blocks."""
    if len(values) < 4:
        return fallback
    return float(np.std(values, ddof=1) / math.sqrt(len(values)))


def _parameters(scan: _Scan, count: int) -> tuple[Parameter, ...]:
    read = (
        f"all {count:,} samples"
        if scan.samples == count
        else f"{scan.samples:,} of {count:,} samples, in {PIECES} evenly spaced pieces"
    )
    rms = math.sqrt(scan.energy / scan.samples / (2 if scan.complex_input else 1))
    out: list[Parameter] = []

    plateau = scan.at_peak if scan.at_peak >= MIN_PEAK_COUNT else 0
    share = plateau / scan.components
    out.append(
        Parameter(
            id="clipping",
            name="Clipping",
            value=100 * share,
            unit="% of components at the peak",
            level=E.MEASURED,
            method="Components equal to the largest magnitude in the recording",
            evidence=(
                f"Read {read}; the peak component is {scan.peak:.6g}"
                + (
                    f", reached by {scan.at_peak:,}."
                    if plateau
                    else ", reached fewer than "
                    f"{MIN_PEAK_COUNT} times (a clean signal touches its peak once or twice)."
                ),
            ),
            warnings=(
                (
                    "A plateau at the peak means the capture saturated: amplitude-dependent "
                    "decisions (QAM) and the noise floor are distorted.",
                )
                if share > CLIP_WARNING
                else ()
            ),
        )
    )

    mean = scan.total / scan.samples
    dc_db = 20 * math.log10(max(abs(mean), 1e-30) / max(rms, 1e-30))
    out.append(
        Parameter(
            id="dc_offset",
            name="DC offset",
            value=round(dc_db, 2),
            unit="dB relative to the RMS component",
            level=E.MEASURED,
            method="Mean of the samples against their RMS",
            evidence=(
                f"Read {read}; mean {mean.real:.4g}{mean.imag:+.4g}j against RMS {rms:.4g}. "
                "A carrier sitting at 0 Hz cannot be told from a hardware offset.",
            ),
            warnings=(
                ("A DC spike this strong can be taken for a signal by the detector.",)
                if dc_db > DC_WARNING_DB
                else ()
            ),
        )
    )

    if scan.complex_input and scan.blocks:
        pi = [b[0] / b[3] for b in scan.blocks]
        pq = [b[1] / b[3] for b in scan.blocks]
        pc = [b[2] / b[3] for b in scan.blocks]
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
        blocks = f"{len(scan.blocks)} blocks of {BLOCK:,} samples; uncertainty from their scatter"
        out.append(
            Parameter(
                id="iq_gain_imbalance",
                name="I/Q gain imbalance",
                value=round(g, 3),
                unit="dB (I over Q)",
                uncertainty=round(g_err, 3),
                level=E.ESTIMATED,
                method="Ratio of the I and Q powers, per block",
                evidence=(f"{blocks}. {note}",),
                warnings=(
                    ("The imbalance leaves an image of every signal mirrored about 0 Hz.",)
                    if abs(g) > IMBALANCE_WARNING_DB
                    else ()
                ),
            )
        )
        out.append(
            Parameter(
                id="iq_phase_imbalance",
                name="I/Q phase imbalance",
                value=round(p, 2),
                unit="degrees from quadrature",
                uncertainty=round(p_err, 2),
                level=E.ESTIMATED,
                method="arcsin of the I-Q correlation over the I and Q powers, per block",
                evidence=(f"{blocks}. {note}",),
                warnings=(
                    ("The I and Q branches are not in quadrature; images appear.",)
                    if abs(p) > PHASE_WARNING_DEG
                    else ()
                ),
            )
        )

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
                "A gap filled with noise or interpolated is not seen.",
            ),
            warnings=(
                ("Stretches of repeated samples look like dropped samples (a buffer overrun).",)
                if scan.gaps
                else ()
            ),
        )
    )
    return tuple(out)
