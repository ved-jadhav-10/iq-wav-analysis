"""Soft-decision Viterbi decoding of rate-1/n convolutional codes (PLAN M5).

Conventions match `dsp.synth.fec.Convolutional`: generators are octal as the standards write
them, the most significant tap multiplies the newest input bit, and the output interleaves the
branches (g0, g1, ... per input bit). Soft inputs are LLRs with a positive value meaning bit 0.

The decoder starts mid-stream: every state begins equally likely, and the best final state is
taken, so a recording that starts inside a coded stream decodes after a few constraint lengths.
"""

from dataclasses import dataclass
from functools import cache

import numba  # pyright: ignore[reportMissingTypeStubs]
import numpy as np
from numpy.typing import NDArray

Bits = NDArray[np.uint8]
Float = NDArray[np.float64]


@dataclass(frozen=True)
class ConvCode:
    name: str
    constraint: int
    generators: tuple[int, ...]  # octal values, one per output branch

    @property
    def n(self) -> int:
        return len(self.generators)


# K = 7, rate 1/2 (171, 133 octal): CCSDS 131.0-B, DVB-S, IEEE 802.11.
K7_R12 = ConvCode("Conv K=7 r½ (171,133)₈", 7, (0o171, 0o133))


@cache
def _outputs(code: ConvCode) -> NDArray[np.int64]:
    """For each register value (newest bit at the top), the n output bits packed per branch.
    Cached, so read-only: callers share the table."""
    k = code.constraint
    table = np.zeros((1 << k, code.n), np.int64)
    for reg in range(1 << k):
        for b, g in enumerate(code.generators):
            table[reg, b] = bin(reg & g).count("1") & 1
    return table


