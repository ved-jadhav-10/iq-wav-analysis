"""The compiled and threaded kernels of the decode chain give exactly what the plain NumPy
formulations they replaced give: same hits, same rates, same windows, same samples, in any
thread order. The references here are the straightforward versions."""

import threading
from typing import Any

import numpy as np
import pytest
from numpy.lib.stride_tricks import sliding_window_view

from dsp import parallel, sync
from dsp.blind_framing import _autocorrelation_peaks  # pyright: ignore[reportPrivateUsage]
from dsp.fec.viterbi import (
    K7_R12,
    ConvCode,
    syndrome_bits,
    syndrome_rates,
    syndrome_rates_at,
)
from dsp.framing import MAX_SYNC_ERRORS, SYNC_WORDS, SyncWord, sync_hits
from dsp.gf2.soft import reliable_window_matrix


def _hits_by_correlation(
    bits: np.ndarray, word: SyncWord, max_errors: int
) -> tuple[np.ndarray, np.ndarray]:
    pm = 1.0 - 2.0 * bits.astype(np.float64)
    ref = 1.0 - 2.0 * word.bits().astype(np.float64)
    c = np.correlate(pm, ref, mode="valid")
    need = word.width - 2 * max_errors
    return np.flatnonzero(c >= need), np.flatnonzero(c <= -need)


def test_sync_hits_match_the_correlation_for_every_word_width_and_error_budget() -> None:
    rng = np.random.default_rng(1)
    words = (
        *SYNC_WORDS,
        SyncWord("wide", 0xDEADBEEFCAFEBABE, 64),
        SyncWord("short", 0x1FF, 9),
        SyncWord("narrow", 0x15, 5),
    )
    for trial in range(60):
        n = int(rng.integers(0, 4000))
        bits = rng.integers(0, 2, n, dtype=np.uint8)
        for word in words:
            if trial % 2 == 0:  # plant noisy copies of the word, upright and inverted
                for pos in rng.integers(0, max(1, n), 4):
                    if pos + word.width <= n:
                        copy = word.bits()
                        for flip in rng.integers(0, word.width, int(rng.integers(0, 5))):
                            copy[flip] ^= 1
                        bits[pos : pos + word.width] = copy ^ int(rng.integers(0, 2))
            for errors in (0, MAX_SYNC_ERRORS, 6):
                got = sync_hits(bits, word, errors)
                if n < word.width:
                    assert len(got[0]) == len(got[1]) == 0
                    continue
                expected = _hits_by_correlation(bits, word, errors)
                assert np.array_equal(got[0], expected[0])
                assert np.array_equal(got[1], expected[1])


def test_sync_hits_on_values_other_than_bits_take_the_correlation_path() -> None:
    bits = np.array([0, 1, 2, 1, 0, 1, 1, 0] * 8, np.uint8)
    word = SyncWord("w", 0b01101, 5)
    got = sync_hits(bits, word, 1)
    expected = _hits_by_correlation(bits, word, 1)
    assert np.array_equal(got[0], expected[0]) and np.array_equal(got[1], expected[1])


def _rates_by_syndrome_bits(hard: np.ndarray, code: ConvCode) -> np.ndarray:
    s = syndrome_bits(hard, code)
    return s.mean(axis=1) if s.shape[1] else np.full(len(hard), 0.5)


CODES = (
    K7_R12,
    ConvCode("K=3", 3, (0o7, 0o5)),
    ConvCode("K=9", 9, (0o753, 0o561)),
    ConvCode("K=15", 15, (0o46321, 0o51271)),
)


def test_syndrome_rates_match_the_syndrome_bits_mean_for_every_row_length() -> None:
    rng = np.random.default_rng(2)
    for _ in range(80):
        rows, width = int(rng.integers(1, 6)), int(rng.integers(0, 90))
        hard = (rng.random((rows, width)) < rng.random()).astype(np.uint8)
        for code in CODES:
            assert np.array_equal(syndrome_rates(hard, code), _rates_by_syndrome_bits(hard, code))


def test_syndrome_rates_read_rows_out_of_a_stream_without_building_them() -> None:
    rng = np.random.default_rng(3)
    flat = rng.integers(0, 2, 5000, dtype=np.uint8)
    for _ in range(40):
        within = rng.integers(0, 1000, int(rng.integers(1, 300)))
        offsets = rng.integers(0, 3000, int(rng.integers(1, 20)))
        rows = flat[offsets[:, None] + within[None, :]]
        assert np.array_equal(
            syndrome_rates_at(flat, 0, K7_R12, offsets, within),
            _rates_by_syndrome_bits(rows, K7_R12),
        )


