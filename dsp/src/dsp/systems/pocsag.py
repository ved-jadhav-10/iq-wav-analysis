"""POCSAG paging (ITU-R M.584-2) on a demodulated bit stream: the system's own check and text.

A transmission is a preamble of alternating bits, then batches of 17 codewords of 32 bits: the
synchronisation codeword 0x7CD215D8, then 8 frames of 2 codewords. Every codeword is a
BCH(31,21) code word (generator x^10 + x^9 + x^8 + x^6 + x^5 + x^3 + 1) plus an even-parity bit,
so a stream that is POCSAG has (a) the synchronisation codeword recurring every 544 bits and
(b) almost every 32-bit codeword between them passing the BCH and parity re-encode, which a
random word does with probability 2^-11. That pair is the check (`sync_recurrence` and
`reencode` proofs); nothing about the modulation or symbol rate is needed for it.

Codewords: bit 31 = 0 is an address codeword (18 address bits, 2 function bits, and the frame
number it sits in supplies the address's low 3 bits) and bit 31 = 1 a message codeword (20 data
bits); 0x7A89C197 is the idle codeword. Alphanumeric text is 7-bit characters, least significant
bit first, packed across the message codewords' data bits.

Limits: the check does not correct errors (a codeword with a bit error is counted as failed and
a page containing one is not rendered); numeric pages are not rendered (only function 3, which
operators use for alphanumeric by convention, is read as text); the standard fixes no meaning
for the function bits, so that reading is itself a convention and is labelled so.
"""

from dataclasses import dataclass
from itertools import pairwise

import numpy as np
from numpy.typing import NDArray

from dsp.framing import SyncWord, binomial_tail, sync_hits

Bits = NDArray[np.uint8]

SYNC = SyncWord("POCSAG", 0x7CD215D8, 32)
IDLE = 0x7A89C197
GENERATOR = 0b11101101001  # x^10 + x^9 + x^8 + x^6 + x^5 + x^3 + 1
CODEWORD_BITS = 32
BATCH_CODEWORDS = 17
BATCH_BITS = CODEWORD_BITS * BATCH_CODEWORDS
RANDOM_VALID = 2.0**-11  # chance a random 32-bit word passes BCH and parity: 10 check bits + parity
# The all-zero and all-one words are valid BCH words, so a constant stream would pass every
# codeword while being nothing like random: they carry no evidence and are left out of the count.
DEGENERATE = (0, 0xFFFFFFFF)
ALPHANUMERIC_FUNCTION = 3
END_OF_TEXT = (0x00, 0x04)  # padding characters after the message text


def words(bits: Bits) -> NDArray[np.uint64]:
    """Each row of a (n, 32) bit array as a 32-bit word, the first bit the most significant."""
    weights = np.uint64(1) << np.arange(CODEWORD_BITS - 1, -1, -1, dtype=np.uint64)
    return (bits.reshape(-1, CODEWORD_BITS).astype(np.uint64) * weights).sum(
        axis=1, dtype=np.uint64
    )


def check(word: NDArray[np.uint64]) -> NDArray[np.bool_]:
    """Which codewords are BCH(31,21) code words with even overall parity."""
    v = word >> np.uint64(1)  # the 31-bit BCH word; bit 0 of the codeword is the parity bit
    for shift in range(30, 9, -1):
        top = (v >> np.uint64(shift)) & np.uint64(1)
        v = v ^ (top * (np.uint64(GENERATOR) << np.uint64(shift - 10)))
    parity = np.zeros(len(word), np.uint64)
    for i in range(CODEWORD_BITS):
        parity ^= (word >> np.uint64(i)) & np.uint64(1)
    return (v == 0) & (parity == 0)


def encode_word(data21: int) -> int:
    """The codeword for 21 data bits (the flag bit and 20 payload bits): data, BCH check, parity."""
    if not 0 <= data21 < 1 << 21:
        raise ValueError("a POCSAG codeword carries 21 data bits")
    remainder = data21 << 10
    for shift in range(30, 9, -1):
        if remainder >> shift & 1:
            remainder ^= GENERATOR << (shift - 10)
    body = (data21 << 10) | remainder
    return (body << 1) | (body.bit_count() & 1)


@dataclass(frozen=True)
class Page:
    """One page: who it is for, its function bits, and the text if it could be read."""

    address: int
    function: int
    batch: int
    text: str | None  # None: not alphanumeric, or a codeword of the page failed its check
    codewords: int


@dataclass(frozen=True)
class Batch:
    start_bit: int  # in the stream as searched (after any polarity inversion)
    valid: int  # codewords passing the check, the synchronisation codeword included
    length_bits: int  # BATCH_BITS unless the stream ends first
    body_hex: tuple[str, ...]  # the codewords after the synchronisation word, 8 hex digits each

    @property
    def complete(self) -> bool:
        return self.length_bits == BATCH_BITS

    @property
    def passes(self) -> bool:
        return self.complete and self.valid == BATCH_CODEWORDS


