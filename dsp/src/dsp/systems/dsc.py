"""MF/HF digital selective calling (ITU-R M.493-16, Annex 1) on a demodulated bit stream: the
system's own check and its calls.

The facts used here are from the Recommendation's text (Annex 1 sections 1, 3, 4, 9 and 10 and
Table A1-3):

- a character is 10 bits: seven information bits (a symbol number 0 to 127), sent least
  significant bit first, then three check bits giving the number of B (0) elements among the
  seven as a binary number, most significant bit first (a Y is a 1);
- time diversity: the first transmission (DX) of a character is followed by four other
  characters before its retransmission (RX), so RX slot k repeats the DX slot k - 5;
- the phasing sequence puts symbol 125 in the DX positions and 111, 110 ... 104 in the RX
  positions, and is not repeated;
- a call is the format specifier (sent twice), its content, the end-of-sequence symbol (117, 122
  or 127) three times in DX and once in RX, and the error-check character (ECC), whose seven bits
  are the even vertical parity of the information characters: the format specifier, the content
  and one EOS, taking each character once (the RX copies and the phasing are not counted).

So the check of a stream is (a) valid ten-bit characters, (b) every RX slot equal to the DX slot
five earlier, with the count of such agreements far above chance; and (c) separately, a
call's ECC matching its content. A random pair of 10-bit groups is a valid equal pair with
probability at most 128 / 1024^2, which together with the polarity (the tones' B and Y are not
known), the 10 group boundaries and the 2 repeat parities (40 hypotheses, in the corrected
p-value) is the significance. The ECC is reported as further evidence, never needed.

A complemented stream passes (a), (b) and the ECC rule alike: every symbol s reads as 127 - s and
its check bits complement with it. The check therefore cannot settle the polarity; only reading a
call can (a doubled format specifier from the Recommendation's list, the EOS three times, an ECC
that matches), and `DscScan.polarity_read` says whether that happened.

Limits: the content is shown as symbol numbers with its first five symbols also as the ten-digit
number they are coded as when they are an address or self-identity (two decimal digits per
symbol, as the Recommendation codes an MMSI); the meaning of every field of every format is not
decoded. VHF DSC (1,200 Bd on a sub-carrier) is not in the catalogue entry.
"""

from dataclasses import dataclass
from itertools import product

import numpy as np
from numpy.typing import NDArray

from dsp.framing import binomial_tail

Bits = NDArray[np.uint8]

WIDTH = 10
REPEAT_SLOTS = 5
RANDOM_PAIR = 128 / 1024**2  # a valid, equal pair of random 10-bit groups, an upper bound
HYPOTHESES = 2 * WIDTH * 2  # polarity x group boundary x which slot parity carries the repeats
MIN_DISTINCT = 8
MIN_PAIRS = 40
PHASING_DX = 125
EOS = {117: "acknowledgement requested", 122: "acknowledgement", 127: "no acknowledgement"}
FORMATS = {
    102: "geographic area",
    112: "distress alert",
    114: "group of ships",
    116: "all ships",
    120: "individual station",
    123: "individual station, semi-automatic/automatic",
}
MAX_CALL_SYMBOLS = 200  # a call's content is far shorter; bounds the search for its EOS

_ZEROS = np.array([7 - bin(i).count("1") for i in range(128)], np.int64)


def symbol_bits(symbol: int) -> list[int]:
    """The ten bits of a character: seven information bits least significant first, then the
    count of zeros among them, most significant bit first."""
    info = [(symbol >> i) & 1 for i in range(7)]
    zeros = info.count(0)
    return [*info, (zeros >> 2) & 1, (zeros >> 1) & 1, zeros & 1]


def groups(bits: Bits, offset: int) -> tuple[NDArray[np.int64], NDArray[np.bool_]]:
    """(symbol numbers, which groups' check bits agree with their information bits) for the
    10-bit groups from `offset`."""
    n = (len(bits) - offset) // WIDTH
    g = bits[offset : offset + n * WIDTH].reshape(n, WIDTH).astype(np.int64)
    symbols = g[:, :7] @ (1 << np.arange(7))
    check = g[:, 7] * 4 + g[:, 8] * 2 + g[:, 9]
    return symbols, check == _ZEROS[symbols]


@dataclass(frozen=True)
class Call:
    format: int  # the format specifier's symbol number
    content: tuple[int | None, ...]  # the symbols between the format specifier and the EOS
    eos: int
    ecc: int | None  # the ECC as received, None when neither copy was valid
    ecc_ok: bool | None  # None when a symbol of the call was lost, so it can't be checked
    complete: bool  # every character recovered from a valid copy
    start_bit: int
    length_bits: int

    @property
    def format_name(self) -> str:
        return FORMATS[self.format]

    @property
    def first_field(self) -> str | None:
        """The first five content symbols as the ten decimal digits they are coded as, None when
        any is missing or above 99 (then it isn't an address or self-identity)."""
        head = self.content[:5]
        if len(head) < 5 or any(s is None or s > 99 for s in head):
            return None
        return "".join(f"{s:02d}" for s in head if s is not None)


