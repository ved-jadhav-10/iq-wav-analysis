"""CCSDS telemetry LDPC (AR4JA, CCSDS 131.0-B-5 section 7) on a demodulated stream: the system's
own check, without the alignment scan.

How the stream looks, as this module reads the standard (from memory of CCSDS 131.0-B; see
"Not verified" below): each transmitted code word is preceded by the 32-bit attached sync marker
0x1ACFFC1D; the code word, the `transmitted` columns of the code (n minus the M punctured ones),
is XORed with the pseudo-randomiser (x^8 + x^7 + x^5 + x^3 + 1, all ones at the first bit of each
code word, period 255 bits), which is not applied to the marker; the first k bits of the code word
are the message, a transfer frame. So the marker recurs every `transmitted + 32` bits, a period no
other catalogued code shares, and that settles the alignment in one pass over the stream.

The check, per code (six of them: k = 1024 and 4096 at rates 1/2, 2/3 and 4/5):

1. The marker, with up to `MAX_SYNC_ERRORS` bit errors, recurs at the code's period (two hits one
   period apart), in either polarity and, for QPSK, under each of the four ways the two bits of a
   symbol can come out of a carrier rotation or an I/Q swap.
2. The code words after the marker, taken off the recurrence grid, are decoded (layered min-sum,
   punctured columns as erasures) with and without the pseudo-randomiser, and a block counts when
   every one of the code's parity checks holds, its message is not degenerate and the decoded word
   is close to the received hard bits.

The statistic. A decoder's "converged" has no closed-form chance, but the distance of the decoded
word to the received bits does: a random block of `tx` bits lies within Hamming distance d of one
of the 2^k transmitted words with probability at most 2^k * P(Binomial(tx, 1/2) <= d) (a union
bound over the code, whatever the decoder did). For the rate-1/2 k = 1024 code a block at 5 %
hard-decision errors is 2^-437 under that bound; it falls below 1 at the Gilbert-Varshamov
distance of the code's rate, about 11 % raw bit errors for rate 1/2, 6 % for 2/3 and 3 % for 4/5
(for QPSK, from about 2, 3 and 5 dB Es/N0 upward). The decoder works lower, where a block is not
claimed as evidence (`MIN_BLOCK_BITS`) and the check says so. The check's p-value is the product of

- the Poisson tail of the marker-recurrence pairs seen at the period (a random position matches
  within 3 errors with probability 5489 / 2^32, a pair of them one period apart at its square),
- the bound above for each valid block (a block counts only when its bound is below
  2^-`MIN_BLOCK_BITS`; with no valid block the check's p-value is 1),
- C(scanned, valid), since which blocks pass is chosen by the data,
- the hypotheses behind the winning variant: stream variants x 2 polarities x 2 randomiser states.

The marker recurrence and the block contents are independent for a random stream, so the product
is the chance of the whole check. The proof is of kind `sync_recurrence`, with the decoder's
syndrome and the distances in the evidence; there is no new proof kind.

Not verified against the standard text (nothing here was compared with the PDF): the marker for
these codes is taken as the 32-bit 0x1ACFFC1D (the standard also defines a 64-bit marker for some
codings, which this check does not try); the randomiser's all-ones seed and its restart at each
code word; that the randomiser covers the code word and not the marker; that the transmitted word
is the first `n - M` columns, the message first. The check does not depend on a frame-error-control
field: the transfer frame is not parsed here (the first 6 bytes are shown as a primary header on
the CCSDS 132.0-B convention, as a HYPOTHESIS).
"""

import math
from dataclasses import dataclass
from itertools import product

import numpy as np
from numpy.typing import NDArray

from dsp.fec import ldpc
from dsp.fec.ldpc import LdpcCode
from dsp.framing import MAX_SYNC_ERRORS, SYNC_WORDS, random_hit_probability
from dsp.scramble import CCSDS as RANDOMISER

Float = NDArray[np.float64]
Bits = NDArray[np.uint8]

