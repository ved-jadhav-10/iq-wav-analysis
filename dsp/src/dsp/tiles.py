"""Multi-resolution STFT tile pyramid: quantised uint8 dB, max-pooled between levels so a
short burst survives zooming out (PLAN §3, §5 M2).

Level 0 is the finest-resolution Welch spectrogram (dsp.spectrum), bounded to a fixed cell
budget regardless of the recording's length, same as detection. Level k+1 halves level k's row
count by max-pooling 2 rows into 1 - never averaging, so a strong but brief burst isn't diluted
into the noise floor as more time is folded into each row. Frequency resolution is the same at
every level: the useful zoom range for a recording is mostly its duration, and blurring
frequency too would lose real resolution the recording's own bandwidth already bounds.

Every level is quantised against the same (`db_min`, `db_max`), fixed from level 0's own
statistics, so the colour mapping doesn't drift between zoom levels. Each level's grid is served
in fixed `TILE_ROWS x TILE_COLS` tiles (`Pyramid.tile`), so a client fetches only the tile it is
looking at, matching the uint8 dB texture the frontend's waterfall shader already expects
(`frontend/src/lib/demoSignal.ts`'s `DemoProducts.tile`: row-major, fftshifted, row 0 at t = 0).
`psd_db` is the same level-0 spectrogram's Welch PSD (every row weighted equally, dsp.spectrum's
`Spectrogram.psd`), so a PSD plot alongside the waterfall needs no second pass over the file.
"""

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from dsp.spectrum import Grid, plan_grid, read_span, spectrograms

Uint8Grid = NDArray[np.uint8]
Float = NDArray[np.float64]

TILE_ROWS = 256
TILE_COLS = 256
MIN_ROWS = 8  # stop pooling once a level would have fewer rows than this
DB_FLOOR_OFFSET = 6.0  # dB below the measured noise floor: db_min, matching the demo convention
DB_FLOOR_RANK = 20.0  # percentile of the spectrogram taken as the noise floor for db_min
DB_EPSILON = 1e-12
DEFAULT_NFFT = 1024


@dataclass(frozen=True)
class Level:
    rows: int
    cols: int
    grid: Uint8Grid  # rows x cols, uint8-quantised dB
    row_span: int  # level-0 rows folded into one row at this level (1 at level 0)


@dataclass(frozen=True)
class Pyramid:
    levels: tuple[Level, ...]  # level 0 finest; later levels progressively pooled in time
    freqs: Float  # cycles/sample, one per column, the same at every level
    psd_db: Float  # the whole recording's Welch PSD, one value per column, in dB
    db_min: float
    db_max: float
    samples: int
    grid: Grid  # level 0's time/frequency grid, for mapping a tile back to sample indices

    def tile(self, level: int, row_tile: int, col_tile: int) -> Uint8Grid:
        """The tile at (level, row_tile, col_tile); empty (but valid) past a level's edge."""
        lv = self.levels[level]
        r0, r1 = row_tile * TILE_ROWS, min(lv.rows, (row_tile + 1) * TILE_ROWS)
        c0, c1 = col_tile * TILE_COLS, min(lv.cols, (col_tile + 1) * TILE_COLS)
        if r0 >= lv.rows or c0 >= lv.cols:
            return np.zeros((0, 0), np.uint8)
        return lv.grid[r0:r1, c0:c1]

    def tiles_for(self, level: int) -> tuple[int, int]:
        """(row tiles, column tiles) a level needs to cover it fully."""
        lv = self.levels[level]
        return math.ceil(lv.rows / TILE_ROWS), math.ceil(lv.cols / TILE_COLS)


def _quantise(power_db: Float, db_min: float, db_max: float) -> Uint8Grid:
    span = max(db_max - db_min, DB_EPSILON)
    scaled = (power_db - db_min) / span * 255.0
    return np.clip(np.round(scaled), 0, 255).astype(np.uint8)


def _to_db(power: Float) -> Float:
    return np.asarray(10 * np.log10(np.maximum(power, DB_EPSILON)), np.float64)


def build_pyramid(source: Any, *, real: bool, nfft: int = DEFAULT_NFFT) -> Pyramid:
    """The whole recording's spectrogram, quantised and pooled into a level-of-detail pyramid.

    `source` is streamed once (`dsp.spectrum.read_span`); memory is bounded by the spectrogram's
    own cell budget (`dsp.spectrum.plan_grid`'s default `MAX_CELLS`), independent of how long the
    recording is - the same design detection uses (PLAN §2 Scale).
    """
    samples = int(source.num_samples)
    grid = plan_grid(samples, nfft)
    if grid is None:
        raise ValueError(f"{samples} samples are too few for a {nfft}-point spectrogram")
    spec = spectrograms(read_span(source, 0, samples), [grid], real=real)[0]
    power = spec.power.astype(np.float64)
    power_db = _to_db(power)
    noise_floor_db = float(np.percentile(power_db, DB_FLOOR_RANK))
    db_min = math.floor(noise_floor_db - DB_FLOOR_OFFSET)
    db_max = math.ceil(float(np.max(power_db)))

    levels = [Level(power_db.shape[0], power_db.shape[1], _quantise(power_db, db_min, db_max), 1)]
    pooled = power
    row_span = 1
    while levels[-1].rows > MIN_ROWS and pooled.shape[0] >= 2:
        rows = pooled.shape[0] - pooled.shape[0] % 2
        pooled = pooled[:rows].reshape(rows // 2, 2, -1).max(axis=1)
        row_span *= 2
        db = _quantise(_to_db(pooled), db_min, db_max)
        levels.append(Level(pooled.shape[0], pooled.shape[1], db, row_span))
    psd_db = _to_db(spec.psd())
    return Pyramid(tuple(levels), spec.freqs, psd_db, db_min, db_max, samples, spec.grid)