@dataclass(frozen=True)
class PocsagScan:
    inverted: bool
    hits: int  # synchronisation codewords found on the codeword grid
    recurrences: int  # consecutive hits exactly one batch apart
    codewords: int  # codewords between the synchronisation words, first hit to end of stream
    valid: int
    p_value: float  # chance this many codewords pass if the stream were random
    batches: tuple[Batch, ...]
    pages: tuple[Page, ...]


def scan(bits: Bits) -> PocsagScan | None:
    """Look for POCSAG in a hard-decision stream, in either polarity. None when the
    synchronisation codeword never recurs one batch apart (nothing to check, and no claim)."""
    best: PocsagScan | None = None
    for inverted in (False, True):
        stream = (1 - bits).astype(np.uint8) if inverted else bits
        found = _scan_polarity(stream, inverted)
        if found is not None and (best is None or found.p_value < best.p_value):
            best = found
    return best


def _scan_polarity(stream: Bits, inverted: bool) -> PocsagScan | None:
    upright, _ = sync_hits(stream, SYNC)
    hits = [int(h) for h in upright]
    pairs = [(a, b) for a, b in pairwise(hits) if b - a == BATCH_BITS]
    if not pairs:
        return None
    phase = pairs[0][0] % CODEWORD_BITS
    grid = [h for h in hits if h % CODEWORD_BITS == phase]
    recurrences = sum(
        1 for a, b in pairs if a % CODEWORD_BITS == phase and b % CODEWORD_BITS == phase
    )
    start = grid[0]
    count = (len(stream) - start) // CODEWORD_BITS
    if count == 0:
        return None
    w = words(stream[start : start + count * CODEWORD_BITS])
    ok = check(w)
    # The synchronisation codewords are known values, not evidence of structure: only the
    # codewords between them count towards the statistic.
    body = ~np.isin(w, np.array(DEGENERATE, np.uint64))
    body[[(h - start) // CODEWORD_BITS for h in grid]] = False
    total = int(body.sum())
    if total == 0:
        return None
    valid = int((ok & body).sum())
    batches: list[Batch] = []
    for h in grid:
        first = (h - start) // CODEWORD_BITS
        chunk = slice(first, min(first + BATCH_CODEWORDS, count))
        n = chunk.stop - chunk.start
        batches.append(
            Batch(
                h,
                int(ok[chunk].sum()),
                n * CODEWORD_BITS if n < BATCH_CODEWORDS else BATCH_BITS,
                tuple(f"{int(x):08X}" for x in w[chunk.start + 1 : chunk.stop]),
            )
        )
    return PocsagScan(
        inverted,
        len(grid),
        recurrences,
        total,
        valid,
        # Both polarities were tried and the better kept: twice the chance, as Bonferroni.
        min(1.0, 2 * binomial_tail(valid, total, RANDOM_VALID)),
        tuple(batches),
        _pages(w, ok, grid, start),
    )


def _pages(
    w: NDArray[np.uint64], ok: NDArray[np.bool_], grid: list[int], start: int
) -> tuple[Page, ...]:
    """The pages in the batches, a page continuing across a synchronisation codeword when the
    next batch follows immediately."""
    pages: list[Page] = []
    open_page: list[int] | None = None  # address, function, batch, then data words
    bad = False

    def close() -> None:
        nonlocal open_page, bad
        if open_page is not None:
            address, function, batch, *data = open_page
            text = None if bad or function != ALPHANUMERIC_FUNCTION else _text(data)
            pages.append(Page(address, function, batch, text, 1 + len(data)))
        open_page, bad = None, False

    previous_end: int | None = None
    for number, h in enumerate(grid):
        first = (h - start) // CODEWORD_BITS
        if previous_end != h:
            close()
        for slot in range(16):
            index = first + 1 + slot
            if index >= len(w):
                break
            word = int(w[index])
            if not ok[index]:
                bad = True
                continue
            if word == IDLE:
                close()
            elif word >> 31 == 0:
                close()
                address = (word >> 13 & 0x3FFFF) << 3 | slot // 2
                open_page = [address, word >> 11 & 3, number]
            elif open_page is not None:
                open_page.append(word >> 11 & 0xFFFFF)
        previous_end = h + BATCH_BITS
    close()
    return tuple(pages)


def _text(data: list[int]) -> str:
    """7-bit characters, least significant bit first, from 20-bit message words sent
    most significant bit first."""
    stream = [(d >> (19 - i)) & 1 for d in data for i in range(20)]
    chars = [sum(stream[i + k] << k for k in range(7)) for i in range(0, len(stream) - 6, 7)]
    while chars and chars[-1] in END_OF_TEXT:
        chars.pop()
    return "".join(chr(c) if 32 <= c < 127 or c in (9, 10, 13) else "�" for c in chars)