ASM = next(w for w in SYNC_WORDS if w.name == "CCSDS ASM")
CODES: tuple[LdpcCode, ...] = tuple(c for c in ldpc.CATALOGUE if c.family == "CCSDS TM")
MAX_BLOCKS = 6  # code words decoded to decide a code
MAX_FRAMES = 500  # code words decoded for the frame table once a code is verified
MIN_MINORITY = 0.05  # a message with fewer 0s or 1s than this is idle, not evidence
# A decoded block counts only when the distance bound puts it at least this far below chance
# (log2 of its probability), so a block that converged far from what was received is not evidence.
MIN_BLOCK_BITS = 30.0
HEADER_BYTES = 6
QPSK_VARIANTS = tuple(product((False, True), repeat=2))  # (swap the pair, invert the second bit)
LN2 = math.log(2.0)


def period(code: LdpcCode) -> int:
    """Bits from one marker to the next."""
    return ASM.width + code.transmitted


def min_bits() -> int:
    """The least stream that can hold two markers and one code word of the shortest code."""
    return min(period(c) for c in CODES) + ASM.width + min(c.transmitted for c in CODES)


@dataclass(frozen=True)
class Block:
    start_bit: int  # of the marker, in the stream as searched
    valid: bool  # every parity check holds, informative message, close to the received bits
    message: bytes  # the decoded message bits, whole bytes
    distance: int  # Hamming distance of the decoded transmitted word to the received bits
    unsatisfied: int  # parity checks of the full code word the decoder left unsatisfied
    log2_p: float  # the union bound on a random block lying this close to some code word


@dataclass(frozen=True)
class CodeRun:
    """One code's outcome: always present, so the ledger shows every code that was tried."""

    code: LdpcCode
    period: int
    hits: int  # markers found at the best variant (both polarities counted apart)
    pairs: int  # marker pairs one period apart, at the variant that had the most
    scanned: int  # code words decoded
    valid: int
    log10_p: float  # of the whole check; 0 when nothing recurred (p = 1)
    verified: bool
    variant: str
    inverted: bool
    randomised: bool
    log10_p_asm: float
    log10_p_blocks: float
    hypotheses: int
    blocks: tuple[Block, ...]  # all decoded blocks of a verified code (frame table), else the scan
    distances: tuple[int, ...]
    statistic: str
    reason: str


@dataclass(frozen=True)
class LdpcScan:
    runs: tuple[CodeRun, ...]
    variants: int  # stream variants tried (1 for BPSK, 4 for QPSK)
    best: CodeRun | None  # the verified run with the smallest p, if any


def variant_names(modulation: str | None) -> tuple[str, ...]:
    if modulation == "QPSK":
        return (
            "bits as demapped",
            "second bit of each pair inverted",
            "bit pairs swapped",
            "bit pairs swapped, second bit inverted",
        )
    return ("bits as demapped",)


def _variants(llr: Float, modulation: str | None) -> list[Float]:
    """The soft stream under each way its bits can be arranged by a carrier-phase ambiguity: as
    given for BPSK, and for QPSK the four pair arrangements (a rotation by 90 degrees swaps the
    pair and inverts one bit; the others come from a mirrored spectrum). A complemented stream is
    the same stream with the polarity searched on the marker."""
    if modulation != "QPSK":
        return [llr]
    pairs = llr[: len(llr) // 2 * 2].reshape(-1, 2)
    out: list[Float] = []
    for swap, invert in QPSK_VARIANTS:
        first = pairs[:, 1 if swap else 0]
        second = pairs[:, 0 if swap else 1] * (-1.0 if invert else 1.0)
        out.append(np.ascontiguousarray(np.stack([first, second], axis=1).ravel()))
    return out


def _marker_hits(llr: Float) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    """Starts of the marker with at most MAX_SYNC_ERRORS errors: (upright, inverted)."""
    if len(llr) < ASM.width:
        empty = np.zeros(0, np.int64)
        return empty, empty
    signs = np.where(llr < 0, -1.0, 1.0)  # +1 for bit 0, as the marker's reference below
    reference = 1.0 - 2.0 * ASM.bits().astype(np.float64)
    # Direct correlation of 32 taps: faster than an FFT for the burst sizes the chain hands over.
    c = np.correlate(signs, reference, mode="valid")
    need = ASM.width - 2 * MAX_SYNC_ERRORS
    return np.flatnonzero(c >= need), np.flatnonzero(c <= -need)


def _log_sum_exp(terms: list[float]) -> float:
    top = max(terms)
    return top + math.log(sum(math.exp(t - top) for t in terms))


def _log10_poisson_tail(k: int, lam: float) -> float:
    """log10 P(X >= k) for X ~ Poisson(lam), k >= 1."""
    terms = [-lam + j * math.log(lam) - math.lgamma(j + 1) for j in range(k, k + 60)]
    return _log_sum_exp(terms) / math.log(10.0)


def _log2_block_p(code: LdpcCode, distance: int) -> float:
    """log2 of 2^k * P(Binomial(tx, 1/2) <= distance), capped at 0 (a probability bound)."""
    tx = code.transmitted
    top = math.lgamma(tx + 1)
    terms = [top - math.lgamma(i + 1) - math.lgamma(tx - i + 1) for i in range(distance + 1)]
    log_tail = _log_sum_exp(terms) - tx * LN2
    return min(0.0, (code.k * LN2 + log_tail) / LN2)


def _log10_choose(n: int, k: int) -> float:
    return (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)) / math.log(10.0)


