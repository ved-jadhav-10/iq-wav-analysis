"""SITOR-B / NAVTEX (ITU-R M.476, M.625, M.540) on a demodulated bit stream: the system's own
check and its text.

Characters are 7 bits with exactly four marks (ones) and three spaces, so a single bit error turns
a valid character into an invalid one. Mode B sends every character twice, the repetition five
character slots after the first transmission: slots alternate between first transmissions (DX)
and repetitions (RX), and RX slot k repeats the DX character of slot k - 5. So a stream that is
SITOR-B has (a) 7-bit groups that are four-of-seven and (b) every other group equal to the group
five slots earlier. A random pair of groups is a valid equal pair with probability at most
35 / 128^2, which makes the agreement a strong test (the `reencode` proof: the two copies agree),
and it fixes the stream's polarity (the complement of a four-of-seven group has three marks), the
group boundary (7 offsets) and which slots are the repetitions (2 parities). Phasing signals do not
agree (they alternate between two different signals), so idle stretches add nothing.

The table is the international ITA2 letters and figures set recast to seven bits (CCIR 476), as
tabulated, most significant bit first, with mark = 1, in the English Wikipedia article "CCIR 476",
which cites the ARRL Handbook and ITU-R Rec. 625; the control codes agree with the phasing signals
the article gives for SITOR (idle alpha 0001111, beta 0110011, repeat 1100110). The bit order
is sent in and the figure-set variant (the article shows the international one, with a pound sign)
are conventions: the check cannot tell a reversed bit order from the tabulated one, so the text
is decoded both ways and the order in which "ZCZC" appears is used, else the tabulated order;
either way the text is a HYPOTHESIS on that convention.

NAVTEX messages are "ZCZC B1B2B3B4", the text and "NNNN": B1 the transmitter's identity, B2 the
subject, B3B4 a serial number (ITU-R M.540).
"""

import re
from dataclasses import dataclass
from itertools import product

import numpy as np
from numpy.typing import NDArray

from dsp.framing import binomial_tail

Bits = NDArray[np.uint8]

WIDTH = 7
REPEAT_SLOTS = 5  # an RX slot repeats the DX slot five places earlier
# A random slot pair is a valid, equal pair with probability at most 35 / 128^2.
RANDOM_PAIR = 35 / 128**2
HYPOTHESES = 2 * WIDTH * 2  # polarity x group offset x which slot parity carries the repeats
MIN_DISTINCT = 8  # distinct characters among the agreeing pairs, so a constant pattern is no match
MIN_PAIRS = 40

LETTERS = {
    0x0F: "SIA", 0x17: "J", 0x1B: "F", 0x1D: "C", 0x1E: "K", 0x27: "W", 0x2B: "Y", 0x2D: "P",
    0x2E: "Q", 0x33: "SIB", 0x35: "G", 0x36: "FIGS", 0x39: "M", 0x3A: "X", 0x3C: "V", 0x47: "A",
    0x4B: "S", 0x4D: "I", 0x4E: "U", 0x53: "D", 0x55: "R", 0x56: "E", 0x59: "N", 0x5A: "LTRS",
    0x5C: " ", 0x63: "Z", 0x65: "L", 0x66: "RPT", 0x69: "H", 0x6A: "BLK", 0x6C: "LF", 0x71: "O",
    0x72: "B", 0x74: "T", 0x78: "CR",
}  # fmt: skip
FIGURES = {
    0x0F: "SIA", 0x17: "BEL", 0x1B: "!", 0x1D: ":", 0x1E: "(", 0x27: "2", 0x2B: "6", 0x2D: "0",
    0x2E: "1", 0x33: "SIB", 0x35: "&", 0x36: "FIGS", 0x39: ".", 0x3A: "/", 0x3C: "=", 0x47: "-",
    0x4B: "'", 0x4D: "8", 0x4E: "7", 0x53: "ENQ", 0x55: "4", 0x56: "3", 0x59: ",", 0x5A: "LTRS",
    0x5C: " ", 0x63: "+", 0x65: ")", 0x66: "RPT", 0x69: "£", 0x6A: "BLK", 0x6C: "LF", 0x71: "9",
    0x72: "?", 0x74: "5", 0x78: "CR",
}  # fmt: skip
SIA, SIB, RPT, LTRS, FIGS = 0x0F, 0x33, 0x66, 0x5A, 0x36
_CONTROLS = {"SIA", "SIB", "RPT", "BLK", "BEL", "ENQ", "LTRS", "FIGS"}
_MESSAGE = re.compile(r"ZCZC ([A-Z])([A-Z])(\d\d)(.*?)NNNN", re.DOTALL)


def reverse_bits(word: int) -> int:
    return int(f"{word:07b}"[::-1], 2)


def is_valid(word: int) -> bool:
    return word.bit_count() == 4


@dataclass(frozen=True)
class Message:
    station: str  # B1, the transmitter's identity
    subject: str  # B2
    serial: str  # B3B4
    body: str
    start_bit: int  # of the first transmission of its first character, in the stream as searched
    length_bits: int  # from there to the end of its last character's slot pair
    complete: bool  # every character recovered from a valid copy (none shown as "?")


