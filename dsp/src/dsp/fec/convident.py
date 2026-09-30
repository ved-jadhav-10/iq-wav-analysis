"""Blind identification of a rate-1/n convolutional code from its coded soft stream (PLAN M5).

Nothing is assumed about the code: not n, not the constraint length K, not the generators, not
which bit of the stream starts a block, not the polarity. Every generator set the search can
name is one of its hypotheses, counted and Bonferroni-corrected.

**Method.** Branch b's output is c_b = g_b * u. For any two branches, g_b * c_0 + g_0 * c_b = 0
(polynomials over GF(2), D the delay), a parity check that involves only those two streams. Take
the two streams of a candidate (polarity, n, offset), interleave them into one stream, and cut it
into windows two bits apart. Windows m blocks wide span the check once m = K, so the first width
at which the window matrix loses rank (`dsp.gf2`) marks the check, and its one-dimensional null
space *is* the check: its taps are g_b and g_0 (`pair_polynomials`). The pairs (0, b) are joined
by least common multiple into one generator set of minimal degree (`join_pairs`). The winner
must then pass the check on the whole stream: a syndrome weight far below the Binomial(L, ½)
that any structureless stream gives, on windows that do not overlap.

**Search space.** Non-recursive, unpunctured rate-1/n codes with n <= `DEFAULT_MAX_N`, constraint
length <= `DEFAULT_MAX_CONSTRAINT`, one polarity for the whole stream, and only the first
`MAX_INPUT_BITS` of it. A code outside that space (punctured, recursive, longer, or with one
branch inverted, as CCSDS's second generator is) is not found; nothing is claimed about it.

**Limits.** The rank test is exact, so it needs windows without bit errors: it is fed the most
reliable windows (`dsp.gf2.soft`), and fails, reporting no code, when too few are clean (a hard
decision input tolerates roughly 0.5 % bit errors; soft inputs more). A code whose branch pair
has a common factor is found in its reduced form. Branch order, and the offset of the first
block, are defined by the search (the stream has no other frame reference): the same code can
also be described at another offset with the branches swapped and delayed, and the search
reports the one with the smallest constraint length. A rate-1/n stream also passes as a
weaker rate-1/(n/k) description for some k | n, so the largest n that passes is preferred.
Puncturing is not handled here.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from dsp.fec.viterbi import ConvCode
from dsp.framing import binomial_tail
from dsp.gf2 import (
    MIN_EXTRA_ROWS,
    nullspace,
    pack,
    parity_counts,
    rank,
    reliable_window_matrix,
    rows_available,
    unpack,
)
from dsp.gf2.poly import pdivmod, pgcd, plcm, pmul

Float = NDArray[np.float64]

MAX_INPUT_BITS = 24_000  # only this much of the stream is searched, so cost does not grow with it
DEFAULT_MAX_N = 6
DEFAULT_MAX_CONSTRAINT = 10
DEFAULT_ALPHA = 1e-6


def to_octal(poly: int, constraint: int) -> int:
    """Generator as the standards write it: the newest input bit (D**0) is the most significant
    of `constraint` bits."""
    return sum(((poly >> i) & 1) << (constraint - 1 - i) for i in range(constraint))


# --- one branch pair ------------------------------------------------------------------------


@dataclass(frozen=True)
class PairCheck:
    """The parity check g_b * c_0 + g_0 * c_b = 0 found for one pair of branches."""

    block: int  # branch b (>= 1)
    blocks: int  # m: the window is m blocks (2m bits of the interleaved pair) wide
    g0: int  # reduced generator of branch 0 (a factor may be missing if g_0, g_b share one)
    gb: int
    vector: NDArray[np.uint8]  # the check as a 2m-bit window of the interleaved pair stream


def pair_polynomials(pair_llr: ArrayLike, branch: int, max_constraint: int) -> PairCheck | str:
    """Find the check between the two interleaved streams of `pair_llr` (c_0 at even positions,
    c_`branch` at odd). Returns the check, or the reason none was found."""
    x = np.asarray(pair_llr, dtype=np.float64)
    for m in range(2, max_constraint + 1):
        width = 2 * m
        available = rows_available(len(x), width, stride=2)
        keep = width + MIN_EXTRA_ROWS + 10
        if available < keep:
            return f"stream too short: {available} windows of {width} bits, need {keep}"
        rows = reliable_window_matrix(x, width, stride=2, keep=keep)
        packed = pack(rows)
        deficiency = width - rank(packed, width)
        if deficiency == 0:
            continue
        if deficiency > 1:
            return f"rank drops by {deficiency} at width {width}: the check is not unique"
        h = unpack(nullspace(packed, width), width)[0]
        gb = sum(int(h[2 * (m - 1 - i)]) << i for i in range(m))
        g0 = sum(int(h[2 * (m - 1 - i) + 1]) << i for i in range(m))
        if g0 == 0 or gb == 0:
            return "the check involves only one of the two streams"
        return PairCheck(branch, m, g0, gb, h)
    return f"no rank drop up to width {2 * max_constraint}"


def join_pairs(pairs: list[PairCheck]) -> tuple[int, ...] | None:
    """One generator per branch from the checks (0, b), b = 1 .. n-1, in minimal degree.

    Each check gives g_0 : g_b up to a common factor; the least common multiple of the g_0s
    is the smallest g_0 all of them divide, and each g_b is scaled to match. A shared delay and
    any factor common to every branch are then removed. None if that leaves an empty code.
    """
    g0 = pairs[0].g0
    for p in pairs[1:]:
        g0 = plcm(g0, p.g0)
    branches = [g0] + [pmul(p.gb, pdivmod(g0, p.g0)[0]) for p in pairs]
    common = 0
    for g in branches:
        common = pgcd(common, g)
    branches = [pdivmod(g, common)[0] for g in branches]
    delay = min((g & -g).bit_length() - 1 for g in branches if g)
    branches = [g >> delay for g in branches]
    return tuple(branches) if all(branches) else None


# --- the search -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Attempt:
    """One row of the search's ledger: a (polarity, n, offset) hypothesis and what decided it."""

    inverted: bool
    n: int
    offset: int
    accepted: bool
    reason: str
    p_value: float | None
    threshold: float


