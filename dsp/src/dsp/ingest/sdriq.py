"""SDRangel `.sdriq` recordings: a 32-byte header, then interleaved I/Q.

The header holds the sample rate (uint32), centre frequency (uint64), start time (uint64,
milliseconds since the Unix epoch), sample size in bits (uint32), a filler word, and a CRC-32 of
the first 28 bytes, all little-endian. With a matching CRC its values are MEASURED; with a
mismatched one they are reported as HYPOTHESIS with the mismatch as evidence.

A 16-bit build writes int16 I/Q (ci16_le). A 24-bit build writes each 24-bit component in a
32-bit word (ci32_le), so its levels read 48 dB below full scale; the warning says so.
"""

import struct
import zlib
from datetime import UTC, datetime
from pathlib import Path

from dsp.evidence import EvidenceLevel
from dsp.ingest.reader import Segment
from dsp.ingest.recording import Recording, stated, unknown

HEADER_BYTES = 32
_METHOD = ".sdriq header"


def read_sdriq(path: Path) -> Recording:
    size = path.stat().st_size
    with path.open("rb") as file:
        header = file.read(HEADER_BYTES)
    if len(header) < HEADER_BYTES:
        raise ValueError(f"{path.name} is shorter than an .sdriq header")
    rate, center, start_ms, bits, _, crc = struct.unpack("<IQQIII", header)
    computed = zlib.crc32(header[:28]) & 0xFFFFFFFF
    ok = computed == crc
    level = EvidenceLevel.MEASURED if ok else EvidenceLevel.HYPOTHESIS
    check = (
        ("Header CRC-32 matches.",)
        if ok
        else (
            f"Header CRC-32 mismatch (stored 0x{crc:08x}, computed 0x{computed:08x}): the "
            "header may be corrupt or this may not be an .sdriq file.",
        )
    )
    if bits == 16:
        datatype = stated(
            "datatype", "ci16_le", f"{_METHOD}: sample size 16", level=level, evidence=check
        )
    elif bits == 24:
        datatype = stated(
            "datatype",
            "ci32_le",
            f"{_METHOD}: sample size 24",
            level=level,
            evidence=check,
            warnings=(
                "24-bit components are stored in 32-bit words: levels read 48 dB below full scale.",
            ),
        )
    else:
        datatype = unknown(
            "datatype",
            _METHOD,
            f"The header states a sample size of {bits} bits; SDRangel writes 16 or 24. "
            + check[0],
            "Choose the sample format.",
        )
    payload = size - HEADER_BYTES
    if rate > 0:
        sample_rate = stated("sample_rate", float(rate), _METHOD, level=level, evidence=check)
    else:
        sample_rate = unknown(
            "sample_rate",
            _METHOD,
            "The header states a sample rate of 0.",
            "Enter the sample rate.",
        )
    start = None
    try:
        when = datetime.fromtimestamp(start_ms / 1000, UTC)
        start = stated(
            "start_time",
            when.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            _METHOD,
            level=level,
            evidence=check,
        )
    except (OverflowError, OSError, ValueError):
        pass
    return Recording(
        name=path.name,
        segments=(Segment(path, HEADER_BYTES, payload),),
        datatype=datatype,
        data_offset=stated("data_offset", HEADER_BYTES, f"{_METHOD}: fixed 32-byte header"),
        sample_rate=sample_rate,
        center_frequency=stated(
            "center_frequency", float(center), _METHOD, level=level, evidence=check
        ),
        iq_method="SDRangel sample layout: real (I) before imaginary (Q)",
        start_time=start,
    )