def _decode_blocks(
    llr: Float, code: LdpcCode, starts: list[int], inverted: bool, randomised: bool
) -> list[Block]:
    """Decode the code words behind the markers at `starts` (all of them fit in `llr`)."""
    tx = code.transmitted
    sign = -1.0 if inverted else 1.0
    if randomised:
        sign_row = sign * (1.0 - 2.0 * RANDOMISER.sequence(tx).astype(np.float64))
    else:
        sign_row = np.full(tx, sign)
    rows = np.stack([llr[s + ASM.width : s + ASM.width + tx] for s in starts]) * sign_row
    hard, converged, _, unsat = ldpc.decode_many(rows, code)
    received = (ldpc.clean_llr(rows) < 0).astype(np.uint8)
    out: list[Block] = []
    for i, s in enumerate(starts):
        distance = int(np.count_nonzero(hard[i, :tx] != received[i]))
        message = hard[i, : code.k]
        ones = float(message.mean())
        informative = min(ones, 1.0 - ones) >= MIN_MINORITY
        usable = code.k - code.k % 8
        bound = _log2_block_p(code, distance)
        out.append(
            Block(
                s,
                bool(converged[i]) and informative and bound <= -MIN_BLOCK_BITS,
                np.packbits(message[:usable]).tobytes(),
                distance,
                int(unsat[i]),
                bound,
            )
        )
    return out


def _grid(hits: NDArray[np.int64], pairs: NDArray[np.int64], p: int) -> list[int]:
    """The markers on the recurrence grid, from the first pair on."""
    first = int(pairs[0])
    return [int(h) for h in hits if h >= first and (int(h) - first) % p == 0]


def scan(llr_in: object, modulation: str | None) -> LdpcScan:
    """Run the check for every code on a soft stream (positive = bit 0; hard decisions as +-1)."""
    llr = ldpc.clean_llr(np.asarray(llr_in))
    variants = _variants(llr, modulation)
    names = variant_names(modulation)
    hypotheses = len(variants) * 2 * 2
    hits = [_marker_hits(v) for v in variants]
    runs = [_run_code(code, variants, names, hits, hypotheses) for code in CODES]
    verified = [r for r in runs if r.verified]
    best = min(verified, key=lambda r: r.log10_p) if verified else None
    return LdpcScan(tuple(runs), len(variants), best)