@dataclass(frozen=True)
class ConvIdentification:
    code: ConvCode
    n: int
    offset: int  # bit index where the first block starts; decode `llr[offset:]`
    inverted: bool  # the stream is complemented; decode `-llr[offset:]`
    windows: int  # non-overlapping windows the syndrome was counted over
    syndrome_weight: int  # of the worst pair check, how many windows failed it
    p_value: float
    threshold: float
    tried: int  # hypotheses the threshold was corrected for
    alpha: float
    # False when every check has even weight: a complemented stream then fits equally well, so
    # `inverted` is only the default, not a finding.
    polarity_determined: bool


@dataclass(frozen=True)
class ConvSearch:
    found: ConvIdentification | None
    tried: int  # hypotheses counted for the correction
    alpha: float
    ledger: tuple[Attempt, ...]


def _pair_stream(y: Float, n: int, offset: int, branch: int) -> Float:
    a, b = y[offset::n], y[offset + branch :: n]
    steps = min(len(a), len(b))
    out = np.empty(2 * steps)
    out[0::2] = a[:steps]
    out[1::2] = b[:steps]
    return out


def minimal_check(g0: int, gb: int) -> NDArray[np.uint8]:
    """The parity check g_b * c_0 + g_0 * c_b = 0 as a window of the interleaved pair stream."""
    m = max(g0.bit_length(), gb.bit_length())
    h = np.zeros(2 * m, np.uint8)
    for i in range(m):
        h[2 * (m - 1 - i)] = (gb >> i) & 1
        h[2 * (m - 1 - i) + 1] = (g0 >> i) & 1
    return h


def _syndrome(pair_llr: Float, check: NDArray[np.uint8]) -> tuple[int, int]:
    """(windows failing the check, windows) over non-overlapping, block-aligned hard windows."""
    width = len(check)
    count = len(pair_llr) // width
    if count == 0:
        return 0, 0
    hard = (pair_llr[: count * width] < 0).astype(np.uint8).reshape(count, width)
    failed = parity_counts(pack(hard), pack(check[None, :]))
    return int(failed[0]), count


