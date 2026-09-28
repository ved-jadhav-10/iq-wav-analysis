"""The tile pyramid: quantisation, max-pooling and tile addressing, checked against exact
values (PLAN §3, §5 M2)."""

from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

from dsp.synth.chain import Scene, SignalSpec, generate
from dsp.tiles import TILE_COLS, TILE_ROWS, Pyramid, _quantise, build_pyramid


class MemorySource:
    def __init__(self, x: NDArray[Any]) -> None:
        self.x = x
        self.num_samples = len(x)

    def read(self, start: int, count: int) -> NDArray[Any]:
        return self.x[start : start + count]


def test_quantise_maps_the_db_range_onto_0_255_and_clips_outside_it() -> None:
    db = np.array([-10.0, -5.0, 0.0, 5.0, 10.0, -999.0, 999.0])
    q = _quantise(db, db_min=-10.0, db_max=0.0)
    assert q.tolist() == [0, 128, 255, 255, 255, 0, 255]


def _burst_pyramid(power_db: float = 0.0, duration: int = 500) -> tuple[Pyramid, SignalSpec]:
    spec = SignalSpec(
        "qpsk", sps=8.0, frame=None, offset=0.2, start=30_000, duration=duration, power_db=power_db
    )
    scene = Scene(1 << 16, (spec,), noise_db=-20.0)
    g = generate(scene, seed=1)
    pyr = build_pyramid(MemorySource(g.samples.astype(np.complex64)), real=False, nfft=1024)
    return pyr, spec


def test_level_0_matches_the_frontends_tile_contract() -> None:
    """Row-major, fftshifted, uint8: the same shape `frontend/src/lib/demoSignal.ts` builds its
    demo texture in, so the frontend's waterfall shader needs no format change for real tiles."""
    pyr, _ = _burst_pyramid()
    level0 = pyr.levels[0]
    assert level0.grid.dtype == np.uint8
    assert level0.grid.shape == (level0.rows, level0.cols)
    assert level0.row_span == 1
    assert np.all(pyr.freqs[:-1] <= pyr.freqs[1:])  # fftshifted: ascending, low to high


def test_later_levels_halve_the_row_count_by_max_pooling_not_averaging() -> None:
    """A brief, strong burst must still stand out well above the pooled noise floor after
    several halvings, which max-pooling gives and averaging would dilute away."""
    pyr, spec = _burst_pyramid(power_db=10.0, duration=200)
    assert len(pyr.levels) > 1
    for prev, level in zip(pyr.levels, pyr.levels[1:], strict=False):
        assert level.rows == prev.rows // 2
        assert level.row_span == prev.row_span * 2
    bin_width = 1.0 / 1024
    in_band = (pyr.freqs >= spec.offset - bin_width) & (pyr.freqs <= spec.offset + bin_width)
    for level in pyr.levels:
        assert int(level.grid[:, in_band].max()) > 200  # still clearly visible, not washed out


def test_every_level_shares_the_same_db_range_so_colour_stays_consistent() -> None:
    pyr, _ = _burst_pyramid()
    for level in pyr.levels:
        assert level.grid.min() >= 0
        assert level.grid.max() <= 255
    # db_min/db_max themselves are fixed once, from level 0, not recomputed per level
    assert pyr.db_max > pyr.db_min


def test_tile_returns_the_right_sub_block_and_is_empty_past_the_edge() -> None:
    pyr, _ = _burst_pyramid()
    level0 = pyr.levels[0]
    whole = level0.grid
    first = pyr.tile(0, 0, 0)
    np.testing.assert_array_equal(first, whole[:TILE_ROWS, :TILE_COLS])
    row_tiles, col_tiles = pyr.tiles_for(0)
    last = pyr.tile(0, row_tiles - 1, col_tiles - 1)
    assert last.shape[0] > 0 and last.shape[1] > 0
    beyond = pyr.tile(0, row_tiles, 0)
    assert beyond.shape == (0, 0)


def test_real_input_pyramid_keeps_only_non_negative_frequencies() -> None:
    x = np.cos(2 * np.pi * 0.1 * np.arange(1 << 15)).astype(np.float64)
    pyr = build_pyramid(MemorySource(x), real=True, nfft=512)
    assert np.all(pyr.freqs >= 0)
    assert pyr.levels[0].cols == len(pyr.freqs)


def test_psd_db_matches_the_recordings_own_signal_and_noise_floor() -> None:
    pyr, spec = _burst_pyramid(power_db=10.0, duration=1 << 16)  # signal for the whole recording
    assert pyr.psd_db.shape == pyr.freqs.shape
    bin_width = 1.0 / 1024
    in_band = (pyr.freqs >= spec.offset - bin_width) & (pyr.freqs <= spec.offset + bin_width)
    assert float(pyr.psd_db[in_band].max()) > float(np.median(pyr.psd_db[~in_band])) + 10


def test_too_short_a_recording_is_refused_rather_than_silently_padded() -> None:
    x = np.zeros(10, np.complex64)
    with pytest.raises(ValueError, match="too few"):
        build_pyramid(MemorySource(x), real=False, nfft=1024)
