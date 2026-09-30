"""Frame synchronisation and CRC checks on a decoded bit stream (PLAN M6).

A catalogued sync word is searched for with up to MAX_SYNC_ERRORS bit errors, in both
polarities (a 180-degree phase ambiguity through a code with odd-weight generators inverts
the data). The frame length is the spacing at which the sync word recurs. Each complete frame
is then checked against the catalogued CRCs, which cover the bits between the sync word and
the CRC field at the end of the frame (the layout `dsp.synth.bits.FrameSpec` writes). A CRC
pass is the only thing here that can make a result VERIFIED.

The catalogues are data copied from the standards (not imported from dsp.synth, which is the
test oracle): CCSDS 131.0-B's attached sync marker, and the CRC parameter sets of Greg Cook's
"Catalogue of parametrised CRC algorithms" (reveng). Each CRC entry carries the catalogue's
check value, the CRC of the nine bytes "123456789", which the tests recompute.
"""

import math
from collections import Counter
from dataclasses import dataclass
from typing import Literal

import numba  # pyright: ignore[reportMissingTypeStubs]
import numpy as np
from numpy.typing import NDArray

from dsp.scramble import Descrambler

Bits = NDArray[np.uint8]

MAX_SYNC_ERRORS = 3
MIN_RECURRENCES = 2  # sync hits at the frame period needed to call a period


@dataclass(frozen=True)
class SyncWord:
    name: str
    value: int
    width: int

    @property
    def hex(self) -> str:
        return f"0x{self.value:0{self.width // 4}X}" if self.width % 4 == 0 else bin(self.value)

    def bits(self) -> Bits:
        return np.array(
            [(self.value >> (self.width - 1 - i)) & 1 for i in range(self.width)], np.uint8
        )


# Sources: CCSDS 131.0-B (attached sync marker); ITU-R M.584-2 (POCSAG synchronisation codeword).
# Only words long enough to have a low chance hit rate belong here: a 13-bit Barker word or an
# 8-bit HDLC flag matches random positions too often to be searched for with bit errors, and is
# found by `dsp.blind_framing` instead.
SYNC_WORDS = (
    SyncWord("CCSDS ASM", 0x1ACFFC1D, 32),
    SyncWord("POCSAG", 0x7CD215D8, 32),
)


@dataclass(frozen=True)
class Crc:
    name: str
    width: int
    poly: int
    init: int
    refin: bool
    refout: bool
    xorout: int

    check: int = 0  # the CRC of b"123456789"; 0 for an entry not from the catalogue

    def compute_many(self, frames: NDArray[np.uint8]) -> NDArray[np.int64]:
        """The CRC of each row of a 2-D bit array (all rows the same length), one per row."""
        rows = np.ascontiguousarray(frames, np.uint8)
        return _crc_rows(
            rows, self.width, self.poly, self.init, self.refin, self.refout, self.xorout
        )

    def compute(self, bits: Bits) -> int:
        top, mask = 1 << (self.width - 1), (1 << self.width) - 1
        data = np.asarray(bits, np.uint8)
        if self.refin:
            usable = len(data) - len(data) % 8
            data = np.concatenate([data[:usable].reshape(-1, 8)[:, ::-1].ravel(), data[usable:]])
        reg = self.init
        for bit in data.tolist():
            feedback = bool(reg & top) ^ bool(bit)
            reg = (reg << 1) & mask
            if feedback:
                reg ^= self.poly
        if self.refout:
            reg = int(f"{reg:0{self.width}b}"[::-1], 2)
        return reg ^ self.xorout