def identify_convolutional(
    llr: ArrayLike,
    *,
    max_n: int = DEFAULT_MAX_N,
    max_constraint: int = DEFAULT_MAX_CONSTRAINT,
    alpha: float = DEFAULT_ALPHA,
) -> ConvSearch:
    """Search `llr` (positive means bit 0) for a rate-1/n convolutional code, n = 2 .. max_n.

    The acceptance threshold is `alpha` divided by the number of hypotheses the search could have
    produced: both polarities x every (n, offset) x every window width it may stop at.
    """
    y = np.asarray(llr, dtype=np.float64)[:MAX_INPUT_BITS]
    tried = 2 * sum(n for n in range(2, max_n + 1)) * (max_constraint - 1)
    ledger: list[Attempt] = []
    accepted: list[ConvIdentification] = []
    for n in range(2, max_n + 1):
        for offset in range(n):
            attempt, found = _attempt(y, n, offset, max_constraint, tried, alpha)
            ledger.append(attempt)
            if found is not None:
                accepted.append(found)
    # One stream can pass under several descriptions: a rate-1/4 code also satisfies a weaker
    # rate-1/2 one (K = 9 for the CCSDS-style K = 5 code), and the same code reads at other
    # offsets with the branches swapped and delayed. Take the description that explains the
    # most parity checks per block (largest n), then the shortest code, then the earliest offset.
    best = min(accepted, key=lambda c: (-c.n, c.code.constraint, c.offset), default=None)
    return ConvSearch(best, tried, alpha, tuple(ledger))


def _attempt(
    y: Float, n: int, offset: int, max_constraint: int, tried: int, alpha: float
) -> tuple[Attempt, ConvIdentification | None]:
    threshold = alpha / tried

    def rejected(reason: str, p: float | None = None) -> tuple[Attempt, None]:
        return Attempt(False, n, offset, False, reason, p, threshold), None

    pairs: list[PairCheck] = []
    streams: list[Float] = []
    for branch in range(1, n):
        pair = _pair_stream(y, n, offset, branch)
        found = pair_polynomials(pair, branch, max_constraint)
        if isinstance(found, str):
            return rejected(f"branches 0 and {branch}: {found}")
        pairs.append(found)
        streams.append(pair)
    generators = join_pairs(pairs)
    if generators is None:
        return rejected("the branch checks do not join into a code")
    constraint = max(g.bit_length() for g in generators)
    if constraint > max_constraint:
        return rejected(f"constraint length {constraint} is above the {max_constraint} searched")

    # The checks found above may be longer than the code needs (a complemented stream adds the
    # all-ones vector to the row space), so verify with the minimal check of the final generators.
    # A complement flips the parity of an odd-weight check on every window, which reads the
    # polarity; an even-weight check cannot tell, and then it cannot matter either.
    worst_p, worst = 0.0, (0, 0)
    votes: set[bool] = set()
    for branch, pair in enumerate(streams, start=1):
        check = minimal_check(generators[0], generators[branch])
        failed, windows = _syndrome(pair, check)
        if windows == 0:
            return rejected("too short to count the syndrome")
        if int(check.sum()) % 2:
            votes.add(failed > windows / 2)
            failed = min(failed, windows - failed)
        p = binomial_tail(windows - failed, windows, 0.5)  # P(Binomial(windows, ½) <= failed)
        if p >= worst_p:
            worst_p, worst = p, (failed, windows)
    if len(votes) > 1:
        return rejected("the odd-weight checks disagree on the polarity", worst_p)
    if worst_p > threshold:
        return rejected("the parity checks fail as often as on a structureless stream", worst_p)
    inverted = True in votes
    octal = tuple(to_octal(g, constraint) for g in generators)
    name = f"Conv K={constraint} r1/{n} ({','.join(f'{g:o}' for g in octal)})₈"
    code = ConvCode(name, constraint, octal)
    return (
        Attempt(inverted, n, offset, True, "the parity checks hold", worst_p, threshold),
        ConvIdentification(
            code,
            n,
            offset,
            inverted,
            worst[1],
            worst[0],
            worst_p,
            threshold,
            tried,
            alpha,
            polarity_determined=bool(votes),
        ),
    )