@numba.njit(cache=True, nogil=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def _viterbi(
    llr: Float, outputs: NDArray[np.int64], k: int
) -> tuple[Bits, float]:  # pragma: no cover - compiled
    n = outputs.shape[1]
    states = 1 << (k - 1)
    steps = len(llr) // n
    # Every branch of a step scores one of 2^n output patterns: score those once per step, then
    # each state only adds a table entry (the per-state loop over the n outputs was the cost).
    patterns = 1 << n
    pattern_of = np.empty(2 * states, np.int64)
    for reg in range(2 * states):
        p = 0
        for j in range(n):
            p |= outputs[reg, j] << j
        pattern_of[reg] = p
    metric = np.zeros(states)
    new = np.empty(states)
    branch = np.empty(patterns)
    decisions = np.empty((steps, states), np.uint8)
    for t in range(steps):
        base = t * n
        for p in range(patterns):
            m = 0.0
            for j in range(n):
                if (p >> j) & 1:
                    m -= llr[base + j]
                else:
                    m += llr[base + j]
            branch[p] = m
        top = -np.inf
        for ns in range(states):
            reg0 = ns << 1
            m0 = metric[reg0 & (states - 1)] + branch[pattern_of[reg0]]
            m1 = metric[(reg0 | 1) & (states - 1)] + branch[pattern_of[reg0 | 1]]
            if m1 > m0:  # ties keep branch 0
                new[ns] = m1
                decisions[t, ns] = 1
            else:
                new[ns] = m0
                decisions[t, ns] = 0
            if new[ns] > top:
                top = new[ns]
        for s in range(states):
            metric[s] = new[s] - top
    state = int(np.argmax(metric))
    out = np.empty(steps, np.uint8)
    for t in range(steps - 1, -1, -1):
        out[t] = state >> (k - 2)
        reg = (state << 1) | decisions[t, state]
        state = reg & (states - 1)
    return out, float(metric.max())


def decode(llr: Float, code: ConvCode = K7_R12) -> Bits:
    """Maximum-likelihood input bits for the soft coded stream `llr` (whole steps only)."""
    bits, _ = _viterbi(np.ascontiguousarray(llr, np.float64), _outputs(code), code.constraint)
    return bits


def syndrome_rate(hard: Bits, code: ConvCode = K7_R12) -> float:
    """The fraction of ones in the rate-1/2 parity syndrome c0 * g1 + c1 * g0 (mod 2), which is
    zero on any codeword: about (w(g0) + w(g1)) x the bit error rate on a correctly aligned
    coded stream, 0.5 on anything else (a misaligned or wrongly deinterleaved one, or noise).
    Inverting every bit keeps it low, since both generators have odd weight."""
    return float(syndrome_rates(np.asarray(hard)[None, :], code)[0])


def syndrome_bits(hard: NDArray[np.uint8], code: ConvCode = K7_R12) -> NDArray[np.uint8]:
    """The parity check of every window of each row of `hard` (rows x bits): rows x windows, 0
    where the window satisfies the code, one window per code step after the first K - 1."""
    if code.n != 2:
        raise ValueError("the parity syndrome is only defined here for rate 1/2")
    k = code.constraint
    steps = hard.shape[1] // 2
    if steps <= k:
        return np.zeros((len(hard), 0), np.uint8)
    c0, c1 = hard[:, 0 : 2 * steps : 2], hard[:, 1 : 2 * steps : 2]
    s = np.zeros((len(hard), steps - k + 1), np.uint8)
    # s[m] = sum_i g1[i] c0[m - i] + g0[i] c1[m - i], taps i = 0 .. k-1 (MSB = newest bit)
    for i in range(k):
        bit = k - 1 - i
        if (code.generators[1] >> bit) & 1:
            s ^= c0[:, k - 1 - i : steps - i]
        if (code.generators[0] >> bit) & 1:
            s ^= c1[:, k - 1 - i : steps - i]
    return s


def _tap_masks(code: ConvCode) -> tuple[int, int]:
    """Bit i of each mask is the tap on the register's i-th newest bit (c0 and c1 registers of
    `syndrome_bits`: the syndrome adds g1's taps on c0 and g0's taps on c1)."""
    k = code.constraint
    m0 = sum(((code.generators[1] >> (k - 1 - i)) & 1) << i for i in range(k))
    m1 = sum(((code.generators[0] >> (k - 1 - i)) & 1) << i for i in range(k))
    return m0, m1


@numba.njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def _parity(x: int) -> int:  # pragma: no cover - compiled
    x ^= x >> 32
    x ^= x >> 16
    x ^= x >> 8
    x ^= x >> 4
    x ^= x >> 2
    x ^= x >> 1
    return x & 1


@numba.njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def _syndrome_ones(
    hard: NDArray[np.uint8],
    offsets: NDArray[np.int64],
    within: NDArray[np.int64],
    k: int,
    m0: int,
    m1: int,
) -> NDArray[np.int64]:  # pragma: no cover - compiled
    """Per offset, the ones among the parity checks of the bits `hard[offset + within]` read as
    code pairs (the checks of `syndrome_bits`, one per step after the first k - 1)."""
    steps = len(within) // 2
    out = np.zeros(len(offsets), np.int64)
    keep = (1 << k) - 1
    for r in range(len(offsets)):
        base = offsets[r]
        r0 = 0
        r1 = 0
        ones = 0
        for t in range(steps):
            r0 = ((r0 << 1) | int(hard[base + within[2 * t]])) & keep
            r1 = ((r1 << 1) | int(hard[base + within[2 * t + 1]])) & keep
            if t >= k - 1:
                ones += _parity(r0 & m0) ^ _parity(r1 & m1)
        out[r] = ones
    return out


def syndrome_rates(hard: NDArray[np.uint8], code: ConvCode = K7_R12) -> Float:
    """`syndrome_rate` for each row of `hard` (rows x bits) at once."""
    width = hard.shape[1]
    return syndrome_rates_at(
        np.ascontiguousarray(hard, np.uint8).ravel(),
        width,
        code,
        np.arange(len(hard), dtype=np.int64) * width,
    )


def syndrome_rates_at(
    flat: NDArray[np.uint8],
    width: int,
    code: ConvCode = K7_R12,
    offsets: NDArray[np.int64] | None = None,
    within: NDArray[np.int64] | None = None,
) -> Float:
    """The syndrome rate of rows read out of `flat`: row r is `flat[offsets[r] + within]`
    (`within` defaults to 0 .. width - 1 and `offsets` to the start of each `width`-bit row),
    without building the rows. The same rates as `syndrome_rates` of those rows."""
    if code.n != 2:
        raise ValueError("the parity syndrome is only defined here for rate 1/2")
    if within is None:
        within = np.arange(width, dtype=np.int64)
    if offsets is None:
        offsets = np.arange(0, len(flat) - width + 1, width, dtype=np.int64)
    steps = len(within) // 2
    if steps <= code.constraint:
        return np.full(len(offsets), 0.5)
    windows = steps - code.constraint + 1
    m0, m1 = _tap_masks(code)
    ones = _syndrome_ones(
        np.ascontiguousarray(flat, np.uint8),
        np.asarray(offsets, np.int64),
        np.asarray(within, np.int64),
        code.constraint,
        m0,
        m1,
    )
    return ones / windows


def encode(bits: NDArray[np.uint8], code: ConvCode = K7_R12) -> Bits:
    """Re-encode from the all-zero state, for re-encode checks."""
    u = np.asarray(bits, np.uint8)
    k = code.constraint
    branches = np.empty((len(u), code.n), np.uint8)
    for b, g in enumerate(code.generators):
        # The most significant tap multiplies the newest bit: tap i is bit k - 1 - i of g.
        taps = np.array([(g >> (k - 1 - i)) & 1 for i in range(k)], np.uint8)
        branches[:, b] = np.convolve(u, taps)[: len(u)] % 2
    return branches.ravel()
