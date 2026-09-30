"""A detection's frame table as text: JSON, CSV, hex or bits (PLAN §5 M6).

JSON and CSV carry every frame with its CRC outcome, so a reader sees the failures too. Hex and
bits are for feeding a payload on to another tool, so they carry only the frames whose CRC
passed, one payload per line, and say so in the file name (`ExportFormat.description`). The
output is deterministic: the same frames always give the same bytes.
"""

import csv
import io
import json
from collections.abc import Sequence
from typing import Literal, get_args

from dsp.report import Frame

ExportFormat = Literal["json", "csv", "hex", "bits"]
FORMATS: tuple[ExportFormat, ...] = get_args(ExportFormat)

DESCRIPTIONS: dict[ExportFormat, str] = {
    "json": "every frame with its CRC outcome",
    "csv": "every frame with its CRC outcome",
    "hex": "payload bytes of the CRC-passing frames, one frame per line",
    "bits": "payload bits of the CRC-passing frames, one frame per line",
}
MEDIA_TYPES: dict[ExportFormat, str] = {
    "json": "application/json",
    "csv": "text/csv",
    "hex": "text/plain",
    "bits": "text/plain",
}
COLUMNS = ("index", "start_bit", "length_bits", "crc", "sync_word", "header_hex", "payload_hex")


def render(frames: Sequence[Frame], fmt: ExportFormat) -> str:
    """The table in `fmt`. An empty table is a valid, empty document."""
    if fmt == "json":
        rows = [f.model_dump(by_alias=True) for f in frames]
        return json.dumps({"frames": rows}, indent=2, ensure_ascii=False) + "\n"
    if fmt == "csv":
        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(COLUMNS)
        for f in frames:
            writer.writerow([getattr(f, c) for c in COLUMNS])
        return out.getvalue()
    passing = [f.payload_hex for f in frames if f.crc == "pass"]
    if fmt == "hex":
        lines = passing
    else:
        lines = [f"{int(h, 16):0{4 * len(h)}b}" if h else "" for h in passing]
    return "".join(f"{line}\n" for line in lines)