def _run_code(
    code: LdpcCode,
    variants: list[Float],
    names: tuple[str, ...],
    hits: list[tuple[NDArray[np.int64], NDArray[np.int64]]],
    hypotheses: int,
) -> CodeRun:
    p = period(code)
    tx = code.transmitted
    # The (variant, polarity) with the most marker pairs one period apart.
    best: tuple[int, int, bool, NDArray[np.int64], NDArray[np.int64]] | None = None
    total_hits = 0
    for v, (up, down) in enumerate(hits):
        for inverted, h in ((False, up), (True, down)):
            total_hits += len(h)
            if len(h) < 2:
                continue
            pairs = h[np.isin(h + p, h)]
            if len(pairs) and (best is None or len(pairs) > best[0]):
                best = (len(pairs), v, inverted, h, pairs)
    if best is None:
        return CodeRun(
            code, p, total_hits, 0, 0, 0, 0.0, False, names[0], False, False, 0.0, 0.0,
            hypotheses, (), (),
            f"marker x{total_hits}, no recurrence at {p:,} bits",
            f"The attached sync marker 0x1ACFFC1D does not recur {p:,} bits apart (the code word "
            f"is {tx:,} bits plus the 32-bit marker), in either polarity or under any bit "
            f"arrangement tried",
        )  # fmt: skip
    npairs, v, inverted, h, pairs = best
    grid = [g for g in _grid(h, pairs, p) if g + ASM.width + tx <= len(variants[v])]
    chance = max(len(variants[v]) - p - ASM.width, 1) * random_hit_probability(ASM) ** 2
    log10_asm = min(0.0, _log10_poisson_tail(npairs, chance))
    scanned_starts = grid[:MAX_BLOCKS]
    if not scanned_starts:
        return CodeRun(
            code, p, total_hits, npairs, 0, 0, 0.0, False, names[v], inverted, False,
            log10_asm, 0.0, hypotheses, (), (),
            f"marker recurs x{npairs} at {p:,} bits, no whole code word follows",
            "The marker recurs at the code's period but the stream ends before a whole code word "
            "after it",
        )  # fmt: skip
    candidates: list[tuple[float, bool, list[Block]]] = []
    for randomised in (True, False):
        blocks = _decode_blocks(variants[v], code, scanned_starts, inverted, randomised)
        log10_blocks = sum(b.log2_p * math.log10(2.0) for b in blocks if b.valid)
        nvalid = sum(b.valid for b in blocks)
        log10_blocks += _log10_choose(len(blocks), nvalid) if nvalid else 0.0
        candidates.append((log10_blocks if nvalid else 0.0, randomised, blocks))
    log10_blocks, randomised, blocks = min(candidates, key=lambda c: c[0])
    nvalid = sum(b.valid for b in blocks)
    # No valid block: the check as a whole found nothing, whatever the marker's recurrence was.
    log10_p = min(0.0, log10_asm + log10_blocks + math.log10(hypotheses)) if nvalid else 0.0
    # The caller's Holm test sets the threshold the p-value must pass.
    verified = nvalid > 0 and log10_p < 0.0
    distances = tuple(b.distance for b in blocks if b.valid)
    if verified:
        starts = grid[:MAX_FRAMES]
        blocks = _decode_blocks(variants[v], code, starts, inverted, randomised)
    raw = f"marker x{total_hits}, {npairs} pair(s) at {p:,}; {nvalid}/{len(scanned_starts)} valid"
    if verified:
        reason = (
            f"the marker recurs {npairs} time(s) {p:,} bits apart and {nvalid} of "
            f"{len(scanned_starts)} code words behind it decode to valid {code.name} code "
            f"words (all {code.checks:,} parity checks hold; Hamming distance to the received "
            f"bits "
            f"{', '.join(str(d) for d in distances)} of {tx:,}), "
            f"{'with' if randomised else 'WITHOUT'} the CCSDS pseudo-randomiser, "
            f"{names[v]}{', complemented' if inverted else ''}"
        )
    else:
        reason = (
            f"the marker recurs {npairs} time(s) {p:,} bits apart but {nvalid} of "
            f"{len(scanned_starts)} code words behind it decode to a {code.name} code word"
            + ("" if nvalid == 0 else " (not significant after correction)")
        )
    return CodeRun(
        code, p, total_hits, npairs, len(scanned_starts), nvalid, log10_p, verified, names[v],
        inverted, randomised, log10_asm, log10_blocks, hypotheses, tuple(blocks), distances,
        raw, reason,
    )  # fmt: skip


def p_value(run: CodeRun) -> float:
    """The check's p-value as a float, floored at 1e-300 (the floor the other checks use)."""
    return max(10.0**run.log10_p, 1e-300)
