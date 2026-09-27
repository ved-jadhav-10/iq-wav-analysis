"""VITA 49 (VRT) packet recordings: signal-data packets carry the samples, context packets the
sample rate, RF reference frequency, bandwidth and payload format.

Packets are big-endian 32-bit words. The header gives the packet type (bits 31-28), whether a
class ID (bit 27) and, for data packets, a trailer (bit 26) are present, the integer and
fractional timestamp types (bits 23-22, 21-20) and the packet size in words (bits 15-0). A
stream ID follows for types 1, 3, 4 and 5. Recordings framed by the VITA 49.1 link layer
("VRLP" ... "VEND") are unwrapped first. The file is scanned through a memory map; one segment
per data packet is kept as arrays.

Context fields follow CIF0 in descending bit order: reference point (30, one word), bandwidth
(29, two), IF reference (28, two), RF reference (27, two), RF offset (26, two), IF band offset
(25, two), reference level (24), gain (23), over-range count (22), sample rate (21, two), then
timestamp adjustment (20, two), calibration time (19), temperature (18), device ID (17, two),
state (16) and the payload format (15, two). Frequencies and rates are 64-bit fixed point with
20 fractional bits. Enabled CIF1/2/3/7 words sit between CIF0 and the fields.

Limits: only the first data stream is read; others are counted in a warning. Payload formats
other than real or Cartesian-complex fixed point (8/16/32 bits) and IEEE floats, with no event
or channel tags, are UNKNOWN. Without a payload format the format sniffer proposes one from the
payload bytes. Little-endian (byte-swapped) VRT files are not recognised.
"""

import mmap
import struct
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from dsp.evidence import EvidenceLevel, Parameter, revise
from dsp.ingest.formats import SampleFormat
from dsp.ingest.rate import center_frequency_parameter, rate_candidates, sample_rate_parameter
from dsp.ingest.reader import SegmentTable
from dsp.ingest.recording import Recording, stated
from dsp.ingest.sniff import BLOCK_BYTES, BLOCKS, sniff_blocks

_METHOD = "VITA 49 context packet"
_DATA_TYPES = (0, 1)
_CONTEXT_TYPES = (4,)
_HAS_STREAM_ID = (1, 3, 4, 5, 6, 7)
_RADIX = float(1 << 20)
# Words each CIF0 field occupies, for bits 30 down to 16 (bit 15 is the payload format).
_FIELD_WORDS = {30: 1, 29: 2, 28: 2, 27: 2, 26: 2, 25: 2, 24: 1, 23: 1, 22: 1, 21: 2, 20: 2,
                19: 1, 18: 1, 17: 2, 16: 1}  # fmt: skip


@dataclass
class _Context:
    bandwidth: float | None = None
    rf_frequency: float | None = None
    sample_rate: float | None = None
    payload_format: int | None = None


@dataclass
class _Scan:
    stream: int | None = None  # the data stream read; None for packets without a stream ID
    seen_data: bool = False
    offsets: list[int] = field(default_factory=lambda: [])
    lengths: list[int] = field(default_factory=lambda: [])
    other_streams: set[int | None] = field(default_factory=lambda: set())
    contexts: dict[int | None, _Context] = field(default_factory=lambda: {})
    context_changes: list[str] = field(default_factory=lambda: [])
    packets: int = 0
    other_packets: int = 0
    warnings: list[str] = field(default_factory=lambda: [])


