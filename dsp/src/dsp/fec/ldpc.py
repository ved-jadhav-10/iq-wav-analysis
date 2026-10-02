"""Standard LDPC codes: a catalogue of published parity-check matrices, a systematic encoder and
a soft-decision decoder (PLAN M5).

The catalogue holds the codes a blind search can try by name: IEEE 802.11n (n = 648, rates 1/2,
2/3, 3/4, 5/6), the CCSDS TC codes (128, 64), (256, 128), (512, 256) and the CCSDS TM (AR4JA)
codes at rates 1/2, 2/3 and 4/5 for k = 1024 and 4096. The numbers are in `ldpc_data` with their
sources; the matrices are built here from them.

Conventions, matching `dsp.fec.viterbi`: an LLR is positive for bit 0 (hard bit = LLR < 0). A
code word is systematic, the message in the first `k` columns of H. Codes with `punctured` > 0
(the CCSDS TM codes) never transmit their last `punctured` columns: the decoder takes the
transmitted length and re-inserts those as LLR 0 (an erasure) and returns all `n` bits.

The decoder is layered normalised min-sum in Numba: each check in turn replaces its messages and
updates the variable posteriors at once, which converges in about half the iterations of the
flooding schedule, and stops as soon as every check holds. Encoding solves H c = 0 for the
parity columns through `dsp.gf2` (the one elimination routine), once per code.
"""

import math
from dataclasses import dataclass
from functools import cache, cached_property

import numba  # pyright: ignore[reportMissingTypeStubs]
import numpy as np
from numpy.typing import ArrayLike, NDArray

from dsp.fec import ldpc_data
from dsp.gf2 import pack, rref, unpack

Bits = NDArray[np.uint8]
Float = NDArray[np.float64]
Index = NDArray[np.int32]

SCREEN_ITER = 5  # decode iterations per offset in the alignment screen's first stage
CANDIDATES = 8  # offsets the screen's second stage decodes in full
NORMALISATION = 0.8  # min-sum scaling; 0.75 to 0.85 is within 0.1 dB of belief propagation


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
        "(numbers cross-checked against yairmz/ldpc, MIT)",
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
        f"CCSDS 231.1-O-1, ({n}, {n // 2}) (numbers cross-checked against labrador-ldpc, MIT)",
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
        "not transmitted (numbers cross-checked against labrador-ldpc, MIT)",
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


@numba.njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
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


@numba.njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
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


def _soft_rows(llr: ArrayLike, code: LdpcCode) -> Float:
    soft = np.atleast_2d(np.ascontiguousarray(llr, np.float64))
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
    """`decode` for each row of `llr` (rows x transmitted); arrays instead of scalars."""
    soft = _soft_rows(llr, code)
    hard, iterations, unsat = _decode_rows(soft, code.pointers, code.cols, alpha, max_iter, code.n)
    return hard, unsat == 0, iterations, unsat


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


@numba.njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def _scan_syndrome(
    hard: Bits, pointers: Index, variables: Index, n: int, codewords: int
) -> NDArray[np.int64]:  # pragma: no cover - compiled
    out = np.zeros(n, np.int64)
    for offset in range(n):
        total = 0
        for w in range(codewords):
            start = offset + w * n
            for c in range(len(pointers) - 1):
                parity = 0
                for e in range(pointers[c], pointers[c + 1]):
                    parity ^= hard[start + variables[e]]
                total += parity
        out[offset] = total
    return out


@numba.njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
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
) -> tuple[NDArray[np.int64], NDArray[np.int64]]:  # pragma: no cover - compiled
    """For each start in `offsets`, decode `codewords` consecutive blocks for `max_iter`
    iterations: the unsatisfied checks summed over them, and how many converged."""
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
            for v in range(transmitted):
                work[v] = llr[start + v]
            _, bad = _min_sum(work, pointers, variables, alpha, max_iter, post, hard)
            unsat[i] += bad
            if bad == 0:
                converged[i] += 1
    return unsat, converged


@dataclass(frozen=True)
class Alignment:
    """The best code-word start found in a soft stream.

    `rate` is the unsatisfied-check fraction at `offset` (hard syndrome, or after a short decode
    for a punctured code); 0.5 is chance. `found` is the corrected verdict: the rate is below
    what chance gives over all `hypotheses` offsets (Hoeffding, false-alarm `alpha`), or for the
    decode screen every scanned code word converged to a valid code word."""

    offset: int
    rate: float
    found: bool
    hypotheses: int
    codewords: int
    method: str  # "syndrome" or "decode"
    threshold: float  # the rate that had to be beaten (syndrome screen; 0 for decode)


def find_alignment(
    soft_llr: ArrayLike,
    code: LdpcCode,
    *,
    codewords: int = 4,
    alpha: float = 1e-3,
    max_iter: int = 20,
) -> Alignment:
    """Scan every code-word start 0 .. transmitted - 1 of the soft stream for `code`.

    An unpunctured code is screened by the hard syndrome of `codewords` consecutive blocks at
    each offset, and `found` needs the best rate below 0.5 - sqrt(ln(offsets / alpha) / (2 N))
    for N checks, so that on noise it fires with probability under `alpha` over the whole scan.
    A punctured code has no hard syndrome (every check touches a punctured column), so each
    offset is screened by a few decoder iterations on one block, the best few offsets are then
    decoded for `max_iter` iterations over every block, and it counts only if every block converges.
    The stream must hold `transmitted - 1 + codewords * transmitted` LLRs; fewer code words are
    scanned if it holds fewer, and fewer than one is an error."""
    llr = np.ascontiguousarray(np.asarray(soft_llr, np.float64).ravel())
    tx = code.transmitted
    codewords = min(codewords, (len(llr) - (tx - 1)) // tx)
    if codewords < 1:
        raise ValueError(f"need at least {2 * tx - 1} LLRs to scan {code.name}, got {len(llr)}")
    if code.punctured == 0:
        hard = (llr < 0).astype(np.uint8)
        bad = _scan_syndrome(hard, code.pointers, code.cols, code.n, codewords)
        rates = bad / (codewords * code.checks)
        best = int(np.argmin(rates))
        spread = math.sqrt(math.log(code.n / alpha) / (2 * codewords * code.checks))
        threshold = 0.5 - spread
        return Alignment(
            best, float(rates[best]), bool(rates[best] < threshold), code.n, codewords, "syndrome",
            threshold,
        )  # fmt: skip
    # Stage 1: one block per offset and a few iterations; stage 2: the best few candidates
    # decoded in full over every block. The `tx` offsets are the hypotheses either way.
    every = np.arange(tx, dtype=np.int64)
    screen, _ = _scan_decode(
        llr, code.pointers, code.cols, code.n, tx, every, 1, NORMALISATION, SCREEN_ITER
    )
    candidates = np.argsort(screen, kind="stable")[:CANDIDATES].astype(np.int64)
    unsat, converged = _scan_decode(
        llr, code.pointers, code.cols, code.n, tx, candidates, codewords, NORMALISATION, max_iter
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
    )