def test_reliable_windows_match_the_row_minimum_with_ties_and_nan() -> None:
    rng = np.random.default_rng(5)
    for trial in range(120):
        n, width = int(rng.integers(100, 2000)), int(rng.integers(2, 15))
        stride, offset = int(rng.choice([1, 2, 3])), int(rng.integers(0, 5))
        x = rng.standard_normal(n)
        if trial % 3 == 0:
            x = np.round(x * 2) / 2  # many equal reliabilities: the stable order decides
        if trial % 7 == 0:
            x[rng.integers(0, n, 5)] = np.nan
        keep = width + 30
        windows = sliding_window_view(x[offset:], width)[::stride]
        if keep > len(windows):
            continue
        weakest = np.abs(windows).min(axis=1)
        order = np.argsort(-weakest, kind="stable")[:keep]
        expected = np.ascontiguousarray((windows[order] < 0).astype(np.uint8))
        got = reliable_window_matrix(x, width, stride=stride, offset=offset, keep=keep)
        assert np.array_equal(got, expected)


def _peaks_by_scan(z: np.ndarray, lags: np.ndarray) -> list[tuple[float, int]]:
    above = np.flatnonzero(z >= 5.0)
    peaks: list[tuple[float, int]] = []
    for i in above[np.argsort(-z[above], kind="stable")]:
        if all(abs(int(lags[i]) - lag) > 2 for _, lag in peaks):
            peaks.append((float(z[i]), int(lags[i])))
    return peaks


def test_autocorrelation_peaks_keep_the_strongest_of_each_neighbourhood() -> None:
    rng = np.random.default_rng(6)
    bits = rng.integers(0, 2, 40000, dtype=np.uint8)
    period = 311
    for k in range(0, len(bits) - period, period):  # a repeating 48-bit header
        bits[k : k + 48] = 1
    peaks = _autocorrelation_peaks(bits)
    assert peaks and peaks[0][1] % period in (0, 1, period - 1)
    # neighbours within 2 lags of a kept peak never appear, and peaks come strongest first
    lags = [lag for _, lag in peaks]
    assert all(abs(a - b) > 2 for i, a in enumerate(lags) for b in lags[:i])
    assert [z for z, _ in peaks] == sorted((z for z, _ in peaks), reverse=True)
    # a dense pile of peaks agrees with the plain scan
    z = rng.standard_normal(3000) * 3
    lag_axis = np.arange(24, 24 + len(z))
    taken = np.zeros(int(lag_axis[-1]) + 3, bool)
    got: list[tuple[float, int]] = []
    for i in np.flatnonzero(z >= 5.0)[np.argsort(-z[z >= 5.0], kind="stable")]:
        lag = int(lag_axis[i])
        if not taken[lag]:
            got.append((float(z[i]), lag))
            taken[max(0, lag - 2) : lag + 3] = True
    assert got == _peaks_by_scan(z, lag_axis)


def test_interpolation_is_the_same_whatever_the_chunking_and_thread_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rng = np.random.default_rng(7)
    x = rng.standard_normal(20000) + 1j * rng.standard_normal(20000)
    cases = ((1.0, True), (0.37, True), (4.7, True), (4.0, False))
    outputs: list[list[Any]] = []
    for chunk, workers in ((1 << 19, 8), (200, 8), (64, 1), (1 << 30, 4)):
        monkeypatch.setattr(sync, "INTERPOLATE_CHUNK_ELEMENTS", chunk)
        monkeypatch.setattr(parallel, "workers", lambda w=workers: w)
        run: list[Any] = []
        for step, anti_alias in cases:
            times = np.arange(0, len(x) - 40, step) + 0.123
            run.append(sync.interpolate(x, times, anti_alias=anti_alias))
        outputs.append(run)
    for other in outputs[1:]:
        for a, b in zip(outputs[0], other, strict=True):
            assert np.array_equal(a, b)


def test_pmap_keeps_the_order_and_does_not_deadlock_when_nested() -> None:
    names: set[str] = set()

    def inner(i: int) -> int:
        names.add(threading.current_thread().name)
        return i * i

    def outer(i: int) -> list[int]:
        return parallel.pmap(inner, range(i))  # runs serially on a pool thread

    assert parallel.pmap(inner, range(50)) == [i * i for i in range(50)]
    assert parallel.pmap(outer, range(6)) == [[j * j for j in range(i)] for i in range(6)]
    assert parallel.pmap(inner, []) == []


def test_pmap_raises_what_a_cell_raises() -> None:
    def boom(i: int) -> int:
        if i == 3:
            raise ValueError("cell 3")
        return i

    with pytest.raises(ValueError, match="cell 3"):
        parallel.pmap(boom, range(8))
