"""Streaming Welch spectrograms and PSDs, at several FFT sizes in one pass (PLAN §5 M2).

Frames are Hann-windowed with 50 % overlap; each spectrogram row averages consecutive frames
(Welch), so a row's value in a noise-only bin is the noise density times the mean of K unit
exponentials, K the frames in the row. Rows are sized so a spectrogram never exceeds
MAX_CELLS cells, whatever the recording's length: memory is bounded by the chunk size and
MAX_CELLS, not by the file.

Units: frequencies are in cycles/sample, bins ordered from -0.5 to 0.5 (fftshift). Power is a
density per unit of normalised frequency, scaled so white noise of variance s2 per sample reads
s2 in every bin: |X_k|^2 / sum(w^2). A real-valued recording's spectrum is symmetric, so only
its bins from 0 to 0.5 are kept.

Limits: the last frames of a recording that don't fill a whole frame are not analysed (fewer
than one FFT length of samples).
"""

import math
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray

Float = NDArray[np.float64]

# Cells per spectrogram; rows average more frames when a recording is long.
MAX_CELLS = 1 << 22
# Fewest frames averaged per row, so a row's noise statistics are usable for detection.
MIN_AVERAGE = 8
# Hann with 50 % overlap: adjacent periodograms correlate by rho^2 = 0.028 in a noise bin, so
# K averaged frames have the variance of K / (1 + 2 rho^2) independent ones.
OVERLAP_VARIANCE = 1 + 2 * 0.0278
READ_CHUNK = 1 << 18


def hann(n: int) -> Float:
    return 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n) / n)


@dataclass(frozen=True)
class Grid:
    """How a span of samples is cut into frames and rows for one FFT size."""

    nfft: int
    start: int  # first sample of the span
    frames: int
    rows: int

    @property
    def hop(self) -> int:
        return self.nfft // 2

    @property
    def bounds(self) -> NDArray[np.int64]:
        """Row r holds frames bounds[r] to bounds[r + 1] - 1: every frame is in one row."""
        return (np.arange(self.rows + 1, dtype=np.int64) * self.frames) // self.rows

    def row_span(self, first: int, last: int) -> tuple[int, int]:
        """Samples [start, stop) covered by rows first..last inclusive."""
        b = self.bounds
        start = self.start + int(b[first]) * self.hop
        stop = self.start + (int(b[last + 1]) - 1) * self.hop + self.nfft
        return start, stop


