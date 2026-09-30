"""The soft demapper against the generator's mapper, and its hard decisions against the theoretical
bit error rate of each modulation on AWGN (PLAN M3's gate: within 1 dB of theory)."""

import math

import numpy as np
import pytest

from dsp.demod import BITS_PER_SYMBOL, ORDERS, demap, ideal_points, rotations
from dsp.synth.modulate import map_bits

MODULATIONS = list(BITS_PER_SYMBOL)


def q(x: float) -> float:
    return 0.5 * math.erfc(x / math.sqrt(2))


def theory_ber(modulation: str, esn0_db: float) -> float:
    """Bit error rate with Gray labels on AWGN, symbol energy 1 (the usual closed forms; the
    8-PSK one is the standard nearest-neighbour approximation)."""
    esn0 = 10 ** (esn0_db / 10)
    if modulation == "BPSK":
        return q(math.sqrt(2 * esn0))
    if modulation == "QPSK":
        return q(math.sqrt(esn0))
    if modulation == "8PSK":
        return 2 * q(math.sqrt(2 * esn0) * math.sin(math.pi / 8)) / 3
    m = 1 << BITS_PER_SYMBOL[modulation]
    k = BITS_PER_SYMBOL[modulation]
    return 4 / k * (1 - 1 / math.sqrt(m)) * q(math.sqrt(3 * esn0 / (m - 1)))


def measured_ber(modulation: str, esn0_db: float, symbols: int = 200_000) -> float:
    k = BITS_PER_SYMBOL[modulation]
    rng = np.random.default_rng(k * 1000 + int(esn0_db))
    bits = rng.integers(0, 2, symbols * k, dtype=np.uint8)
    x = map_bits(bits, modulation.lower())
    sigma = math.sqrt(10 ** (-esn0_db / 10) / 2)
    noise = sigma * (rng.normal(size=symbols) + 1j * rng.normal(size=symbols))
    hard = (demap(x + noise, modulation).llr < 0).astype(np.uint8)
    return float(np.mean(hard != bits))


@pytest.mark.parametrize("modulation", MODULATIONS)
def test_the_demapper_inverts_the_generators_mapper_and_points_have_unit_power(
    modulation: str,
) -> None:
    k = BITS_PER_SYMBOL[modulation]
    bits = np.random.default_rng(k).integers(0, 2, 600 * k, dtype=np.uint8)
    x = map_bits(bits, modulation.lower())
    assert np.array_equal((demap(x, modulation).llr < 0).astype(np.uint8), bits)
    assert np.mean(np.abs(ideal_points(modulation)) ** 2) == pytest.approx(1.0)
    assert len(rotations(modulation)) == ORDERS[modulation]


@pytest.mark.parametrize(
    ("modulation", "esn0_db"),
    [("BPSK", 6.0), ("QPSK", 9.0), ("8PSK", 13.0), ("16QAM", 15.0), ("64QAM", 21.0)],
)
def test_the_bit_error_rate_is_within_one_db_of_theory(modulation: str, esn0_db: float) -> None:
    ber = measured_ber(modulation, esn0_db)
    # Theory at 1 dB more SNR is a lower rate, at 1 dB less a higher one; the measurement must
    # sit between them (a demapper worse than 1 dB would fall above the upper bound).
    assert theory_ber(modulation, esn0_db + 1) <= ber <= theory_ber(modulation, esn0_db - 1)
    assert ber > 0  # a rate this low still has errors: the test is measuring something