@dataclass(frozen=True)
class Ccir476Scan:
    inverted: bool
    offset: int  # bits skipped before the first group
    repeat_parity: int  # the slot parity (0 or 1) that carries repetitions
    pairs: int  # repetition slots examined
    agree: int  # valid, equal to the copy five slots earlier, and not a run of one character
    distinct: int  # different characters among the agreeing pairs
    p_value: float  # corrected for the hypotheses tried
    tried: int
    text: str
    messages: tuple[Message, ...]
    bit_order: str  # "as tabulated" or "reversed", which one put ZCZC in the text
    characters: int  # characters recovered from either copy
    erased: int  # characters neither copy of which was valid
    span: tuple[int, int]  # first and last bit covered by agreeing pairs


def groups(bits: Bits, offset: int) -> NDArray[np.int64]:
    """7-bit groups from `offset`, the first bit of each the most significant."""
    n = (len(bits) - offset) // WIDTH
    weights = 1 << np.arange(WIDTH - 1, -1, -1)
    return bits[offset : offset + n * WIDTH].reshape(n, WIDTH).astype(np.int64) @ weights


_POPCOUNT = np.array([bin(i).count("1") for i in range(128)], np.int64)


def scan(bits: Bits) -> Ccir476Scan | None:
    """Look for SITOR-B in a hard-decision stream: the strongest polarity, group offset and repeat
    parity, with its p-value already corrected for having tried all of them (the caller decides
    whether it is significant). None when none shows the minimum of repeated, varied characters."""
    best: Ccir476Scan | None = None
    for inverted, offset, parity in product((False, True), range(WIDTH), (0, 1)):
        stream = (1 - bits).astype(np.uint8) if inverted else bits
        found = _scan_one(stream, inverted, offset, parity)
        if found is not None and (best is None or found.p_value < best.p_value):
            best = found
    return best


def _scan_one(stream: Bits, inverted: bool, offset: int, parity: int) -> Ccir476Scan | None:
    g = groups(stream, offset)
    if len(g) <= REPEAT_SLOTS + 1:
        return None
    valid = _POPCOUNT[g] == 4
    k = np.arange(REPEAT_SLOTS, len(g))
    k = k[k % 2 == parity]
    pairs = len(k)
    if pairs < MIN_PAIRS:
        return None
    agree = valid[k] & valid[k - REPEAT_SLOTS] & (g[k] == g[k - REPEAT_SLOTS]) & (g[k] != g[k - 1])
    a = int(agree.sum())
    distinct = len(set(g[k][agree].tolist()))
    if a == 0 or distinct < MIN_DISTINCT:
        return None
    p = min(1.0, HYPOTHESES * binomial_tail(a, pairs, RANDOM_PAIR))
    first, last = int(k[agree][0]), int(k[agree][-1])
    text, order, messages, chars, erased = _decode(g, valid, parity, offset)
    return Ccir476Scan(
        inverted,
        offset,
        parity,
        pairs,
        a,
        distinct,
        p,
        HYPOTHESES,
        text,
        messages,
        order,
        chars,
        erased,
        (offset + WIDTH * (first - REPEAT_SLOTS), offset + WIDTH * (last + 1)),
    )


def _decode(
    g: NDArray[np.int64], valid: NDArray[np.bool_], parity: int, offset: int
) -> tuple[str, str, tuple[Message, ...], int, int]:
    """The text of the first transmissions (slots of the other parity), each replaced by its
    repetition five slots later when it is not a valid character, in whichever bit order puts
    ZCZC in the text (the tabulated one if neither does)."""
    slots = [d for d in range(len(g)) if d % 2 != parity]
    chars: list[int | None] = []
    for d in slots:
        if valid[d]:
            chars.append(int(g[d]))
        elif d + REPEAT_SLOTS < len(g) and valid[d + REPEAT_SLOTS]:
            chars.append(int(g[d + REPEAT_SLOTS]))
        else:
            chars.append(None)
    decoded: list[tuple[str, str, list[int]]] = []
    for order, flip in (("as tabulated", False), ("reversed", True)):
        text, origin = _text([None if c is None else reverse_bits(c) if flip else c for c in chars])
        decoded.append((order, text, origin))
    # The reversed order is taken only when it, and not the tabulated one, puts ZCZC headers in.
    found = [len(_MESSAGE.findall(text)) for _, text, _ in decoded]
    order, text, origin = decoded[1] if found[1] > found[0] else decoded[0]
    messages: list[Message] = []
    for m in _MESSAGE.finditer(text):
        first, last = origin[m.start()], origin[m.end() - 1]
        body = m.group(4).strip("\n ").replace("\n", " ")
        messages.append(
            Message(
                m.group(1),
                m.group(2),
                m.group(3),
                body,
                offset + WIDTH * slots[first],
                WIDTH * (slots[last] - slots[first]) + 2 * WIDTH,
                "?" not in m.group(0),
            )
        )
    return (
        text,
        order,
        tuple(messages),
        sum(c is not None for c in chars),
        sum(c is None for c in chars),
    )


def _text(chars: list[int | None]) -> tuple[str, list[int]]:
    """The text and, for each of its characters, the index of the received character it came
    from."""
    out: list[str] = []
    origin: list[int] = []
    table = LETTERS
    for i, c in enumerate(chars):
        if c is None:
            out.append("?")
            origin.append(i)
            continue
        symbol = table.get(c)
        if symbol == "LTRS":
            table = LETTERS
        elif symbol == "FIGS":
            table = FIGURES
        elif symbol is None or symbol in _CONTROLS:
            continue
        elif symbol in ("CR", "LF"):
            out.append("\n")
            origin.append(i)
        else:
            out.append(symbol)
            origin.append(i)
    return "".join(out), origin
