"""Soft-decision Viterbi decoding of rate-1/n convolutional codes (PLAN M5).

Conventions match `dsp.synth.fec.Convolutional`: generators are octal as the standards write
them, the most significant tap multiplies the newest input bit, and the output interleaves the
branches (g0, g1, ... per input bit). Soft inputs are LLRs with a positive value meaning bit 0.

The decoder starts mid-stream: every state begins equally likely, and the best final state is
taken, so a recording that starts inside a coded stream decodes after a few constraint lengths.
"""

from dataclasses import dataclass

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


def _outputs(code: ConvCode) -> NDArray[np.int64]:
    """For each register value (newest bit at the top), the n output bits packed per branch."""
    k = code.constraint
    table = np.zeros((1 << k, code.n), np.int64)
    for reg in range(1 << k):
        for b, g in enumerate(code.generators):
            table[reg, b] = bin(reg & g).count("1") & 1
    return table


@numba.njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def _viterbi(
    llr: Float, outputs: NDArray[np.int64], k: int
) -> tuple[Bits, float]:  # pragma: no cover - compiled
    n = outputs.shape[1]
    states = 1 << (k - 1)
    steps = len(llr) // n
    metric = np.zeros(states)
    new = np.empty(states)
    decisions = np.empty((steps, states), np.uint8)
    for t in range(steps):
        base = t * n
        for ns in range(states):
            best = -np.inf
            choice = 0
            for b in range(2):
                reg = (ns << 1) | b
                prev = reg & (states - 1)
                m = metric[prev]
                for j in range(n):
                    if outputs[reg, j]:
                        m -= llr[base + j]
                    else:
                        m += llr[base + j]
                if m > best:
                    best = m
                    choice = b
            new[ns] = best
            decisions[t, ns] = choice
        top = new.max()
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


def syndrome_rates(hard: NDArray[np.uint8], code: ConvCode = K7_R12) -> Float:
    """`syndrome_rate` for each row of `hard` (rows x bits) at once."""
    s = syndrome_bits(hard, code)
    return s.mean(axis=1) if s.shape[1] else np.full(len(hard), 0.5)


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
