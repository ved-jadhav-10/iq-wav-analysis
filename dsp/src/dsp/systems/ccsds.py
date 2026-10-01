"""CCSDS telemetry transfer frames (CCSDS 132.0-B-3) after the attached sync marker.

A frame is the marker, a 6-byte primary header, the data field and, at the end, a 16-bit frame
error control field that is CRC-16/CCITT-FALSE over everything from the header on (CCSDS 132.0-B-3
section 4.1.6). The system's own check is the marker recurring at the frame period and that CRC
passing on the frames; the version number 0 of every passing frame's header is a further
condition, since 132.0-B has no other TM version. The blind chain already searches for exactly
this framing, so this module reads what it found instead of searching again.
"""

from dataclasses import dataclass

TM_VERSION = 0
HEADER_BYTES = 6


@dataclass(frozen=True)
class PrimaryHeader:
    version: int
    spacecraft_id: int
    virtual_channel: int
    ocf_flag: bool
    master_channel_count: int
    virtual_channel_count: int
    data_field_status: int


def parse_header(frame: bytes) -> PrimaryHeader | None:
    """The primary header at the start of a frame's bytes (marker and check field excluded);
    None when the frame is shorter than a header."""
    if len(frame) < HEADER_BYTES:
        return None
    return PrimaryHeader(
        version=frame[0] >> 6,
        spacecraft_id=((frame[0] & 0x3F) << 4) | (frame[1] >> 4),
        virtual_channel=(frame[1] >> 1) & 0x7,
        ocf_flag=bool(frame[1] & 1),
        master_channel_count=frame[2],
        virtual_channel_count=frame[3],
        data_field_status=(frame[4] << 8) | frame[5],
    )
