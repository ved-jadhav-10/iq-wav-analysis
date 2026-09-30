"""Signal detection in time and frequency (PLAN §5 M2).

For each FFT size the recording's Welch spectrogram (dsp.spectrum) is searched:

1. **Noise floor.** Each bin's median over time is robust to bursts. An ordered statistic of
   those medians over a sliding window of 1/8 of the band (OS-CFAR along frequency) follows a
   receiver's passband shape; it is capped at a low percentile of the whole band, so a signal
   wider than the window can't raise the floor under itself.
2. **Cells.** A cell's power over the floor is, in noise, the mean of K unit exponentials (K the
   frames averaged, less their overlap correlation), so its thresholds are exact Gamma
   quantiles: seeds at a false-alarm probability of SEED_PFA, extent at EXTENT_PFA (hysteresis).
3. **Clean-up and labelling.** A morphological closing joins fragments of one signal; connected
   components (8-connectivity) that hold a seed become candidates.
4. **Significance.** Candidates are chosen on the even-numbered frames of each row and tested
   on the odd-numbered ones (split-sample), so the test isn't biased by the selection. A
   candidate's mean over its cells in the odd frames has an exact Gamma null; its tail
   probability must be below ALPHA divided by the number of cells and by the number of searches
   (Bonferroni over every place a component could start). Every candidate counts as a
   hypothesis.

Each FFT size is searched twice: row by row, and on all rows averaged into one (the Welch PSD of
the whole recording), which finds weak continuous signals no single row shows.

The searches are merged finest frequency resolution first (see `merge`). Time edges are then
refined on the finest time grid. A detection just beside a much stronger one over the same time
is taken as its skirt or sidelobe and dropped; a weak detection mirrored across 0 Hz by a much
stronger one over the same time is labelled a probable I/Q-imbalance image.

Units: samples and cycles/sample. The in-band SNR a detection reports is a detector statistic
(biased upwards near threshold, because cells were selected for being high); the estimation
stage measures SNR properly.

Limits: a signal filling more than about 70 % of the band raises the floor estimate; noise whose
level changes over time (receiver AGC) is not tracked; a burst shorter than a spectrogram row is
diluted by the row's average, and rows lengthen with the recording (MAX_CELLS).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from itertools import pairwise
from typing import Any

import numpy as np
from numpy.typing import NDArray

from dsp import _scipy
from dsp.evidence import EvidenceLevel, Parameter
from dsp.spectrum import Grid, Spectrogram, plan_grid, read_span, spectrograms

Float = NDArray[np.float64]

FFT_SIZES = (256, 1024, 4096)
SEED_PFA = 1e-4
EXTENT_PFA = 1e-2
ALPHA = 0.01  # family-wise chance of a false detection in a recording, shared by the searches
FLOOR_WINDOW = 8  # the local floor's window is 1/FLOOR_WINDOW of the band
FLOOR_RANK = 20.0  # percentile of the window taken as its floor
GLOBAL_RANK = 30.0  # percentile of the whole band that caps the local floor
IMAGE_DB = 15.0  # an image or sidelobe is at least this much weaker than its signal
VALLEY_DB = 10.0  # a gap this far below both neighbours separates two signals
REFINE_DB = 10.0  # time refinement keeps rows within this of the band's upper level


@dataclass(frozen=True)
class Detection:
    start: int  # first sample
    stop: int  # one past the last sample
    low: float  # lower band edge, cycles/sample
    high: float  # upper band edge, cycles/sample
    nfft: int  # the FFT size it was found at
    snr_db: float  # detector statistic: mean cell power over the floor, less one, in dB
    score: float  # -log10 of the box's tail probability (significance)
    cells: int
    image_of: int | None = None  # index of the detection this one mirrors
    # degrees of freedom behind snr_db's cell mean (`detection_parameters`'s uncertainty); 0
    # only for a Detection built by hand (tests), never one from detect_resolution/merge_tone_combs.
    dof: float = 0.0
    # samples per row in the time grid that set start/stop (`detection_parameters`'s
    # uncertainty); 0 only for a Detection built by hand (tests).
    time_resolution: int = 0

    @property
    def centre(self) -> float:
        return (self.low + self.high) / 2

    @property
    def bandwidth(self) -> float:
        return self.high - self.low

    @property
    def duration(self) -> int:
        return self.stop - self.start


@dataclass(frozen=True)
class Floor:
    level: Float  # per bin, density units
    global_level: float
    local_bins: int  # how many bins the cap replaced the local estimate in


@dataclass(frozen=True)
class Resolution:
    """One search: an FFT size, time-resolved or integrated over the whole recording."""

    spectrogram: Spectrogram
    floor: Floor
    candidates: int
    detections: tuple[Detection, ...]
    threshold: float  # the significance a box needed, as -log10 p

    @property
    def integrated(self) -> bool:
        return self.spectrogram.grid.rows == 1


@dataclass(frozen=True)
class DetectionResult:
    resolutions: tuple[Resolution, ...]
    detections: tuple[Detection, ...]
    samples: int
    real_input: bool

    @property
    def hypotheses(self) -> int:
        return sum(r.candidates for r in self.resolutions)

    @property
    def noise_density(self) -> float:
        """The finest-frequency resolution's global floor: noise per unit normalised frequency."""
        return self.resolutions[-1].floor.global_level

    def finest_frequency(self) -> Resolution:
        return max(self.resolutions, key=lambda r: (r.spectrogram.nfft, not r.integrated))