def read_vita49(path: Path) -> Recording:
    size = path.stat().st_size
    if size < 8:
        raise ValueError(f"{path.name} is too short to hold a VITA 49 packet")
    scan = _Scan()
    with path.open("rb") as file, mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as m:
        if m[:4] == b"VRLP":
            _frames(m, size, scan)
        else:
            _packets(m, 0, size, scan)
        if not scan.seen_data:
            raise ValueError(f"{path.name} holds no VITA 49 signal-data packets")
        head = _payload_sample(m, scan)
    context = scan.contexts.get(scan.stream) or next(iter(scan.contexts.values()), _Context())
    warnings = list(scan.warnings)
    if scan.other_streams:
        warnings.append(
            f"{len(scan.other_streams)} other data stream(s) are present; only stream "
            f"{_sid(scan.stream)} is read."
        )
    if scan.other_packets:
        warnings.append(f"{scan.other_packets} extension or command packet(s) were skipped.")
    table = SegmentTable(
        (path,),
        np.zeros(len(scan.offsets), dtype=np.int32),
        np.array(scan.offsets, dtype=np.int64),
        np.array(scan.lengths, dtype=np.int64),
    )
    facts = (
        f"{scan.packets} VITA 49 packets; {len(scan.offsets)} signal-data packets on stream "
        f"{_sid(scan.stream)}."
    )
    datatype, from_format = _datatype(context.payload_format, head, facts)
    if warnings or scan.context_changes:
        datatype = revise(datatype, warnings=(*datatype.warnings, *warnings, *scan.context_changes))
    fmt = datatype.value if isinstance(datatype.value, str) else None
    if context.sample_rate:
        sample_rate = stated("sample_rate", context.sample_rate, f"{_METHOD}: sample rate field")
    else:
        sample_rate = sample_rate_parameter(
            rate_candidates(path.name, fmt),
            fmt,
            "Sample-rate candidates: file name and standard SDR device rates",
            "No context packet states a sample rate.",
        )
    if context.rf_frequency is not None:
        evidence = (f"Context bandwidth {context.bandwidth:,.6g} Hz.",) if context.bandwidth else ()
        center = stated(
            "center_frequency",
            context.rf_frequency,
            f"{_METHOD}: RF reference frequency field",
            evidence=evidence,
        )
    else:
        center = center_frequency_parameter(
            path.name,
            "Centre-frequency candidates: file name",
            "No context packet states an RF reference frequency.",
        )
    first = int(scan.offsets[0])
    return Recording(
        name=path.name,
        segments=table,
        datatype=datatype,
        data_offset=stated(
            "data_offset", first, "VITA 49 packet headers: the first signal-data payload"
        ),
        sample_rate=sample_rate,
        center_frequency=center,
        iq_method="VITA 49 Cartesian complex: I before Q"
        if from_format
        else "Convention for I/Q recordings: the in-phase component is stored first",
        iq_convention=None
        if from_format
        else "No context packet states the payload format, so nothing in the file says I comes "
        "first. Swap if a known carrier sits on the wrong side of the spectrum.",
    )


def _frames(m: mmap.mmap, size: int, scan: _Scan) -> None:
    """VITA 49.1 link-layer frames: 'VRLP', count and size word, packets, 'VEND' or a CRC."""
    pos = 0
    while pos + 12 <= size:
        if m[pos : pos + 4] != b"VRLP":
            scan.warnings.append(f"{size - pos} bytes at byte {pos} don't start a VRL frame.")
            return
        (word,) = struct.unpack_from(">I", m, pos + 4)
        words = word & 0xFFFFF
        if words < 3 or pos + words * 4 > size:
            scan.warnings.append(f"The VRL frame at byte {pos} is truncated or malformed.")
            return
        _packets(m, pos + 8, pos + (words - 1) * 4, scan)
        pos += words * 4


def _packets(m: mmap.mmap, pos: int, end: int, scan: _Scan) -> None:
    while pos + 4 <= end:
        (header,) = struct.unpack_from(">I", m, pos)
        kind, words = header >> 28, header & 0xFFFF
        if words == 0 or pos + words * 4 > end or kind > 7:
            if scan.packets == 0:
                raise ValueError("the file doesn't start with a VITA 49 packet")
            scan.warnings.append(
                f"{end - pos} bytes at byte {pos} don't form a VITA 49 packet; reading stops."
            )
            return
        scan.packets += 1
        prologue = 1 + (kind in _HAS_STREAM_ID)
        sid = struct.unpack_from(">I", m, pos + 4)[0] if kind in _HAS_STREAM_ID else None
        prologue += 2 * ((header >> 27) & 1)
        prologue += (header >> 22) & 3 != 0
        prologue += 2 * ((header >> 20) & 3 != 0)
        if kind in _DATA_TYPES:
            trailer = (header >> 26) & 1
            length = (words - prologue - trailer) * 4
            if not scan.seen_data:
                scan.seen_data, scan.stream = True, sid
            if sid == scan.stream and length > 0:
                scan.offsets.append(pos + prologue * 4)
                scan.lengths.append(length)
            elif sid != scan.stream:
                scan.other_streams.add(sid)
        elif kind in _CONTEXT_TYPES:
            _context(m, pos + prologue * 4, pos + words * 4, sid, scan, scan.packets)
        else:
            scan.other_packets += 1
        pos += words * 4