@dataclass(frozen=True)
class DscScan:
    inverted: bool
    offset: int
    repeat_parity: int
    pairs: int
    agree: int
    distinct: int
    p_value: float  # corrected for the hypotheses tried
    tried: int
    calls: tuple[Call, ...]
    polarity_read: bool  # a call was read, so the polarity is the one its format specifier fits
    characters: int
    erased: int
    span: tuple[int, int]


def scan(bits: Bits) -> DscScan | None:
    """The strongest polarity, group boundary and repeat parity for DSC in a hard-decision
    stream, its p-value already corrected for having tried them all (the caller decides whether
    it is significant); None when none shows the minimum of repeated, varied characters."""
    best: DscScan | None = None
    for inverted, offset, parity in product((False, True), range(WIDTH), (0, 1)):
        stream = (1 - bits).astype(np.uint8) if inverted else bits
        found = _scan_one(stream, inverted, offset, parity)
        if found is not None and (best is None or _rank(found) < _rank(best)):
            best = found
    return best


def _rank(found: DscScan) -> tuple[float, int]:
    """Stronger first: the lower p-value, and between equal ones (a complemented stream is also a
    valid stream: symbol s reads as 127 - s, check bits and copies still agree) the polarity in
    which calls can be read."""
    return found.p_value, -len(found.calls)


def _scan_one(stream: Bits, inverted: bool, offset: int, parity: int) -> DscScan | None:
    symbols, valid = groups(stream, offset)
    if len(symbols) <= REPEAT_SLOTS + 1:
        return None
    k = np.arange(REPEAT_SLOTS, len(symbols))
    k = k[k % 2 == parity]
    if len(k) < MIN_PAIRS:
        return None
    agree = (
        valid[k]
        & valid[k - REPEAT_SLOTS]
        & (symbols[k] == symbols[k - REPEAT_SLOTS])
        & (symbols[k] != symbols[k - 1])
    )
    a = int(agree.sum())
    distinct = len(set(symbols[k][agree].tolist()))
    if a == 0 or distinct < MIN_DISTINCT:
        return None
    p = min(1.0, HYPOTHESES * binomial_tail(a, len(k), RANDOM_PAIR))
    calls, recovered, erased = _calls(symbols, valid, parity, offset)
    first, last = int(k[agree][0]), int(k[agree][-1])
    return DscScan(
        inverted,
        offset,
        parity,
        len(k),
        a,
        distinct,
        p,
        HYPOTHESES,
        calls,
        bool(calls),
        recovered,
        erased,
        (offset + WIDTH * (first - REPEAT_SLOTS), offset + WIDTH * (last + 1)),
    )


def _calls(
    symbols: NDArray[np.int64], valid: NDArray[np.bool_], parity: int, offset: int
) -> tuple[tuple[Call, ...], int, int]:
    """The calls in the first-transmission stream (each symbol replaced by its repetition when
    it fails its check), found as a doubled format specifier, content, three EOS and an ECC."""
    slots = [d for d in range(len(symbols)) if d % 2 != parity]
    stream: list[int | None] = []
    for d in slots:
        if valid[d]:
            stream.append(int(symbols[d]))
        elif d + REPEAT_SLOTS < len(symbols) and valid[d + REPEAT_SLOTS]:
            stream.append(int(symbols[d + REPEAT_SLOTS]))
        else:
            stream.append(None)
    calls: list[Call] = []
    i = 0
    while i < len(stream) - 2:
        fmt = stream[i]
        if fmt in FORMATS and stream[i + 1] == fmt:
            call = _call_at(stream, i, slots, offset)
            if call is not None:
                calls.append(call[0])
                i = call[1]
                continue
        i += 1
    return tuple(calls), sum(s is not None for s in stream), sum(s is None for s in stream)


def _call_at(
    stream: list[int | None], i: int, slots: list[int], offset: int
) -> tuple[Call, int] | None:
    fmt = stream[i]
    assert fmt is not None
    limit = min(len(stream) - 3, i + 2 + MAX_CALL_SYMBOLS)
    for j in range(i + 2, limit):
        eos = stream[j]
        if eos in EOS and stream[j + 1] == eos and stream[j + 2] == eos:
            content = tuple(stream[i + 2 : j])
            ecc = stream[j + 3] if j + 3 < len(stream) else None
            complete = None not in content and ecc is not None
            parity = fmt ^ eos
            for s in content:
                parity ^= s or 0
            ecc_ok = (ecc == parity) if complete and ecc is not None else None
            last = min(j + 3, len(stream) - 1)
            return (
                Call(
                    fmt,
                    content,
                    eos,
                    ecc,
                    ecc_ok,
                    complete,
                    offset + WIDTH * slots[i],
                    WIDTH * (slots[last] - slots[i]) + 2 * WIDTH,
                ),
                j + 4,
            )
    return None