def integrate(spec: Spectrogram) -> Spectrogram:
    """The spectrogram's rows averaged into one: the Welch PSD of the whole span, which finds
    weak continuous signals that no single row shows."""
    g = spec.grid
    dof_even, dof_odd = spec.half_dof

    def mean(rows: NDArray[np.float32], weights: Float) -> NDArray[np.float32]:
        w = weights / weights.sum()
        return (w @ rows.astype(np.float64))[None, :].astype(np.float32)

    return Spectrogram(
        Grid(g.nfft, g.start, g.frames, 1),
        mean(spec.power, spec.counts.astype(np.float64)),
        mean(spec.even, dof_even),
        mean(spec.odd, dof_odd),
        np.array([spec.counts.sum()], np.int64),
        spec.freqs,
        spec.real_input,
    )


def _median_factor(dof: float) -> float:
    return _scipy.gamma_ppf(0.5, dof)


def noise_floor(spec: Spectrogram) -> Floor:
    dof = float(np.median(spec.dof))
    rows = spec.power.shape[0]
    medians = np.median(spec.power, axis=0).astype(np.float64) / _median_factor(dof)
    # A median over `rows` rows of K-frame averages has relative spread ~1.25/sqrt(rows K); an
    # order statistic of such values sits that many spreads below their mean.
    spread = 1.2533 / math.sqrt(rows * dof)
    width = max(3, len(medians) // FLOOR_WINDOW) | 1
    local = _scipy.percentile_filter(medians, FLOOR_RANK, width) / (1 - 0.8416 * spread)
    cap = float(np.percentile(medians, GLOBAL_RANK)) / (1 - 0.5244 * spread)
    level = np.minimum(local, cap)
    return Floor(level, cap, int(np.sum(local > cap)))


def _thresholds(dof: Float, pfa: float) -> Float:
    unique = {float(d): _scipy.gamma_isf(pfa, float(d)) for d in np.unique(dof)}
    return np.array([unique[float(d)] for d in dof])


def _row_width(grid: Grid, row: int) -> int:
    """The sample span one row covers in `grid`: the granularity time-edge snapping (start/stop)
    is limited to, so a detection's time uncertainty (`detection_parameters`) is stated against
    this, not against `nfft` - refine_time and detect_resolution can each set start/stop from a
    different grid than the detection's own `nfft`."""
    start, stop = grid.row_span(row, row)
    return stop - start


def detect_resolution(
    spec: Spectrogram, floor: Floor | None = None, *, searches: int = 1
) -> Resolution:
    """Candidates are chosen on the even frames and tested on the odd ones, so the test isn't
    biased by the selection (frames of opposite parity correlate by rho^2 = 0.028)."""
    floor = floor or noise_floor(spec)
    level = floor.level[None, :]
    # A silent recording has a zero floor: 0/0 is nothing to detect, not a warning.
    with np.errstate(invalid="ignore", divide="ignore"):
        chosen, tested, ratio = (
            np.nan_to_num(x / level, nan=0.0, posinf=0.0) for x in (spec.even, spec.odd, spec.power)
        )
    dof_even, dof_odd = spec.half_dof
    seeds = chosen > _thresholds(dof_even, SEED_PFA)[:, None]
    extent = chosen > _thresholds(dof_even, EXTENT_PFA)[:, None]
    extent = _scipy.closing(extent, 3, 3) | seeds
    labels, _ = _scipy.label(extent)
    threshold = -math.log10(ALPHA / searches / ratio.size)
    found: list[Detection] = []
    candidates = 0
    seeded = set(np.unique(labels[seeds]).tolist())
    cell_dof = np.broadcast_to(dof_odd[:, None], ratio.shape)
    # dof behind snr_db's mean, which averages every frame in a cell (spec.power), not just the
    # odd half cell_dof (above) tests significance on - kept separate from `dof` (the score's own
    # dof) so `detection_parameters`'s uncertainty isn't understated by the split-sample halving.
    full_cell_dof = np.broadcast_to(spec.dof[:, None], ratio.shape)
    for index, (rs, cs) in enumerate(_scipy.find_objects(labels), start=1):
        if index not in seeded:
            continue
        candidates += 1
        mine = labels[rs, cs] == index
        dof = float(cell_dof[rs, cs][mine].sum())
        score = -_scipy.log10_gamma_sf(float(tested[rs, cs][mine].mean()), dof)
        if score < threshold:
            continue
        start, stop = spec.grid.row_span(rs.start, rs.stop - 1)
        half_bin = 0.5 / spec.nfft
        found.append(
            Detection(
                start=start,
                stop=stop,
                low=float(spec.freqs[cs.start]) - half_bin,
                high=float(spec.freqs[cs.stop - 1]) + half_bin,
                nfft=spec.nfft,
                snr_db=10 * math.log10(max(float(ratio[rs, cs][mine].mean()) - 1, 1e-6)),
                score=score,
                cells=int(mine.sum()),
                dof=float(full_cell_dof[rs, cs][mine].sum()),
                time_resolution=_row_width(spec.grid, rs.start),
            )
        )
    return Resolution(spec, floor, candidates, tuple(found), threshold)


def _overlap(a: tuple[float, float], b: tuple[float, float]) -> float:
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def _io_min(a: Detection, b: Detection) -> float:
    """Intersection over the smaller box, in time x frequency."""
    t = _overlap((a.start, a.stop), (b.start, b.stop))
    f = _overlap((a.low, a.high), (b.low, b.high))
    smaller = min(a.duration * a.bandwidth, b.duration * b.bandwidth)
    return t * f / smaller if smaller > 0 else 0.0


def band_ratio(
    res: Resolution, low: float, high: float, start: int, stop: int
) -> tuple[float, float]:
    """Mean power over the floor in a band and time span, and its degrees of freedom."""
    spec = res.spectrogram
    half_bin = 0.5 / spec.nfft
    bins = (spec.freqs - half_bin >= low) & (spec.freqs + half_bin <= high)
    if not bins.any():
        centre = int(np.argmin(np.abs(spec.freqs - (low + high) / 2)))
        bins = np.zeros_like(bins)
        bins[centre] = True
    g = spec.grid
    b = g.bounds
    starts, stops = g.start + b[:-1] * g.hop, g.start + (b[1:] - 1) * g.hop + g.nfft
    rows = (stops > start) & (starts < stop)
    if not rows.any():
        return 1.0, 1.0
    cells = spec.power[np.ix_(rows, bins)] / res.floor.level[bins]
    dof = float(spec.dof[rows].sum()) * int(bins.sum())
    return float(cells.mean()), dof


def _fragments(parts: Sequence[Detection], reference: Resolution) -> bool:
    """Whether detections side by side in frequency are pieces of one signal: the band between
    each pair is above the noise and less than VALLEY_DB below the weaker of the pair."""
    ordered = sorted(parts, key=lambda d: d.low)
    for a, b in pairwise(ordered):
        start, stop = max(a.start, b.start), min(a.stop, b.stop)
        if stop <= start or b.low <= a.high:
            continue
        gap, dof = band_ratio(reference, a.high, b.low, start, stop)
        if gap <= _scipy.gamma_isf(EXTENT_PFA, dof):
            return False
        level_a, _ = band_ratio(reference, a.low, a.high, start, stop)
        level_b, _ = band_ratio(reference, b.low, b.high, start, stop)
        if (gap - 1) < (min(level_a, level_b) - 1) * 10 ** (-VALLEY_DB / 10):
            return False
    return True


def merge(resolutions: Sequence[Resolution]) -> list[Detection]:
    """Combine the searches, finest frequency resolution first.

    A signal is described by the finest FFT size that detects it, which gives the sharpest band
    edges (time edges are refined afterwards). A coarser detection that overlaps nothing kept is
    a new signal (a burst too short for the finer rows). One that covers two or more kept
    detections which are fragments of one weak signal replaces them; otherwise it is the same
    signal seen less sharply and is dropped. Within one FFT size, overlapping detections from
    the time-resolved and integrated searches keep the more significant.
    """
    kept: list[Detection] = []
    for nfft in sorted({r.spectrogram.nfft for r in resolutions}, reverse=True):
        level = [r for r in resolutions if r.spectrogram.nfft == nfft]
        reference = next(r for r in level if not r.integrated or len(level) == 1)
        found: list[Detection] = []
        for d in sorted((d for r in level for d in r.detections), key=lambda d: -d.score):
            if all(_io_min(d, k) <= 0.3 for k in found):
                found.append(d)
        finer = list(kept)
        for d in found:
            covered = [k for k in finer if _io_min(d, k) > 0.3]
            if not covered:
                kept.append(d)
            elif len(covered) >= 2 and _fragments(covered, reference):
                kept = [k for k in kept if k not in covered]
                kept.append(d)
    return kept


def refine_time(d: Detection, finest: Resolution) -> Detection:
    """Tighten a detection's time edges on the finest time grid: its first and last rows whose
    band power is above the noise threshold and within REFINE_DB of the band's upper level, so
    another signal's skirt under the same band doesn't stretch a burst."""
    spec, floor = finest.spectrogram, finest.floor
    half_bin = 0.5 / spec.nfft
    bins = (spec.freqs + half_bin > d.low) & (spec.freqs - half_bin < d.high)
    if not bins.any():
        return d
    g = spec.grid
    bounds = g.bounds
    starts = g.start + bounds[:-1] * g.hop
    stops = g.start + (bounds[1:] - 1) * g.hop + g.nfft
    inside = (stops > d.start) & (starts < d.stop)
    band = (spec.power[:, bins] / floor.level[bins]).mean(axis=1)
    noise = band > _thresholds(spec.dof * int(bins.sum()), EXTENT_PFA)
    if not (noise & inside).any():
        return d
    upper = float(np.percentile(band[inside], 90))
    active = noise & inside & (band > upper * 10 ** (-REFINE_DB / 10))
    rows = np.flatnonzero(active)
    start, stop = g.row_span(int(rows[0]), int(rows[-1]))
    # The edges are snapped to this grid now, not the one that set d.time_resolution (which may
    # be a different nfft's grid, from detect_resolution) - kept in step so detection_parameters'
    # uncertainty matches whichever grid actually determined start/stop.
    return replace(
        d,
        start=max(d.start, start),
        stop=min(d.stop, stop),
        time_resolution=_row_width(g, int(rows[0])),
    )


def absorb_sidelobes(detections: Sequence[Detection]) -> list[Detection]:
    """Drop a detection that sits just beside a much stronger one over the same time: the
    stronger signal's spectral skirt or sidelobe, not a signal of its own."""
    ranked = sorted(detections, key=lambda d: -d.snr_db)
    kept: list[Detection] = []
    for d in ranked:
        beside = any(
            k.snr_db - d.snr_db >= IMAGE_DB
            and _overlap((d.start, d.stop), (k.start, k.stop)) > 0.8 * d.duration
            and max(d.low - k.high, k.low - d.high) <= max(k.bandwidth, 4.0 / d.nfft)
            for k in kept
        )
        if not beside:
            kept.append(d)
    return kept


COMB_TIME_OVERLAP = 0.7  # fraction of the shorter duration two tones must share
COMB_WIDTH_RATIO = 3.0  # tones must be within this factor of each other's width


def _comb_groups(detections: Sequence[Detection]) -> list[list[Detection]]:
    """Cluster detections that share time extent and are similarly wide: several separate
    tones of one M-FSK carrier look this way, unlike independent signals, which would need to
    coincide in duration, start time and bandwidth all at once purely by chance."""
    remaining = list(detections)
    groups: list[list[Detection]] = []
    while remaining:
        seed = remaining.pop(0)
        group, rest = [seed], []
        for d in remaining:
            close = _overlap((seed.start, seed.stop), (d.start, d.stop)) >= COMB_TIME_OVERLAP * min(
                seed.duration, d.duration
            ) and (1 / COMB_WIDTH_RATIO <= d.bandwidth / seed.bandwidth <= COMB_WIDTH_RATIO)
            (group if close else rest).append(d)
        remaining = rest
        groups.append(group)
    return groups


COMB_SPACING_TOLERANCE = 0.3  # relative: how far a tone's spacing may sit from the median one
# 2 is deliberately excluded: with only one gap, "evenly spaced" holds for any pair and carries
# no information, so a 2-tone group always falls through to the power-based test below.
COMB_TEMPLATE_ORDERS = (4, 8)  # M-FSK orders with enough gaps for spacing to be real evidence
COMB_POWER_SPREAD_DB = 6.0  # the widest spread of tone SNRs a comb may have


def _evenly_spaced(group: Sequence[Detection]) -> bool:
    """Whether the group's tone count matches a valid M-FSK order (with enough tones for
    spacing to mean anything) and its centres are close to evenly spaced: continuous-phase
    M-FSK's tones sit at (2k - M + 1) * deviation, an arithmetic progression, whatever the
    deviation - this pattern is its own evidence, independent of how much noise-floor gap sits
    between the outermost tones."""
    if len(group) not in COMB_TEMPLATE_ORDERS:
        return False
    # Random data spends equal time on every tone, so an M-FSK comb's tones have near-equal
    # power; independent signals that happen to sit evenly spaced usually don't.
    powers = [d.snr_db for d in group]
    if max(powers) - min(powers) > COMB_POWER_SPREAD_DB:
        return False
    centres = sorted(d.centre for d in group)
    gaps = np.diff(centres)
    median = float(np.median(gaps))
    return median > 0 and bool(np.all(np.abs(gaps - median) <= COMB_SPACING_TOLERANCE * median))


def merge_tone_combs(detections: Sequence[Detection], reference: Resolution) -> list[Detection]:
    """Replace a cluster of similarly wide, co-temporal detections with one, when they form a
    valid M-FSK tone pattern (`_evenly_spaced`): separated M-FSK tones look like several signals
    to `merge`'s contiguity test (each tone is a narrow line with little energy between it and
    the next), unlike independent signals, which would need to coincide in duration, start time
    and bandwidth all at once purely by chance.

    An earlier version of this also merged a cluster whenever its whole span (tones and gaps
    together) cleared the ordinary significance bar, without needing the spacing pattern; that
    test turned out to accept almost any two strong, nearby, similarly wide real signals too
    (their combined average is easily significant on its own, comb or not), merging unrelated
    signals as if they were one FSK carrier - removed rather than kept as an unsound fallback.
    A 2-tone (2-FSK) cluster is never merged here for the same reason: with one gap there is no
    spacing pattern to check, so a genuine 2-FSK carrier only gets merged if `merge`'s own
    contiguity test (a real gap-significance check, unlike the removed fallback) already treats
    it as one signal - a known gap, not a silent one (see PLAN M2 §0).
    """
    out: list[Detection] = []
    for group in _comb_groups(detections):
        if not _evenly_spaced(group):
            out.extend(group)
            continue
        low, high = min(d.low for d in group), max(d.high for d in group)
        start, stop = min(d.start for d in group), max(d.stop for d in group)
        mean, dof = band_ratio(reference, low, high, start, stop)
        out.append(
            Detection(
                start=start,
                stop=stop,
                low=low,
                high=high,
                nfft=reference.spectrogram.nfft,
                snr_db=10 * math.log10(max(mean - 1, 1e-6)),
                score=max(d.score for d in group),
                cells=sum(d.cells for d in group),
                dof=dof,
                time_resolution=_row_width(reference.spectrogram.grid, 0),
            )
        )
    return out


def mark_images(detections: Sequence[Detection]) -> list[Detection]:
    """Label a weak detection mirrored across 0 Hz by a much stronger, simultaneous one."""
    out = list(detections)
    for i, a in enumerate(detections):
        for j, b in enumerate(detections):
            if i == j or b.snr_db - a.snr_db < IMAGE_DB:
                continue
            mirrored = abs(a.centre + b.centre) < max(a.bandwidth, b.bandwidth) / 2
            similar = 0.5 < a.bandwidth / b.bandwidth < 2
            together = _overlap((a.start, a.stop), (b.start, b.stop)) > 0.7 * a.duration
            if mirrored and similar and together and abs(b.centre) > b.bandwidth / 2:
                out[i] = replace(a, image_of=j)
                break
    return out


def detect(source: Any, *, real: bool, fft_sizes: Sequence[int] = FFT_SIZES) -> DetectionResult:
    """Detect signals in a whole recording, streaming it once."""
    samples = int(source.num_samples)
    grids = [g for n in fft_sizes if (g := plan_grid(samples, n)) is not None]
    if not grids:
        return DetectionResult((), (), samples, real)
    return detect_spectrograms(
        spectrograms(read_span(source, 0, samples), grids, real=real), samples, real
    )


def detect_spectrograms(specs: Sequence[Spectrogram], samples: int, real: bool) -> DetectionResult:
    count = sum(2 if s.grid.rows > 1 else 1 for s in specs)
    searches: list[Resolution] = []
    for spec in sorted(specs, key=lambda s: s.nfft):
        timed = detect_resolution(spec, searches=count)
        searches.append(timed)
        if spec.grid.rows > 1:
            searches.append(detect_resolution(integrate(spec), timed.floor, searches=count))
    resolutions = tuple(searches)
    finest_frequency = max(resolutions, key=lambda r: (r.spectrogram.nfft, not r.integrated))
    merged = absorb_sidelobes(merge_tone_combs(merge(resolutions), finest_frequency))
    finest = resolutions[0]
    refined = [refine_time(d, finest) for d in merged]
    refined.sort(key=lambda d: (d.start, d.low))
    final = refined if real else mark_images(refined)
    return DetectionResult(resolutions, tuple(final), samples, real)


def grids_for(samples: int, fft_sizes: Sequence[int] = FFT_SIZES) -> list[Grid]:
    return [g for n in fft_sizes if (g := plan_grid(samples, n)) is not None]


def detection_parameters(d: Detection) -> tuple[Parameter, ...]:
    """This detection's own findings as Parameters (PLAN §3): time in samples and frequency in
    cycles/sample, so nothing here needs a sample rate - a caller with one converts to seconds
    and Hz for display once it's known, same as the tile pyramid's frequency axis does.

    `snr_db` is the detector's own statistic, biased upward near the significance threshold
    (this module's docstring); `dsp.estimate.snr_psd` on the channelised signal is the proper
    estimate, not built here yet.
    """
    image_warning: tuple[str, ...] = ()
    if d.image_of is not None:
        image_warning = (
            f"Mirrored across 0 Hz by a much stronger, simultaneous detection (signal_"
            f"{d.image_of}); probably its I/Q-image, not an independent signal.",
        )
    # start/stop are snapped to whichever time grid last set them (refine_time's finest grid, or
    # detect_resolution's own nfft if refine_time left them unchanged) - that grid's row width
    # (d.time_resolution), not d.nfft, is the actual snapping granularity; half a row, matching
    # the "half a bin" convention centre_frequency uses above.
    time_uncertainty = max(d.time_resolution, 1) / 2.0
    # ratio_mean = 1 + s (s = the linear excess-over-floor ratio snr_db reports) is, to good
    # approximation, Gamma(shape=dof, scale=(1+s)/dof): a Gamma scale family, so its standard
    # deviation scales with its own mean, (1+s)/sqrt(dof), not with the noise-only floor's
    # deviation alone. Propagated through snr_db = 10 log10(s): d(10 log10(ratio_mean-1))
    # /d(ratio_mean) = 10/(s ln 10), giving 4.343 (1+s)/(s sqrt(dof)). Checked against dsp.synth
    # across SNR (0-30 dB, dof in the thousands): matches the true across-seed spread to within
    # about 2x in the typical 6-20 dB range; looser near 0 dB (selection effects add extra
    # spread the Gamma model doesn't capture) and at very high SNR.
    s = 10 ** (d.snr_db / 10)
    snr_uncertainty = 4.343 * (1 + s) / (max(s, 1e-6) * math.sqrt(max(d.dof, 1.0)))
    return (
        Parameter(
            id="center_frequency",
            name="Centre frequency",
            value=d.centre,
            unit="cycles/sample",
            uncertainty=0.5 / d.nfft,
            level=EvidenceLevel.ESTIMATED,
            method="Detection band centre (dsp.detect)",
            evidence=(
                f"Found at FFT size {d.nfft}, significance {d.score:.1f} (-log10 p) over "
                f"{d.cells} cells.",
            ),
        ),
        Parameter(
            id="bandwidth",
            name="Bandwidth",
            value=d.bandwidth,
            unit="cycles/sample",
            uncertainty=1.0 / d.nfft,
            level=EvidenceLevel.ESTIMATED,
            method="Detection band edges (dsp.detect)",
        ),
        Parameter(
            id="start_sample",
            name="Start",
            value=d.start,
            unit="samples",
            uncertainty=time_uncertainty,
            level=EvidenceLevel.ESTIMATED,
            method="Time-edge refinement (dsp.detect.refine_time)",
        ),
        Parameter(
            id="stop_sample",
            name="Stop",
            value=d.stop,
            unit="samples",
            uncertainty=time_uncertainty,
            level=EvidenceLevel.ESTIMATED,
            method="Time-edge refinement (dsp.detect.refine_time)",
        ),
        Parameter(
            id="snr_db",
            name="SNR (detector statistic)",
            value=d.snr_db,
            unit="dB",
            uncertainty=snr_uncertainty,
            level=EvidenceLevel.ESTIMATED,
            method="Mean cell power over the noise floor (dsp.detect)",
            warnings=(
                "Biased upward near the significance threshold; not the same as an Es/N0 "
                "estimate (dsp.estimate.snr_psd, once run on this signal's channelised "
                "samples).",
                *image_warning,
            ),
        ),
    )
