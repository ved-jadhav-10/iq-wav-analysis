"""Frame synchronisation and CRC checks on a decoded bit stream (PLAN M6).

A catalogued sync word is searched for with up to MAX_SYNC_ERRORS bit errors, in both
polarities (a 180-degree phase ambiguity through a code with odd-weight generators inverts
the data). The frame length is the spacing at which the sync word recurs. Each complete frame
is then checked against the catalogued CRCs, which cover the bits between the sync word and
the CRC field at the end of the frame (the layout `dsp.synth.bits.FrameSpec` writes). A CRC
pass is the only thing here that can make a result VERIFIED.

The catalogues are data copied from the standards (not imported from dsp.synth, which is the
test oracle): CCSDS 131.0-B's attached sync marker, and the CRC-16 parameter sets from the
reveng catalogue.
"""

import math
from collections import Counter
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

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


SYNC_WORDS = (SyncWord("CCSDS ASM", 0x1ACFFC1D, 32),)


@dataclass(frozen=True)
class Crc:
    name: str
    width: int
    poly: int
    init: int
    refin: bool
    refout: bool
    xorout: int

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


CRCS = (
    Crc("CRC-16/CCITT-FALSE", 16, 0x1021, 0xFFFF, False, False, 0x0000),
    Crc("CRC-16/X-25", 16, 0x1021, 0xFFFF, True, True, 0xFFFF),
    Crc("CRC-16/XMODEM", 16, 0x1021, 0x0000, False, False, 0x0000),
)


def _to_int(bits: Bits) -> int:
    return int("".join(map(str, bits.tolist())), 2) if len(bits) else 0


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


def find_frames(bits: Bits, word: SyncWord, crcs: tuple[Crc, ...] = CRCS) -> FrameResult | None:
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
        bodies.append((s, stream[s + word.width : end] if end <= len(stream) else None))
    complete = [b for _, b in bodies if b is not None]
    best: Crc | None = None
    best_passes = 0
    for crc in crcs:
        passes = sum(
            1
            for b in complete
            if len(b) > crc.width and crc.compute(b[: -crc.width]) == _to_int(b[-crc.width :])
        )
        if passes > best_passes:
            best, best_passes = crc, passes
    frames: list[DecodedFrame] = []
    width = best.width if best else 16
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
        ok = best is not None and best.compute(data) == _to_int(body[-width:])
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
    )
