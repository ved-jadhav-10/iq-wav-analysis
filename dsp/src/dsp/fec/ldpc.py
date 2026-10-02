"""Standard LDPC codes: a catalogue of published parity-check matrices, a systematic encoder and
a soft-decision decoder (PLAN M5).

The catalogue holds the codes a blind search can try by name: IEEE 802.11n (n = 648, rates 1/2,
2/3, 3/4, 5/6), the CCSDS TC codes (128, 64), (256, 128), (512, 256) and the CCSDS TM (AR4JA)
codes at rates 1/2, 2/3 and 4/5 for k = 1024 and 4096. The numbers are in `ldpc_data` (extracted
mechanically from two MIT-licensed implementations, not compared with the standards' own tables);
the matrices are built here from them.

Conventions, matching `dsp.fec.viterbi`: an LLR is positive for bit 0 (hard bit = LLR < 0). A
code word is systematic, the message in the first `k` columns of H. Codes with `punctured` > 0
(the CCSDS TM codes) never transmit their last `punctured` columns: the decoder takes the
transmitted length and re-inserts those as LLR 0 (an erasure) and returns all `n` bits.

The decoder is layered normalised min-sum in Numba: each check in turn replaces its messages and
updates the variable posteriors at once, which converges in about half the iterations of the
flooding schedule, and stops as soon as every check holds. Encoding solves H c = 0 for the
parity columns through `dsp.gf2` (the one elimination routine), once per code.
"""

from dataclasses import dataclass
from functools import cache, cached_property
from statistics import NormalDist

import numba  # pyright: ignore[reportMissingTypeStubs]
import numpy as np
from numpy.typing import ArrayLike, NDArray

from dsp.fec import ldpc_data
from dsp.gf2 import pack, rref, unpack

Bits = NDArray[np.uint8]
Float = NDArray[np.float64]
Index = NDArray[np.int32]

SCREEN_ITER = 5  # decode iterations per offset in a punctured code's alignment screen
CANDIDATES = 8  # offsets a punctured code's screen decodes in full
NORMALISATION = 0.8  # min-sum scaling; 0.75 to 0.85 is within 0.1 dB of belief propagation
# A demodulator dividing by a zero variance gives +-inf or NaN: +-inf becomes this large finite LLR.
LLR_CLIP = 1e6
# A block with fewer informative (finite, nonzero) LLRs than this fraction never "converges".
MIN_USABLE = 0.5
# The unpunctured alignment screen: windows of the stream it scans (evenly spaced), the offsets of
# a window whose full soft syndrome is computed (after a cheaper pass on a third of the checks, for
# codes at least COARSE_FROM long), the offsets of a window that go into the candidate pool (a
# quasi-cyclic code's neighbouring offsets score high), the candidates decoded, and the
# false-alarm budget of the soft-syndrome gate over all windows x offsets.
MAX_WINDOWS = 8
REFINE = 16
COARSE_FROM = 512
PER_WINDOW = 4
MAX_DECODES = 8
GATE_ALPHA = 0.1
# A window whose hard bits are more constant than this fraction, or repeat with a period up to
# MAX_PERIOD at this agreement, carries no alignment (the all-zero word fits every offset).
MIN_MINORITY = 0.05
MAX_PERIOD = 64
PERIODIC = 0.9