def _context(m: mmap.mmap, pos: int, end: int, sid: int | None, scan: _Scan, n: int) -> None:
    if pos + 4 > end:
        return
    (cif0,) = struct.unpack_from(">I", m, pos)
    pos += 4 + 4 * sum((cif0 >> bit) & 1 for bit in (1, 2, 3, 7))
    found = _Context()
    for bit in range(30, 14, -1):
        if not (cif0 >> bit) & 1:
            continue
        words = 2 if bit == 15 else _FIELD_WORDS[bit]
        if pos + 4 * words > end:
            return
        if bit == 29:
            found.bandwidth = struct.unpack_from(">q", m, pos)[0] / _RADIX
        elif bit == 27:
            found.rf_frequency = struct.unpack_from(">q", m, pos)[0] / _RADIX
        elif bit == 21:
            found.sample_rate = struct.unpack_from(">q", m, pos)[0] / _RADIX
        elif bit == 15:
            found.payload_format = struct.unpack_from(">Q", m, pos)[0]
        pos += 4 * words
    known = scan.contexts.get(sid)
    if known is None:
        scan.contexts[sid] = found
        return
    for name in ("sample_rate", "rf_frequency", "payload_format"):
        before, after = getattr(known, name), getattr(found, name)
        if before is None:
            setattr(known, name, after)
        elif after is not None and after != before and len(scan.context_changes) < 5:
            scan.context_changes.append(
                f"Context packet {n} changes the {name.replace('_', ' ')} from {before} to "
                f"{after}; the first value is reported."
            )


def _payload_sample(m: mmap.mmap, scan: _Scan) -> list[bytes]:
    """Payload bytes from packets spread across the file, for the sniffer."""
    picks = np.linspace(0, len(scan.offsets) - 1, min(BLOCKS, len(scan.offsets))).astype(int)
    out: list[bytes] = []
    for i in picks:
        data, k = b"", int(i)
        while len(data) < BLOCK_BYTES and k < len(scan.offsets):
            data += m[scan.offsets[k] : scan.offsets[k] + scan.lengths[k]]
            k += 1
        out.append(data[: BLOCK_BYTES // 16 * 16])
    return out


def _datatype(word: int | None, head: list[bytes], facts: str) -> tuple[Parameter, bool]:
    """The datatype from the payload format field, else from the sniffer; and which it was."""
    if word is None:
        sniffed = sniff_blocks(head).datatype
        return (
            revise(
                sniffed,
                evidence=(
                    facts,
                    "No context packet states the payload format; the format sniffer scored "
                    "the payload bytes.",
                    *sniffed.evidence,
                ),
            ),
            False,
        )
    w1 = word >> 32
    complexity, item_format = (w1 >> 29) & 3, (w1 >> 24) & 0x1F
    event_tags, channel_tags = (w1 >> 20) & 7, (w1 >> 16) & 0xF
    packing, item = ((w1 >> 6) & 0x3F) + 1, (w1 & 0x3F) + 1
    detail = (
        f"Payload format: {('real', 'complex Cartesian', 'complex polar', 'reserved')[complexity]}"
        f", item format 0x{item_format:02x}, {item}-bit items in {packing}-bit fields."
    )
    kind = {0x00: "i", 0x10: "u", 0x0E: "f", 0x0F: "f"}.get(item_format)
    width_ok = (kind in ("i", "u") and item in (8, 16, 32)) or (
        (item_format, item) in ((0x0E, 32), (0x0F, 64))
    )
    if (
        complexity > 1
        or kind is None
        or not width_ok
        or packing != item
        or event_tags
        or channel_tags
    ):
        return (
            Parameter(
                id="datatype",
                name="Sample format",
                value=None,
                level=EvidenceLevel.UNKNOWN,
                method=f"{_METHOD}: payload format field",
                evidence=(facts, detail, "Sanket doesn't decode this payload format."),
                resolve_hint="Convert the recording to 8/16/32-bit fixed point or IEEE floats.",
            ),
            True,
        )
    endian = "" if item == 8 else "_be"
    datatype = f"{'c' if complexity == 1 else 'r'}{kind}{item}{endian}"
    SampleFormat.parse(datatype)  # every combination above is a SigMF datatype
    return stated(
        "datatype", datatype, f"{_METHOD}: payload format field", evidence=(facts, detail)
    ), True


def _sid(stream: int | None) -> str:
    return "(no stream ID)" if stream is None else f"0x{stream:08x}"