def plan_grid(
    samples: int,
    nfft: int,
    *,
    start: int = 0,
    max_cells: int = MAX_CELLS,
    min_average: int = MIN_AVERAGE,
) -> Grid | None:
    """The grid for `samples` samples, or None if they don't fill min_average frames."""
    hop = nfft // 2
    if samples < nfft:
        return None
    frames = (samples - nfft) // hop + 1
    if frames < min_average:
        return None
    max_rows = max(1, max_cells // nfft)
    per_row = max(min_average, math.ceil(frames / max_rows))
    return Grid(nfft, start, frames, max(1, frames // per_row))


@dataclass(frozen=True)
class Spectrogram:
    grid: Grid
    power: NDArray[np.float32]  # (rows, bins): every frame
    even: NDArray[np.float32]  # (rows, bins): the even-numbered frames only
    odd: NDArray[np.float32]  # (rows, bins): the odd-numbered frames only
    counts: NDArray[np.int64]  # frames averaged in each row
    freqs: Float  # bin centres, cycles/sample
    real_input: bool

    @property
    def nfft(self) -> int:
        return self.grid.nfft

    @property
    def dof(self) -> Float:
        """Per row: the equivalent number of independent periodograms averaged."""
        return self.counts / OVERLAP_VARIANCE

    @property
    def half_dof(self) -> tuple[Float, Float]:
        """Per row: independent periodograms in the even and in the odd frames. Frames of one
        parity don't overlap each other (hop = nfft / 2), so no correction applies."""
        b = self.grid.bounds
        even = (b[1:] + 1) // 2 - (b[:-1] + 1) // 2
        return even.astype(np.float64), (self.counts - even).astype(np.float64)

    def psd(self) -> Float:
        """The Welch PSD over the whole span: every frame weighted equally."""
        weights = self.counts / self.counts.sum()
        return np.asarray(weights @ self.power.astype(np.float64), np.float64)


class _Accumulator:
    """Frames for one FFT size, fed chunk by chunk; holds under one chunk plus a frame."""

    def __init__(self, grid: Grid, real: bool) -> None:
        self.grid = grid
        self.real = real
        self.window = hann(grid.nfft)
        self.norm = float(np.sum(self.window**2))
        self.pending: NDArray[Any] | None = None
        self.next_frame = 0
        self.row_of = np.repeat(np.arange(grid.rows), np.diff(grid.bounds))
        self.sums = np.zeros((2, grid.rows, grid.nfft), np.float64)  # even, odd frames

    def feed(self, chunk: NDArray[Any]) -> None:
        g = self.grid
        buf = chunk if self.pending is None else np.concatenate([self.pending, chunk])
        available = (len(buf) - g.nfft) // g.hop + 1 if len(buf) >= g.nfft else 0
        count = min(available, g.frames - self.next_frame)
        if count > 0:
            frames = sliding_window_view(buf, g.nfft)[:: g.hop][:count]
            spectra = np.fft.fft(frames * self.window, axis=1)
            power = spectra.real**2 + spectra.imag**2
            index = np.arange(self.next_frame, self.next_frame + count)
            for parity in (0, 1):
                mine = index % 2 == parity
                if not mine.any():
                    continue
                rows = self.row_of[index[mine]]
                starts = np.flatnonzero(np.r_[True, rows[1:] != rows[:-1]])
                self.sums[parity, rows[starts]] += np.add.reduceat(power[mine], starts, axis=0)
            self.next_frame += count
        self.pending = buf[count * g.hop :] if count > 0 else buf

    def result(self) -> Spectrogram:
        g = self.grid
        b = g.bounds
        counts = np.diff(b)
        even_n = (b[1:] + 1) // 2 - (b[:-1] + 1) // 2
        odd_n = counts - even_n

        def shaped(sums: Float, n: NDArray[np.int64]) -> Float:
            out = np.fft.fftshift(sums / np.maximum(n, 1)[:, None] / self.norm, axes=1)
            return out[:, keep] if self.real else out

        freqs = np.fft.fftshift(np.fft.fftfreq(g.nfft))
        keep = freqs >= 0
        total = self.sums[0] + self.sums[1]
        return Spectrogram(
            g,
            shaped(total, counts).astype(np.float32),
            shaped(self.sums[0], even_n).astype(np.float32),
            shaped(self.sums[1], odd_n).astype(np.float32),
            counts,
            freqs[keep] if self.real else freqs,
            self.real,
        )


def spectrograms(
    chunks: Iterable[NDArray[Any]],
    grids: Sequence[Grid],
    *,
    real: bool,
) -> list[Spectrogram]:
    """One Welch spectrogram per grid from one pass over the chunks (which must start at each
    grid's `start` and run consecutively)."""
    accumulators = [_Accumulator(g, real) for g in grids]
    for chunk in chunks:
        for acc in accumulators:
            if acc.next_frame < acc.grid.frames:
                acc.feed(chunk)
        if all(acc.next_frame >= acc.grid.frames for acc in accumulators):
            break
    return [acc.result() for acc in accumulators]


def read_span(source: Any, start: int, stop: int, chunk: int = READ_CHUNK) -> Iterator[Any]:
    """Consecutive chunks of samples [start, stop) from a reader."""
    for s in range(start, stop, chunk):
        yield source.read(s, min(chunk, stop - s))


def _welch_nfft(n_samples: int, nfft: int) -> int:
    """The FFT size `welch(x, nfft)` actually uses for `n_samples` samples: `nfft`, clipped down
    for a short `x` so it still gets at least one frame. `welch_dof`, `welch_freqs` and `welch`
    itself all clip the same way, so a caller's `freqs` axis always matches its `psd` in length.
    """
    return min(nfft, 1 << max(3, int(math.log2(max(n_samples, 8)))))


def welch_dof(n_samples: int, nfft: int) -> float:
    """The degrees of freedom `welch(x, nfft)` averages into each bin, for `n_samples` samples:
    the frames a `welch` call folds into its one row, corrected for their 50 % overlap."""
    nfft = _welch_nfft(n_samples, nfft)
    grid = plan_grid(n_samples, nfft, min_average=1, max_cells=nfft)
    if grid is None:
        raise ValueError(f"{n_samples} samples are too few for a {nfft}-point PSD")
    return grid.frames / OVERLAP_VARIANCE


def welch_freqs(n_samples: int, nfft: int, real: bool) -> Float:
    """The frequency axis (cycles/sample, fftshifted) matching `welch(x, nfft)`'s bins for an
    `x` of `n_samples` samples: build this instead of reconstructing it from `len(psd)`, which
    silently mismatches for real input (see `welch`) or a `nfft` clipped down for a short `x`.
    """
    nfft = _welch_nfft(n_samples, nfft)
    freqs = np.fft.fftshift(np.fft.fftfreq(nfft))
    return freqs[freqs >= 0] if real else freqs


def welch(x: NDArray[Any], nfft: int) -> Float:
    """Welch PSD of samples in memory, fftshifted, in the module's density units.

    Real input gets only its non-negative frequencies (see `spectrograms`); a real signal's
    negative-frequency half carries no separate information, and folding it in as if it were
    complex would double the measured bandwidth and centre it on 0 Hz instead of the signal.
    Build the matching frequency axis with `welch_freqs`, not `fftfreq(len(psd))` - a real
    result is shorter than `nfft`, and `nfft` itself may have been clipped down.
    """
    real = not np.iscomplexobj(x)
    nfft = _welch_nfft(len(x), nfft)
    grid = plan_grid(len(x), nfft, min_average=1, max_cells=nfft)
    if grid is None:
        raise ValueError(f"{len(x)} samples are too few for a {nfft}-point PSD")
    return spectrograms([x], [grid], real=real)[0].psd()