@dataclass(frozen=True, eq=False)
class LdpcCode:
    """A code's parity-check matrix H (`checks` x `n`) as a sparse edge list sorted by row."""

    name: str
    family: str
    n: int  # columns of H: the full code word, punctured columns included
    k: int  # message bits: n - rank H, the first k columns
    punctured: int  # trailing columns of the code word that are never transmitted
    source: str
    rows: Index  # the check of each edge (row of H), non-decreasing
    cols: Index  # the variable (column of H) of each edge

    @property
    def transmitted(self) -> int:
        return self.n - self.punctured

    @cached_property
    def pointers(self) -> Index:
        """CSR row pointers: the edges of check c are `pointers[c]:pointers[c + 1]`."""
        counts = np.bincount(self.rows)
        return np.concatenate([[0], np.cumsum(counts)]).astype(np.int32)

    @property
    def checks(self) -> int:
        return len(self.pointers) - 1

    @cached_property
    def row_weights(self) -> NDArray[np.int64]:
        return np.diff(self.pointers).astype(np.int64)

    @cached_property
    def column_weights(self) -> NDArray[np.int64]:
        return np.bincount(self.cols, minlength=self.n).astype(np.int64)

    def dense(self) -> Bits:
        """H as a checks x n array of 0/1."""
        h = np.zeros((self.checks, self.n), np.uint8)
        h[self.rows, self.cols] = 1
        return h

    @cached_property
    def rank(self) -> int:
        """The GF(2) rank of H (so `n - rank` is the dimension of the code); computed once."""
        return len(rref(pack(self.dense()), self.n)[1])

    def __repr__(self) -> str:
        return f"LdpcCode({self.name!r}, n={self.n}, k={self.k}, punctured={self.punctured})"


