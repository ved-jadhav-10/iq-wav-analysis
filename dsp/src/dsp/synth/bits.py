"""Bit-level ground truth: packing, CRCs, frames and scramblers.

Bits are uint8 arrays of 0s and 1s, most significant bit first within each byte, so a sync word
or CRC reads the same way as in the standards that define it.

CRCs are specified by the usual catalogue parameters (width, polynomial, initial value, input and
output reflection, final XOR); each preset carries its catalogue check value, the CRC of the
ASCII bytes "123456789", which the tests confirm.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

Bits = NDArray[np.uint8]


def to_bits(data: bytes | NDArray[Any]) -> Bits:
    return np.unpackbits(np.frombuffer(bytes(data), dtype=np.uint8))


def to_bytes(bits: NDArray[Any]) -> bytes:
    if len(bits) % 8:
        raise ValueError(f"{len(bits)} bits don't make whole bytes")
    return np.packbits(np.asarray(bits, dtype=np.uint8)).tobytes()


def int_bits(value: int, width: int) -> Bits:
    return np.array([(value >> (width - 1 - i)) & 1 for i in range(width)], dtype=np.uint8)


@dataclass(frozen=True)
class Crc:
    name: str
    width: int
    poly: int
    init: int
    refin: bool
    refout: bool
    xorout: int
    check: int  # CRC of b"123456789"

    def compute(self, bits: NDArray[Any]) -> int:
        """CRC of a bit sequence (any length), bit by bit."""
        top, mask = 1 << (self.width - 1), (1 << self.width) - 1
        reg = self.init
        data = np.asarray(bits, dtype=np.uint8)
        if self.refin:
            usable = len(data) - len(data) % 8
            data = np.concatenate([data[:usable].reshape(-1, 8)[:, ::-1].ravel(), data[usable:]])
        for bit in data:
            feedback = ((reg & top) != 0) ^ bool(bit)
            reg = (reg << 1) & mask
            if feedback:
                reg ^= self.poly
        if self.refout:
            reg = int(f"{reg:0{self.width}b}"[::-1], 2)
        return reg ^ self.xorout

    def bits(self, bits: NDArray[Any]) -> Bits:
        """The CRC as bits, most significant first, ready to append."""
        return int_bits(self.compute(bits), self.width)


CRCS: dict[str, Crc] = {
    c.name: c
    for c in (
        Crc("CRC-16/CCITT-FALSE", 16, 0x1021, 0xFFFF, False, False, 0x0000, 0x29B1),
        Crc("CRC-16/X-25", 16, 0x1021, 0xFFFF, True, True, 0xFFFF, 0x906E),
        Crc("CRC-16/XMODEM", 16, 0x1021, 0x0000, False, False, 0x0000, 0x31C3),
        Crc("CRC-32", 32, 0x04C11DB7, 0xFFFFFFFF, True, True, 0xFFFFFFFF, 0xCBF43926),
    )
}

# Sync words, most significant bit first, with their sources.
SYNC_WORDS: dict[str, tuple[int, int]] = {
    "CCSDS ASM": (0x1ACFFC1D, 32),  # CCSDS 131.0-B attached sync marker
    "Barker-13": (0b1111100110101, 13),
    "POCSAG": (0x7CD215D8, 32),  # ITU-R M.584 synchronisation codeword
}


@dataclass(frozen=True)
class FrameSpec:
    """sync word | counter | payload | CRC over counter and payload."""

    sync: str = "CCSDS ASM"
    counter_bits: int = 16
    payload_bytes: int = 64
    crc: str | None = "CRC-16/CCITT-FALSE"

    @property
    def sync_bits(self) -> Bits:
        value, width = SYNC_WORDS[self.sync]
        return int_bits(value, width)

    @property
    def length(self) -> int:
        crc = CRCS[self.crc].width if self.crc else 0
        return len(self.sync_bits) + self.counter_bits + 8 * self.payload_bytes + crc

    def truth(self) -> dict[str, Any]:
        return {
            "sync": self.sync,
            "syncWord": f"0x{SYNC_WORDS[self.sync][0]:X}",
            "syncBits": len(self.sync_bits),
            "counterBits": self.counter_bits,
            "payloadBits": 8 * self.payload_bytes,
            "crc": self.crc,
            "frameBits": self.length,
        }


def frames(spec: FrameSpec, payloads: NDArray[Any], first_count: int = 0) -> Bits:
    """One frame per payload row (bytes); the counter increments from `first_count`."""
    out: list[Bits] = []
    for i, payload in enumerate(np.asarray(payloads, dtype=np.uint8)):
        body = np.concatenate(
            [int_bits((first_count + i) % (1 << spec.counter_bits), spec.counter_bits),
             to_bits(payload)]
        )  # fmt: skip
        crc = CRCS[spec.crc].bits(body) if spec.crc else np.zeros(0, np.uint8)
        out.append(np.concatenate([spec.sync_bits, body, crc]))
    return np.concatenate(out) if out else np.zeros(0, np.uint8)


@dataclass(frozen=True)
class Scrambler:
    """Additive (synchronous) scrambler: data XOR a Fibonacci LFSR sequence.

    `taps` are the exponents of the feedback polynomial other than the constant term, highest
    first. The sequence obeys the polynomial's recurrence: for x^8 + x^7 + x^5 + x^3 + 1,
    a[k+8] = a[k+7] ^ a[k+5] ^ a[k+3] ^ a[k]. The first `degree` outputs are `seed`, most
    significant bit first, and the register restarts at every frame.
    """

    name: str
    taps: tuple[int, ...]
    seed: int

    def sequence(self, n: int) -> Bits:
        degree = self.taps[0]
        state = [(self.seed >> (degree - 1 - i)) & 1 for i in range(degree)]
        out = np.empty(n, dtype=np.uint8)
        for k in range(n):
            out[k] = state[0]
            feedback = state[0]
            for t in self.taps[1:]:
                feedback ^= state[t]
            state = [*state[1:], feedback]
        return out

    def apply(self, bits: NDArray[Any]) -> Bits:
        data = np.asarray(bits, dtype=np.uint8)
        return data ^ self.sequence(len(data))


SCRAMBLERS = {
    # CCSDS 131.0-B pseudo-randomiser: h(x) = x^8 + x^7 + x^5 + x^3 + 1, all ones at the start of
    # each frame; the sequence begins FF 48 0E C0.
    "CCSDS": Scrambler("CCSDS", (8, 7, 5, 3), 0xFF),
}
