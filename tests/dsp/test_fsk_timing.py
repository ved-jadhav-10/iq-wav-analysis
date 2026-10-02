"""FSK timing on inputs with no timing to find (PLAN M3): a pure-noise channel whose few timing
blocks disagree must be refused as too inconsistent, never reported as a NaN jitter. The null
bench found this: `Parameter` rejects NaN, so the whole chain run raised."""

import numpy as np
import pytest

from dsp import fsk

# Noise inputs (seed, samples, symbols per sample) whose timing blocks all disagree with the median:
# before the fix each gave a NaN jitter.
DISAGREEING = [(54, 8278, 1 / 16), (73, 16920, 1 / 32), (149, 8250, 1 / 16)]


def noise(seed: int, n: int) -> np.ndarray:
    """Unit noise; the generator first draws a length, as the search that found these did."""
    rng = np.random.default_rng(seed)
    rng.integers(3000, 20000)
    return rng.standard_normal(n) + 1j * rng.standard_normal(n)


@pytest.mark.parametrize(("seed", "n", "rate"), DISAGREEING)
def test_blocks_that_disagree_are_refused_not_nan(seed: int, n: int, rate: float) -> None:
    with pytest.raises(ValueError, match="no timing block agrees"):
        fsk.demodulate(noise(seed, n), rate)


def test_noise_never_gives_a_non_finite_jitter() -> None:
    for seed in range(60):
        x = noise(seed, 3000 + 317 * seed)
        try:
            symbols = fsk.demodulate(x, 1 / 16)
        except ValueError:
            continue  # too few symbols, or no consistent timing
        assert np.isfinite(symbols.jitter)