def _edges(h_rows: list[Index], h_cols: list[Index], n: int) -> tuple[Index, Index]:
    """Sorted edges of the GF(2) sum of the given entry lists (a repeated entry cancels)."""
    key = np.concatenate(h_rows).astype(np.int64) * n + np.concatenate(h_cols)
    unique, counts = np.unique(key, return_counts=True)
    odd = unique[counts % 2 == 1]
    return (odd // n).astype(np.int32), (odd % n).astype(np.int32)


def _ieee_80211n(rate: str) -> LdpcCode:
    base = ldpc_data.IEEE_802_11N_648[rate]
    z = ldpc_data.IEEE_802_11N_648_Z
    block_cols = len(base[0])
    n = block_cols * z
    i = np.arange(z)
    rows: list[Index] = []
    cols: list[Index] = []
    for r, line in enumerate(base):
        for c, shift in enumerate(line):
            if shift >= 0:  # row i of the block has its one in column (i + shift) mod z
                rows.append((r * z + i).astype(np.int32))
                cols.append((c * z + (i + shift) % z).astype(np.int32))
    edge_rows, edge_cols = _edges(rows, cols, n)
    k = n - len(base) * z
    return LdpcCode(
        f"IEEE 802.11n n=648 r{rate}",
        "IEEE 802.11n",
        n,
        k,
        0,
        f"IEEE 802.11-2020 Annex F, n = 648, Z = 27, rate {rate} "
        "(numbers extracted from yairmz/ldpc, MIT)",
        edge_rows,
        edge_cols,
    )


def _ccsds_tc(n: int) -> LdpcCode:
    blocks = ldpc_data.CCSDS_TC[n]
    m = n // 8
    i = np.arange(m)
    rows: list[Index] = []
    cols: list[Index] = []
    for r, line in enumerate(blocks):
        for c, shifts in enumerate(line):
            for shift in shifts:
                rows.append((r * m + i).astype(np.int32))
                cols.append((c * m + (i + shift) % m).astype(np.int32))
    edge_rows, edge_cols = _edges(rows, cols, n)
    return LdpcCode(
        f"CCSDS TC n={n} k={n // 2}",
        "CCSDS TC",
        n,
        n - 4 * m,
        0,
        f"CCSDS 231.1-O-1, ({n}, {n // 2}) (numbers extracted from labrador-ldpc, MIT)",
        edge_rows,
        edge_cols,
    )


def _tm_permutation(k: int, m: int) -> Index:
    """pi_k(i), i = 0 .. M-1 (CCSDS 131.0-B-5 section 7.4.2.4): the column of row i in Pi_k."""
    q = m // 4
    i = np.arange(m)
    j = (4 * i) // m
    theta = ldpc_data.CCSDS_TM_THETA[k - 1]
    phi = np.asarray(ldpc_data.CCSDS_TM_PHI[m], np.int64)[:, k - 1]
    return (q * ((theta + j) % 4) + (phi[j] + i) % q).astype(np.int32)


def _ccsds_tm(k: int, rate: str) -> LdpcCode:
    blocks = ldpc_data.CCSDS_TM[rate]
    info_blocks = {"1/2": 2, "2/3": 4, "4/5": 8}[rate]
    m = k // info_blocks
    block_cols = len(blocks[0])
    n = block_cols * m
    i = np.arange(m, dtype=np.int32)
    rows: list[Index] = []
    cols: list[Index] = []
    for r, line in enumerate(blocks):
        for c, terms in enumerate(line):
            for term in terms:
                rows.append(r * m + i)
                cols.append(c * m + (i if term == 0 else _tm_permutation(term, m)))
    edge_rows, edge_cols = _edges(rows, cols, n)
    return LdpcCode(
        f"CCSDS TM k={k} r{rate}",
        "CCSDS TM",
        n,
        info_blocks * m,
        m,  # the last block column (the protograph's degree-6 variable node) is punctured
        f"CCSDS 131.0-B-5 section 7, k = {k}, rate {rate}, M = {m}; the last M columns are "
        "not transmitted (numbers extracted from labrador-ldpc, MIT)",
        edge_rows,
        edge_cols,
    )


def _catalogue() -> tuple[LdpcCode, ...]:
    codes = [_ieee_80211n(rate) for rate in ("1/2", "2/3", "3/4", "5/6")]
    codes += [_ccsds_tc(n) for n in (128, 256, 512)]
    codes += [_ccsds_tm(k, rate) for k in (1024, 4096) for rate in ("1/2", "2/3", "4/5")]
    return tuple(codes)


CATALOGUE: tuple[LdpcCode, ...] = _catalogue()


def by_name(name: str) -> LdpcCode:
    for code in CATALOGUE:
        if code.name == name:
            return code
    raise KeyError(f"no catalogued LDPC code named {name!r}")


# -- encoding ------------------------------------------------------------------------------------


@cache
def _parity_map(code: LdpcCode) -> tuple[NDArray[np.int64], NDArray[np.float32]]:
    """(positions of the parity columns, a k x parity matrix P) with parity = message P mod 2.

    Eliminating from the right (the columns reversed) puts the pivots, which are the parity
    columns, last; the standard codes then leave exactly the first k columns free.
    """
    n = code.n
    reduced, pivots = rref(pack(code.dense()[:, ::-1]), n)
    if len(pivots) != n - code.k:
        raise ValueError(f"{code.name}: H has rank {len(pivots)}, expected {n - code.k}")
    parity = (n - 1 - pivots).astype(np.int64)
    free = np.setdiff1d(np.arange(n), parity)
    if not np.array_equal(free, np.arange(code.k)):
        raise ValueError(f"{code.name} is not systematic in its first {code.k} columns")
    dense = unpack(reduced[: len(pivots)], n)
    # float32 so the product runs on BLAS; sums of at most k <= 2^24 ones are exact
    return parity, dense[:, n - 1 - free].T.astype(np.float32)


def encode(code: LdpcCode, bits: ArrayLike, *, full: bool = False) -> Bits:
    """Systematic code words for the messages `bits` (k bits, or rows of k bits).

    The transmitted code word by default; `full=True` keeps the punctured columns too."""
    u = np.atleast_2d(np.asarray(bits, np.uint8))
    if u.shape[-1] != code.k:
        raise ValueError(f"{code.name} takes {code.k}-bit messages, not {u.shape[-1]}")
    parity, matrix = _parity_map(code)
    word = np.empty((len(u), code.n), np.uint8)
    word[:, : code.k] = u
    word[:, parity] = (u.astype(np.float32) @ matrix % 2).astype(np.uint8)
    out = word if full else word[:, : code.transmitted]
    return out[0] if np.ndim(bits) == 1 else out


# -- decoding ------------------------------------------------------------------------------------


@numba.njit(cache=True, nogil=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def _unsatisfied(
    hard: Bits, pointers: Index, variables: Index
) -> int:  # pragma: no cover - compiled
    count = 0
    for c in range(len(pointers) - 1):
        parity = 0
        for e in range(pointers[c], pointers[c + 1]):
            parity ^= int(hard[variables[e]])
        count += parity
    return count


@numba.njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def _min_sum(
    llr: Float,
    pointers: Index,
    variables: Index,
    alpha: float,
    max_iter: int,
    post: Float,
    hard: Bits,
) -> tuple[int, int]:  # pragma: no cover - compiled
    """Layered normalised min-sum on `llr` (length n); `post` and `hard` are n-long work
    arrays. Returns (iterations run, unsatisfied checks of the final hard decisions)."""
    n = len(llr)
    checks = len(pointers) - 1
    msg = np.zeros(len(variables))
    for v in range(n):
        post[v] = llr[v]
        hard[v] = 1 if llr[v] < 0 else 0
    unsat = _unsatisfied(hard, pointers, variables)
    iterations = 0
    while unsat > 0 and iterations < max_iter:
        iterations += 1
        for c in range(checks):
            lo = pointers[c]
            hi = pointers[c + 1]
            min1 = np.inf
            min2 = np.inf
            arg = -1
            negative = 0
            for e in range(lo, hi):
                q = post[variables[e]] - msg[e]
                if q < 0:
                    negative ^= 1
                a = abs(q)
                if a < min1:
                    min2 = min1
                    min1 = a
                    arg = e
                elif a < min2:
                    min2 = a
            if min2 == np.inf:
                min2 = min1
            for e in range(lo, hi):
                v = variables[e]
                q = post[v] - msg[e]
                mag = alpha * (min2 if e == arg else min1)
                new = -mag if (negative ^ (1 if q < 0 else 0)) else mag
                post[v] = q + new
                msg[e] = new
        for v in range(n):
            hard[v] = 1 if post[v] < 0 else 0
        unsat = _unsatisfied(hard, pointers, variables)
    return iterations, unsat


@numba.njit(cache=True, nogil=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def _decode_rows(
    llr: Float,
    pointers: Index,
    variables: Index,
    alpha: float,
    max_iter: int,
    n: int,
) -> tuple[Bits, NDArray[np.int64], NDArray[np.int64]]:  # pragma: no cover - compiled
    """Decode each row of `llr` (rows x width, width <= n; the rest erased) in turn."""
    rows = llr.shape[0]
    width = llr.shape[1]
    hard_out = np.zeros((rows, n), np.uint8)
    iterations = np.zeros(rows, np.int64)
    unsat = np.zeros(rows, np.int64)
    work = np.zeros(n)
    post = np.zeros(n)
    hard = np.zeros(n, np.uint8)
    for r in range(rows):
        work[:] = 0.0
        for v in range(width):
            work[v] = llr[r, v]
        it, bad = _min_sum(work, pointers, variables, alpha, max_iter, post, hard)
        hard_out[r, :] = hard
        iterations[r] = it
        unsat[r] = bad
    return hard_out, iterations, unsat


def clean_llr(llr: ArrayLike) -> Float:
    """The LLRs as finite float64: NaN becomes 0 (an erasure) and +-inf (or anything beyond
    `LLR_CLIP`) the largest finite magnitude, so a demodulator's divide by a zero variance can
    neither poison a decode nor decode to a confident all-zero word."""
    soft = np.asarray(llr, np.float64)
    return np.ascontiguousarray(
        np.clip(
            np.nan_to_num(soft, nan=0.0, posinf=LLR_CLIP, neginf=-LLR_CLIP), -LLR_CLIP, LLR_CLIP
        )
    )


def _soft_rows(llr: ArrayLike, code: LdpcCode) -> Float:
    soft = np.atleast_2d(clean_llr(llr))
    if soft.shape[-1] not in (code.transmitted, code.n):
        raise ValueError(
            f"{code.name} decodes {code.transmitted} transmitted LLRs"
            + (f" (or all {code.n})" if code.punctured else "")
            + f", not {soft.shape[-1]}"
        )
    return soft


def decode(
    llr: ArrayLike, code: LdpcCode, max_iter: int = 50, alpha: float = NORMALISATION
) -> tuple[Bits, bool, int, int]:
    """Decode one code word from its `code.transmitted` LLRs (positive = bit 0).

    Returns (all n hard bits, message = the first k; converged; iterations used; unsatisfied
    checks). `converged` means every parity check holds, which is a valid code word but, for a
    short code at low SNR, not proof that it is the one sent."""
    hard, converged, iterations, unsat = decode_many(llr, code, max_iter, alpha)
    return hard[0], bool(converged[0]), int(iterations[0]), int(unsat[0])


def decode_many(
    llr: ArrayLike, code: LdpcCode, max_iter: int = 50, alpha: float = NORMALISATION
) -> tuple[Bits, NDArray[np.bool_], NDArray[np.int64], NDArray[np.int64]]:
    """`decode` for each row of `llr` (rows x transmitted); arrays instead of scalars.

    Non-finite LLRs are cleaned (`clean_llr`). A row converges only if every check holds and at
    least half of its transmitted LLRs carry information (finite and nonzero): an all-erased row
    would otherwise "decode" to the all-zero word, which is a code word of every linear code."""
    soft = _soft_rows(llr, code)
    hard, iterations, unsat = _decode_rows(soft, code.pointers, code.cols, alpha, max_iter, code.n)
    informed = (
        np.count_nonzero(soft[:, : code.transmitted], axis=1) >= MIN_USABLE * code.transmitted
    )
    return hard, (unsat == 0) & informed, iterations, unsat


# -- alignment screening -------------------------------------------------------------------------


def syndrome(hard_bits: ArrayLike, code: LdpcCode) -> Bits:
    """The checks of the full code word `hard_bits` (n bits): 0 where the check holds."""
    hard = np.asarray(hard_bits, np.uint8)
    if hard.shape != (code.n,):
        raise ValueError(f"the syndrome takes the full {code.n}-bit code word of {code.name}")
    parity = np.zeros(code.checks, np.uint8)
    np.bitwise_xor.at(parity, code.rows, hard[code.cols])
    return parity


def syndrome_rate(hard_bits: ArrayLike, code: LdpcCode) -> float:
    """The fraction of unsatisfied checks over the code words in `hard_bits` (rows of n bits):
    0 for a code word, about w x BER / 2 for a noisy one, 0.5 for anything else (a misaligned
    stream, noise). Needs every column, so a punctured code needs `decode` instead."""
    hard = np.atleast_2d(np.asarray(hard_bits, np.uint8))
    if hard.shape[-1] != code.n:
        why = f"; {code.name} is punctured, use decode" if code.punctured else ""
        raise ValueError(f"the syndrome takes {code.n}-bit code words{why}")
    bad = sum(_unsatisfied(row, code.pointers, code.cols) for row in hard)
    return bad / (code.checks * len(hard))


@numba.njit(cache=True, nogil=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def _soft_syndrome(
    t: Float,
    pointers: Index,
    variables: Index,
    n: int,
    starts: NDArray[np.int64],
    blocks: int,
    stride: int,
) -> Float:  # pragma: no cover - compiled
    """The soft syndrome at each block start in `starts`: the mean over `blocks` consecutive
    blocks of `n` and over every `stride`-th check of the product of `t` (tanh(LLR / 2)) over the
    check's variables. It is 1 for noiseless code words and 0 on average for anything else."""
    checks = len(pointers) - 1
    out = np.zeros(len(starts))
    for i in range(len(starts)):
        total = 0.0
        used = 0
        for w in range(blocks):
            base = starts[i] + w * n
            for c in range(0, checks, stride):
                prod = 1.0
                for e in range(pointers[c], pointers[c + 1]):
                    prod *= t[base + variables[e]]
                total += prod
                used += 1
        out[i] = total / used
    return out


@numba.njit(cache=True, nogil=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def _periodicity(hard: Bits, max_period: int) -> float:  # pragma: no cover - compiled
    """The largest fraction of bits that equal the bit `p` places on, over p = 1 .. max_period:
    about 0.5 for a random stream, 1 for a constant or repeating one."""
    best = 0.0
    for p in range(1, min(max_period, len(hard) - 1) + 1):
        same = 0
        for i in range(len(hard) - p):
            same += 1 if hard[i] == hard[i + p] else 0
        best = max(best, same / (len(hard) - p))
    return best


@numba.njit(cache=True, nogil=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def _scan_decode(
    llr: Float,
    pointers: Index,
    variables: Index,
    n: int,
    transmitted: int,
    offsets: NDArray[np.int64],
    codewords: int,
    alpha: float,
    max_iter: int,
    stop_early: bool,
) -> tuple[NDArray[np.int64], NDArray[np.int64]]:  # pragma: no cover - compiled
    """For each start in `offsets`, decode `codewords` consecutive blocks for `max_iter`
    iterations: the unsatisfied checks summed over them, and how many converged (every check
    holds and at least `MIN_USABLE` of the block's LLRs are nonzero). With `stop_early` the
    first block that fails ends that offset's decode (the later ones can no longer make it
    "every block converged"): the counts are then of the blocks decoded so far."""
    unsat = np.zeros(len(offsets), np.int64)
    converged = np.zeros(len(offsets), np.int64)
    work = np.zeros(n)
    post = np.zeros(n)
    hard = np.zeros(n, np.uint8)
    for i in range(len(offsets)):
        offset = offsets[i]
        for w in range(codewords):
            work[:] = 0.0
            start = offset + w * transmitted
            informative = 0
            for v in range(transmitted):
                work[v] = llr[start + v]
                if work[v] != 0.0:
                    informative += 1
            _, bad = _min_sum(work, pointers, variables, alpha, max_iter, post, hard)
            unsat[i] += bad
            if bad == 0 and informative >= MIN_USABLE * transmitted:
                converged[i] += 1
            elif stop_early:
                break
    return unsat, converged


@dataclass(frozen=True)
class Alignment:
    """The best code-word start found in a soft stream.

    `offset` is where a block starts, modulo the transmitted length (so a burst in the middle of
    the stream reports the same offset as one from its start). `rate` is the fraction of
    unsatisfied parity checks of the hard decisions there, 0.5 being chance. `found` is the
    verdict: every one of the `codewords` blocks scanned converged to a valid code word.

    The unpunctured screen (method "soft syndrome") ranks every offset in up to `windows` windows
    of the stream by the soft syndrome, a z-score `statistic` against its own noise-only spread,
    and decodes only the best candidates, those whose statistic reaches `threshold`: the gate
    that pays for the decoder, corrected for the `hypotheses` = windows x offsets it chose
    among. A punctured code (method "decode") has no hard syndrome, so a few decoder iterations
    at every offset do the ranking and `statistic` and `threshold` are 0. Either way `converged`
    is how many of the `codewords` blocks the best candidate decoded to a code word."""

    offset: int
    rate: float
    found: bool
    hypotheses: int
    codewords: int
    method: str  # "soft syndrome" or "decode"
    threshold: float  # the statistic a candidate had to reach to be decoded (0 for "decode")
    statistic: float = 0.0  # the best candidate's soft-syndrome z-score
    windows: int = 1  # windows of the stream scanned
    converged: int = 0  # blocks of the best candidate that decoded to a code word


def _window_starts(length: int, window: int) -> list[int]:
    """Up to `MAX_WINDOWS` windows of `window` LLRs spread over `length`, overlapping by half
    when the stream is long enough for that many (a single window from the start otherwise)."""
    count = min(MAX_WINDOWS, max(1, 2 * length // window - 1))
    if count == 1:
        return [0]
    return [round(i * (length - window) / (count - 1)) for i in range(count)]


def _informative(llr: Float, hard: Bits, start: int, length: int) -> bool:
    """False for a window that cannot tell one alignment from another: mostly erased, constant
    LLRs, hard bits that are almost all one value, or a short repeating pattern. Every one of
    those is a code word (or close to one) at every offset: the all-zero word, above all."""
    seg = llr[start : start + length]
    mean_abs = float(np.abs(seg).mean())
    if np.count_nonzero(seg) < MIN_USABLE * length or float(seg.std()) <= 1e-6 * mean_abs:
        return False
    ones = float(hard[start : start + length].mean())
    if min(ones, 1.0 - ones) < MIN_MINORITY:
        return False
    return _periodicity(hard[start : start + length], MAX_PERIOD) < PERIODIC


def _hard_rate(hard: Bits, code: LdpcCode, start: int, blocks: int) -> float:
    bad = sum(
        _unsatisfied(hard[start + w * code.n : start + (w + 1) * code.n], code.pointers, code.cols)
        for w in range(blocks)
    )
    return bad / (blocks * code.checks)


def find_alignment(
    soft_llr: ArrayLike,
    code: LdpcCode,
    *,
    codewords: int = 4,
    gate_alpha: float = GATE_ALPHA,
    max_iter: int = 50,
) -> Alignment:
    """Find where `code`'s blocks start in a soft stream (positive LLR = bit 0).

    An unpunctured code is screened in two stages over up to `MAX_WINDOWS` windows of `codewords`
    blocks spread along the stream. Stage 1 scores every offset of every window by the soft
    syndrome (the mean over checks of prod tanh(L / 2), the statistic of blind code recognition,
    far less lossy than the hard syndrome, which costs 1 to 2 dB) as a z-score against what noise
    gives (the checks' products are uncorrelated and zero-mean on noise, so the variance is known
    from the window's own mean tanh^2); degenerate windows (constant, periodic, mostly erased)
    are skipped. Stage 2 runs the layered min-sum decoder for `max_iter` iterations over all
    `codewords` blocks of the best few windows whose z-score reaches the gate, the z-score a
    noise-only stream exceeds with probability `gate_alpha` over all windows x offsets, and
    `found` needs every block to converge to a valid code word. The gate only saves decoder time:
    the decoder's convergence decides. The first window that fully converges is returned.

    Measured on this machine: recall equals the ceiling of the decoder run at the true offset on
    the same four words (tests/dsp/test_ldpc.py, 20 streams per code near its waterfall, e.g. 19
    of 20 for 802.11n r1/2 at 2 dB Eb/N0); 0 false alarms in 3,000 streams per code family
    (802.11n, CCSDS TC) of Gaussian noise and uncoded random bits, 4 to 33 blocks long, though a
    single block does converge on noise about once in 10^4 for 802.11n r5/6 and TC n = 128, which
    is why every scanned block must; about 3 ms for a six-block stream and 25 ms for a long one
    at n = 648 (0.5 and 4 ms at n = 128).

    A punctured code has no hard syndrome (every check touches a punctured column), so a few
    decoder iterations on one block rank the offsets of the stream's head, the best few are
    decoded over every block, and it counts only if every block converges.

    Non-finite LLRs are cleaned (`clean_llr`). The stream must hold `transmitted - 1 + codewords
    * transmitted` LLRs; fewer code words are scanned if it holds fewer, and fewer than one is an
    error. A burst shorter than the spacing of the windows can fall between them: the scan is
    for streams that are mostly the signal, as a demodulated burst is."""
    llr = clean_llr(np.asarray(soft_llr).ravel())
    tx = code.transmitted
    codewords = min(codewords, (len(llr) - (tx - 1)) // tx)
    if codewords < 1:
        raise ValueError(f"need at least {2 * tx - 1} LLRs to scan {code.name}, got {len(llr)}")
    if code.punctured:
        return _find_punctured(llr, code, codewords, max_iter)
    window = (codewords + 1) * tx - 1
    starts = _window_starts(len(llr), window)
    hypotheses = len(starts) * tx
    gate = NormalDist().inv_cdf(1.0 - gate_alpha / hypotheses)
    hard = (llr < 0).astype(np.uint8)
    t = np.tanh(llr / 2)
    scored: list[tuple[float, int]] = []  # (z-score, block start): each window's best offsets
    for start in starts:
        if not _informative(llr, hard, start, window):
            continue
        # Every offset is first scored on every `stride`-th check (a third of the work, for a
        # code with enough checks), and the best `REFINE` are re-scored on all of them.
        stride = 3 if code.n >= COARSE_FROM else 1
        every = start + np.arange(tx, dtype=np.int64)
        coarse = _soft_syndrome(t, code.pointers, code.cols, tx, every, codewords, stride)
        shortlist = every[np.argsort(coarse)[::-1][:REFINE]]
        soft = _soft_syndrome(t, code.pointers, code.cols, tx, shortlist, codewords, 1)
        m2 = float(np.mean(t[start : start + window] ** 2))
        sigma = float(np.sqrt(np.sum(m2**code.row_weights) / codewords)) / code.checks
        # A quasi-cyclic code's offset one bit away shares most of its checks with the right one
        # (three quarters of them for 802.11n), so at low SNR the neighbour can score higher.
        for i in np.argsort(soft)[::-1][:PER_WINDOW]:
            scored.append((float(soft[i] / sigma) if sigma > 0 else 0.0, int(shortlist[i])))
    scored.sort(reverse=True)

    def result(start: int, found: bool, z: float, done: int) -> Alignment:
        return Alignment(
            start % tx,
            _hard_rate(hard, code, start, codewords),
            found,
            hypotheses,
            codewords,
            "soft syndrome",
            gate,
            z,
            len(starts),
            done,
        )

    best: tuple[int, int, float, int] | None = None  # (converged, -unsatisfied, z, start)
    for z, start in scored[:MAX_DECODES]:
        if z < gate:
            break
        unsat, converged = _scan_decode(
            llr, code.pointers, code.cols, tx, tx, np.array([start], np.int64), codewords,
            NORMALISATION, max_iter, True,
        )  # fmt: skip
        if converged[0] == codewords:
            return result(start, True, z, codewords)
        if best is None or (int(converged[0]), -int(unsat[0])) > best[:2]:
            best = (int(converged[0]), -int(unsat[0]), z, start)
    if best is not None:
        return result(best[3], False, best[2], best[0])
    if scored:  # nothing reached the gate: report the best-scoring offset, undecoded
        return result(scored[0][1], False, scored[0][0], 0)
    return Alignment(
        0, 0.5, False, hypotheses, codewords, "soft syndrome", gate, 0.0, len(starts), 0
    )


def _find_punctured(llr: Float, code: LdpcCode, codewords: int, max_iter: int) -> Alignment:
    """Stage 1: one block per offset and a few iterations; stage 2: the best few candidates
    decoded in full over every block. The `transmitted` offsets are the hypotheses."""
    tx = code.transmitted
    every = np.arange(tx, dtype=np.int64)
    screen, _ = _scan_decode(
        llr, code.pointers, code.cols, code.n, tx, every, 1, NORMALISATION, SCREEN_ITER, False
    )
    candidates = np.argsort(screen, kind="stable")[:CANDIDATES].astype(np.int64)
    unsat, converged = _scan_decode(
        llr,
        code.pointers,
        code.cols,
        code.n,
        tx,
        candidates,
        codewords,
        NORMALISATION,
        max_iter,
        False,
    )
    pick = int(np.argmin(unsat))
    return Alignment(
        int(candidates[pick]),
        float(unsat[pick] / (codewords * code.checks)),
        bool(converged[pick] == codewords),
        tx,
        codewords,
        "decode",
        0.0,
        0.0,
        1,
        int(converged[pick]),
    )