@numba.njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def _crc_rows(
    rows: NDArray[np.uint8],
    width: int,
    poly: int,
    init: int,
    refin: bool,
    refout: bool,
    xorout: int,
) -> NDArray[np.int64]:  # pragma: no cover - compiled
    count, length = rows.shape
    out = np.empty(count, np.int64)
    top = 1 << (width - 1)
    mask = (1 << width) - 1
    whole = length - length % 8  # a trailing partial byte is not reflected
    for f in range(count):
        reg = init
        for i in range(length):
            j = i
            if refin and i < whole:
                j = (i // 8) * 8 + 7 - i % 8
            feedback = ((reg & top) != 0) != (rows[f, j] != 0)
            reg = (reg << 1) & mask
            if feedback:
                reg ^= poly
        if refout:
            flipped = 0
            for _ in range(width):
                flipped = (flipped << 1) | (reg & 1)
                reg >>= 1
            reg = flipped
        out[f] = reg ^ xorout
    return out


# name, width, poly, init, refin, refout, xorout, check. Parameters and check values are the
# reveng catalogue's; a wrong entry fails its check in tests/dsp/test_framing_crcs.py.
_CATALOGUE = (
    ("CRC-16/CCITT-FALSE", 16, 0x1021, 0xFFFF, False, False, 0x0000, 0x29B1),
    ("CRC-16/X-25", 16, 0x1021, 0xFFFF, True, True, 0xFFFF, 0x906E),
    ("CRC-16/XMODEM", 16, 0x1021, 0x0000, False, False, 0x0000, 0x31C3),
    ("CRC-16/KERMIT", 16, 0x1021, 0x0000, True, True, 0x0000, 0x2189),
    ("CRC-16/MCRF4XX", 16, 0x1021, 0xFFFF, True, True, 0x0000, 0x6F91),
    ("CRC-16/AUG-CCITT", 16, 0x1021, 0x1D0F, False, False, 0x0000, 0xE5CC),
    ("CRC-16/GENIBUS", 16, 0x1021, 0xFFFF, False, False, 0xFFFF, 0xD64E),
    ("CRC-16/ARC", 16, 0x8005, 0x0000, True, True, 0x0000, 0xBB3D),
    ("CRC-16/MODBUS", 16, 0x8005, 0xFFFF, True, True, 0x0000, 0x4B37),
    ("CRC-16/USB", 16, 0x8005, 0xFFFF, True, True, 0xFFFF, 0xB4C8),
    ("CRC-16/BUYPASS", 16, 0x8005, 0x0000, False, False, 0x0000, 0xFEE8),
    ("CRC-16/DNP", 16, 0x3D65, 0x0000, True, True, 0xFFFF, 0xEA82),
    ("CRC-16/EN-13757", 16, 0x3D65, 0x0000, False, False, 0xFFFF, 0xC2B7),
    ("CRC-16/DECT-X", 16, 0x0589, 0x0000, False, False, 0x0000, 0x007F),
    ("CRC-16/T10-DIF", 16, 0x8BB7, 0x0000, False, False, 0x0000, 0xD0DB),
    ("CRC-16/CDMA2000", 16, 0xC867, 0xFFFF, False, False, 0x0000, 0x4C06),
    ("CRC-8", 8, 0x07, 0x00, False, False, 0x00, 0xF4),
    ("CRC-8/MAXIM", 8, 0x31, 0x00, True, True, 0x00, 0xA1),
    ("CRC-8/ROHC", 8, 0x07, 0xFF, True, True, 0x00, 0xD0),
    ("CRC-8/DARC", 8, 0x39, 0x00, True, True, 0x00, 0x15),
    ("CRC-8/DVB-S2", 8, 0xD5, 0x00, False, False, 0x00, 0xBC),
    ("CRC-8/ITU", 8, 0x07, 0x00, False, False, 0x55, 0xA1),
    ("CRC-8/SAE-J1850", 8, 0x1D, 0xFF, False, False, 0xFF, 0x4B),
    ("CRC-8/WCDMA", 8, 0x9B, 0x00, True, True, 0x00, 0x25),
    ("CRC-32", 32, 0x04C11DB7, 0xFFFFFFFF, True, True, 0xFFFFFFFF, 0xCBF43926),
    ("CRC-32/BZIP2", 32, 0x04C11DB7, 0xFFFFFFFF, False, False, 0xFFFFFFFF, 0xFC891918),
    ("CRC-32/MPEG-2", 32, 0x04C11DB7, 0xFFFFFFFF, False, False, 0x00000000, 0x0376E6E7),
    ("CRC-32/POSIX", 32, 0x04C11DB7, 0x00000000, False, False, 0xFFFFFFFF, 0x765E7680),
    ("CRC-32/JAMCRC", 32, 0x04C11DB7, 0xFFFFFFFF, True, True, 0x00000000, 0x340BC6D9),
    ("CRC-32C", 32, 0x1EDC6F41, 0xFFFFFFFF, True, True, 0xFFFFFFFF, 0xE3069283),
    ("CRC-32/XFER", 32, 0x000000AF, 0x00000000, False, False, 0x00000000, 0xBD0BE338),
)
CRCS = tuple(Crc(*row[:7], check=row[7]) for row in _CATALOGUE)


def _hex(bits: Bits, sep: str = "") -> str:
    usable = len(bits) - len(bits) % 8
    return sep.join(f"{b:02X}" for b in np.packbits(bits[:usable]).tolist())


def sync_hits(
    bits: Bits, word: SyncWord, max_errors: int = MAX_SYNC_ERRORS
) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    """Where the word starts with at most `max_errors` bit errors: (upright, inverted)."""
    if len(bits) < word.width:
        empty = np.zeros(0, np.int64)
        return empty, empty
    pm = 1.0 - 2.0 * bits.astype(np.float64)
    ref = 1.0 - 2.0 * word.bits().astype(np.float64)
    c = np.correlate(pm, ref, mode="valid")
    need = word.width - 2 * max_errors
    return np.flatnonzero(c >= need), np.flatnonzero(c <= -need)


def random_hit_probability(word: SyncWord, max_errors: int = MAX_SYNC_ERRORS) -> float:
    """Chance a random position matches the word (one polarity) within `max_errors`."""
    return sum(math.comb(word.width, e) for e in range(max_errors + 1)) / 2.0**word.width


def period_of(hits: NDArray[np.int64]) -> tuple[int, int] | None:
    """The most common spacing between consecutive hits and how many pairs share it."""
    if len(hits) < MIN_RECURRENCES:
        return None
    gaps: Counter[int] = Counter(int(g) for g in np.diff(hits))
    period, count = gaps.most_common(1)[0]
    return (int(period), count) if count >= MIN_RECURRENCES - 1 else None


@dataclass(frozen=True)
class DecodedFrame:
    index: int
    start_bit: int
    length_bits: int
    crc: Literal["pass", "fail", "truncated"]
    header_hex: str
    payload_hex: str
    payload: bytes


@dataclass(frozen=True)
class FrameResult:
    word: SyncWord
    inverted: bool
    hits: int
    period: int  # frame length in bits, sync word included
    recurrences: int  # consecutive hit pairs at the period
    crc: Crc | None  # the catalogue CRC that passes most frames, None if none passes any
    passes: int
    complete: int  # frames fully inside the stream
    frames: tuple[DecodedFrame, ...]
    descrambler: str | None = None  # the additive descrambler applied to each frame, if any


def binomial_tail(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p), bounded below at 1e-300."""
    if k <= 0:
        return 1.0
    log_terms = [
        math.lgamma(n + 1)
        - math.lgamma(i + 1)
        - math.lgamma(n - i + 1)
        + i * math.log(p)
        + (n - i) * math.log1p(-p)
        for i in range(k, n + 1)
    ]
    top = max(log_terms)
    total = top + math.log(sum(math.exp(t - top) for t in log_terms))
    return max(math.exp(total), 1e-300)


def _passes(crc: Crc, rows: NDArray[np.uint8]) -> NDArray[np.bool_]:
    """Which complete frames (equal-length rows, CRC field last) carry a valid `crc`."""
    if rows.size == 0 or rows.shape[1] <= crc.width:
        return np.zeros(len(rows), bool)
    received = rows[:, -crc.width :].astype(np.int64) @ (1 << np.arange(crc.width - 1, -1, -1))
    return crc.compute_many(rows[:, : -crc.width]) == received


def find_frames(
    bits: Bits,
    word: SyncWord,
    crcs: tuple[Crc, ...] = CRCS,
    descrambler: Descrambler | None = None,
) -> FrameResult | None:
    """Frames delimited by a recurring sync word, each checked against every catalogued CRC."""
    upright, inverted = sync_hits(bits, word)
    use_inverted = len(inverted) > len(upright)
    hits = inverted if use_inverted else upright
    found = period_of(hits)
    if found is None:
        return None
    period, recurrences = found
    stream = (1 - bits).astype(np.uint8) if use_inverted else bits
    # Keep hits on the period's grid, anchored at the first hit that starts a run of them.
    starts = [int(h) for h in hits if (int(h) - int(hits[0])) % period == 0]
    bodies: list[tuple[int, Bits | None]] = []
    for s in starts:
        end = s + period
        body = stream[s + word.width : end] if end <= len(stream) else None
        if body is not None and descrambler is not None:
            body = descrambler.frame(body)  # each frame restarts the register after its sync word
        bodies.append((s, body))
    complete = [b for _, b in bodies if b is not None]
    rows = np.array(complete, np.uint8) if complete else np.zeros((0, 0), np.uint8)
    best: Crc | None = None
    best_passes = 0
    for crc in crcs:
        passes = int(_passes(crc, rows).sum())
        if passes > best_passes:
            best, best_passes = crc, passes
    frames: list[DecodedFrame] = []
    width = best.width if best else 16
    passed = _passes(best, rows) if best else np.zeros(len(complete), bool)
    done = 0  # index into the complete frames
    for i, (s, body) in enumerate(bodies):
        if body is None:
            tail = stream[s + word.width :]
            frames.append(
                DecodedFrame(
                    i + 1, s, len(stream) - s, "truncated", _hex(tail[:32], " "), _hex(tail), b""
                )
            )
            continue
        data = body[:-width]
        ok = bool(passed[done])
        done += 1
        frames.append(
            DecodedFrame(
                i + 1,
                s,
                period,
                "pass" if ok else "fail",
                _hex(data[:32], " "),
                _hex(data),
                np.packbits(data[: len(data) - len(data) % 8]).tobytes(),
            )
        )
    return FrameResult(
        word,
        use_inverted,
        len(hits),
        period,
        recurrences,
        best,
        best_passes,
        len(complete),
        tuple(frames),
        descrambler.name if descrambler else None,
    )
