"""AIS (ITU-R M.1371-6) on a demodulated bit stream: the system's own check, per packet.

AIS sends GMSK at 9,600 bit/s. Each packet is HDLC: a flag 01111110, the message bits and a
16-bit frame check sequence with a 0 stuffed after every run of five 1s, and a closing flag; the
whole stream is NRZI coded (a 0 is a change of level, a 1 no change). The FCS is CRC-16/X.25
(polynomial 0x1021 reflected, initial value and final XOR 0xFFFF) over the message bytes, each
byte read with its first transmitted bit as the least significant, and sent low byte first.

The check: NRZI-decode (which only looks at changes, so the bit polarity and a mirrored GMSK
spectrum do not matter), find the flags, take what lies between two flags, remove the stuffing and
test the CRC. A random stream puts a flag about once every 256 bits and a candidate frame passes
its CRC with probability 2^-16, so a verified packet is a `crc` proof; a run of them recurring is
what makes it significant (a single pass is not: at the 10^-6 level a handful of candidate frames
cannot rule out chance).

The message fields are laid out as in the Recommendation's Table 1 for the first few bits only:
message type (6 bits), repeat indicator (2) and MMSI (30), read most significant bit first from
the bits as transmitted. They are shown as a HYPOTHESIS: the check does not depend on them.

Limits: only whole-byte packets are checked (every position report and static message is); a
frame with a bit error fails its CRC and is not repaired; time-division gaps and the training
sequence's ramp are not modelled, the training sequence (0101...) only appears as flags found
after it.
"""

from dataclasses import dataclass
from itertools import pairwise

import numpy as np
from numpy.typing import NDArray

from dsp.framing import binomial_tail

Bits = NDArray[np.uint8]

FLAG = np.array([0, 1, 1, 1, 1, 1, 1, 0], np.uint8)
FCS_BITS = 16
MIN_FRAME_BITS = 80  # destuffed bits (data and FCS) worth testing: the shortest AIS message is 168
CRC_CHANCE = 2.0**-FCS_BITS
MIN_PASSES = 2  # one passing packet cannot clear alpha = 1e-6 against a random stream's candidates
POLY_REFLECTED = 0x8408
INIT = 0xFFFF
XOROUT = 0xFFFF


def crc16_x25(data: bytes) -> int:
    """CRC-16/X.25 (also called IBM-SDLC) of `data`; the check value of b"123456789" is 0x906E."""
    register = INIT
    for byte in data:
        register ^= byte
        for _ in range(8):
            register = (register >> 1) ^ POLY_REFLECTED if register & 1 else register >> 1
    return register ^ XOROUT


def nrzi_decode(bits: Bits) -> Bits:
    """1 where the level did not change, 0 where it did (the first bit has no predecessor and is
    dropped)."""
    b = np.asarray(bits, np.uint8)
    return (1 ^ (b[1:] ^ b[:-1])).astype(np.uint8)


def nrzi_encode(bits: Bits) -> Bits:
    """The inverse of `nrzi_decode` for a start level of 0: a 0 toggles, a 1 holds."""
    out = np.empty(len(bits) + 1, np.uint8)
    out[0] = 0
    for i, bit in enumerate(np.asarray(bits, np.uint8)):
        out[i + 1] = out[i] ^ (1 - bit)
    return out


def stuff(bits: Bits) -> Bits:
    """HDLC bit stuffing: a 0 after every five consecutive 1s."""
    out: list[int] = []
    ones = 0
    for bit in np.asarray(bits, np.uint8).tolist():
        out.append(bit)
        ones = ones + 1 if bit else 0
        if ones == 5:
            out.append(0)
            ones = 0
    return np.array(out, np.uint8)


def destuff(bits: Bits) -> Bits | None:
    """The bits with each stuffed 0 removed, or None if six 1s in a row (a flag or an abort)
    appear inside the frame."""
    out: list[int] = []
    ones = 0
    values = np.asarray(bits, np.uint8).tolist()
    i = 0
    while i < len(values):
        bit = values[i]
        if bit:
            ones += 1
            out.append(1)
            if ones == 5:
                i += 1
                if i < len(values) and values[i] == 1:
                    return None
                ones = 0
        else:
            ones = 0
            out.append(0)
        i += 1
    return np.array(out, np.uint8)


def bytes_lsb_first(bits: Bits) -> bytes:
    """Whole bytes from transmit-order bits, the first bit of each byte its least significant."""
    return np.packbits(np.asarray(bits, np.uint8).reshape(-1, 8)[:, ::-1], axis=1).tobytes()


def fcs_passes(frame: Bits) -> bool:
    """Whether a destuffed frame (data bits then the 16 FCS bits, in transmit order) is a whole
    number of bytes and its CRC-16/X.25 matches the FCS sent low byte first."""
    if len(frame) % 8 or len(frame) < MIN_FRAME_BITS:
        return False
    data = bytes_lsb_first(frame)
    return crc16_x25(data[:-2]) == int.from_bytes(data[-2:], "little")


def flag_positions(bits: Bits) -> list[int]:
    """Where the flag 01111110 starts, without overlapping hits."""
    b = np.asarray(bits, np.uint8)
    if len(b) < len(FLAG):
        return []
    windows = np.lib.stride_tricks.sliding_window_view(b, len(FLAG))
    hits = np.flatnonzero((windows == FLAG).all(axis=1)).tolist()
    out: list[int] = []
    for h in hits:
        if not out or h >= out[-1] + len(FLAG):
            out.append(h)
    return out


@dataclass(frozen=True)
class Packet:
    start_bit: int  # in the NRZI-decoded stream, the opening flag's first bit
    length_bits: int  # data and FCS, destuffed
    passes: bool
    data: bytes  # the message bits in field order, MSB first, without the FCS
    message_type: int
    mmsi: int


@dataclass(frozen=True)
class AisScan:
    packets: tuple[Packet, ...]  # every candidate frame that was long enough to test
    passes: int
    candidates: int
    p_value: float

    @property
    def passing(self) -> tuple[Packet, ...]:
        return tuple(p for p in self.packets if p.passes)


def scan(bits: Bits) -> AisScan | None:
    """The candidate frames between flags in the NRZI-decoded stream and how many pass their
    CRC; None when fewer than MIN_PASSES do."""
    decoded = nrzi_decode(bits)
    flags = flag_positions(decoded)
    packets: list[Packet] = []
    for a, b in pairwise(flags):
        frame = destuff(decoded[a + len(FLAG) : b])
        if frame is None or len(frame) < MIN_FRAME_BITS:
            continue
        ok = fcs_passes(frame)
        body = frame[:-FCS_BITS]
        padded = np.concatenate([body, np.zeros(-len(body) % 8, np.uint8)])
        field_bytes = np.packbits(padded).tobytes()
        weights = 1 << np.arange(5, -1, -1)
        kind = int((body[:6] * weights).sum()) if len(body) >= 6 else 0
        mmsi_bits = body[8:38]
        mmsi = int("".join(map(str, mmsi_bits.tolist())), 2) if len(mmsi_bits) == 30 else 0
        packets.append(Packet(a, len(frame), ok, field_bytes, kind, mmsi))
    passes = sum(p.passes for p in packets)
    if passes < MIN_PASSES:
        return None
    return AisScan(
        tuple(packets), passes, len(packets), binomial_tail(passes, len(packets), CRC_CHANCE)
    )
