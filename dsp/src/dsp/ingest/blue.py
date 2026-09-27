"""MIDAS Blue (X-Midas, NeXtMidas, REDHAWK) files: a 512-byte header control block, then data.

The header states the byte orders (`head_rep`, `data_rep`: "EEEI" little-endian, "IEEE"
big-endian), where the data starts and how long it is, the file type, and a two-letter format:
S (scalar, real) or C (complex), then B, I, L, F or D (int8, int16, int32, float32, float64).
For a type-1000 file the adjunct's `xdelta` is the sample interval when `xunits` is 1 (seconds),
so the sample rate is 1 / xdelta. The centre frequency comes from an `RF_FREQ` keyword, in the
main keyword string or the extended header, when one is present.

Limits: only type-1000/1001 files (one sample stream) are read; framed type-2000 data (spectra,
frames) is UNKNOWN. Detached headers (data in a separate `.det` file) are read when that file is
beside the header. int64 ("X") and packed-bit data have no sample format and are UNKNOWN.
"""

import struct
from pathlib import Path

from dsp.evidence import Parameter, revise
from dsp.ingest.rate import center_frequency_parameter, rate_candidates, sample_rate_parameter
from dsp.ingest.reader import Segment
from dsp.ingest.recording import Recording, clamp, stated, unknown

HEADER_BYTES = 512
_METHOD = "MIDAS Blue header"
_TYPES = {"B": ("i", 8), "I": ("i", 16), "L": ("i", 32), "F": ("f", 32), "D": ("f", 64)}
_TYPE_BYTES = {"A": 1, "B": 1, "I": 2, "L": 4, "X": 8, "F": 4, "D": 8}
_REPS = {"EEEI": "<", "IEEE": ">"}
# The extended header is keyword records; anything larger is corruption, not metadata.
_MAX_EXTENDED = 16 << 20


def read_blue(path: Path) -> Recording:
    with path.open("rb") as file:
        hcb = file.read(HEADER_BYTES)
        if len(hcb) < HEADER_BYTES or hcb[:4] != b"BLUE":
            raise ValueError(f"{path.name} is not a MIDAS Blue file")
        head_rep, data_rep = hcb[4:8].decode("latin-1"), hcb[8:12].decode("latin-1")
        if head_rep not in _REPS or data_rep not in _REPS:
            raise ValueError(f"{path.name}: unknown byte order {head_rep!r}/{data_rep!r}")
        o = _REPS[head_rep]
        detached, _, _, ext_start, ext_size = struct.unpack(o + "5i", hcb[12:32])
        data_start, data_size = struct.unpack(o + "dd", hcb[32:48])
        (file_type,) = struct.unpack(o + "i", hcb[48:52])
        code = hcb[52:54].decode("latin-1")
        keywords = _main_keywords(hcb[160:256], o)
        _, xdelta, xunits = struct.unpack(o + "ddi", hcb[256:276])
        if 0 < ext_size <= _MAX_EXTENDED and ext_start > 0:
            file.seek(ext_start * 512)
            keywords.update(_extended_keywords(file.read(ext_size), o))
    data_path = path.with_suffix(".det") if detached else path
    if not data_path.exists():
        raise ValueError(f"{path.name} is a detached header and {data_path.name} is missing")
    facts = f"Blue header: type {file_type}, format {code!r}, data {data_rep}, xunits {xunits}."
    datatype = _datatype(code, file_type, data_rep, facts)
    fmt_name = datatype.value if isinstance(datatype.value, str) else None
    offset = int(data_start)
    length, warnings = clamp(offset, int(data_size), data_path.stat().st_size, "Blue header")
    if warnings:
        datatype = revise(datatype, warnings=warnings)
    if xunits == 1 and xdelta > 0:
        rate = float(f"{1 / xdelta:.12g}")
        sample_rate = stated("sample_rate", rate, f"{_METHOD}: 1 / xdelta ({xdelta!r} s)")
    else:
        sample_rate = sample_rate_parameter(
            rate_candidates(path.name, fmt_name),
            fmt_name,
            "Sample-rate candidates: file name and standard SDR device rates",
            f"The adjunct doesn't state a sample interval in seconds (xunits {xunits}, "
            f"xdelta {xdelta!r}).",
        )
    rf = keywords.get("RF_FREQ")
    if isinstance(rf, float):
        center = stated("center_frequency", rf, f"{_METHOD}: RF_FREQ keyword")
    else:
        center = center_frequency_parameter(
            path.name,
            "Centre-frequency candidates: file name",
            "The Blue file has no RF_FREQ keyword, so it doesn't record a centre frequency.",
        )
    return Recording(
        name=path.name,
        segments=(Segment(data_path, offset, length),),
        datatype=datatype,
        data_offset=stated("data_offset", offset, f"{_METHOD}: data_start"),
        sample_rate=sample_rate,
        center_frequency=center,
        iq_method="MIDAS Blue complex format: real before imaginary",
    )


def _datatype(code: str, file_type: int, data_rep: str, facts: str) -> Parameter:
    endian = "_le" if data_rep == "EEEI" else "_be"
    if file_type not in (1000, 1001):
        return unknown(
            "datatype",
            _METHOD,
            f"{facts} Type {file_type} isn't a single sample stream (type 2000 holds frames).",
            "Export the data as a type-1000 file.",
        )
    if len(code) != 2 or code[0] not in "SC" or code[1] not in _TYPES:
        return unknown(
            "datatype",
            _METHOD,
            f"{facts} Format {code!r} has no sample format.",
            "Convert the data to 8/16/32-bit integers or 32/64-bit floats.",
        )
    kind, bits = _TYPES[code[1]]
    suffix = "" if bits == 8 else endian
    datatype = f"{'c' if code[0] == 'C' else 'r'}{kind}{bits}{suffix}"
    return stated("datatype", datatype, _METHOD, evidence=(facts,))


def _main_keywords(raw: bytes, o: str) -> dict[str, float | str]:
    (length,) = struct.unpack(o + "i", raw[:4])
    text = raw[4 : 4 + max(0, min(length, 92))].decode("latin-1")
    out: dict[str, float | str] = {}
    for field in text.split("\x00"):
        if "=" in field:
            key, value = field.split("=", 1)
            out[key.strip().upper()] = _number(value)
    return out


def _extended_keywords(raw: bytes, o: str) -> dict[str, float | str]:
    """Keyword records: total length, header length, tag length, type, value, tag, padding."""
    out: dict[str, float | str] = {}
    p = 0
    while p + 8 <= len(raw):
        lkey, lext, ltag, kind = struct.unpack(o + "ihbc", raw[p : p + 8])
        if lkey < 8 or lext < 8 or lext > lkey or p + lkey > len(raw):
            break
        value = raw[p + 8 : p + lkey - lext + 8]
        tag = raw[p + lkey - lext + 8 : p + lkey - lext + 8 + max(0, ltag)].decode("latin-1")
        type_char = kind.decode("latin-1")
        if type_char == "A":
            out[tag.upper()] = _number(value.rstrip(b"\x00").decode("latin-1"))
        elif type_char in "BILXFD" and len(value) >= _TYPE_BYTES[type_char]:
            fmt = {"B": "b", "I": "h", "L": "i", "X": "q", "F": "f", "D": "d"}[type_char]
            out[tag.upper()] = float(struct.unpack(o + fmt, value[: _TYPE_BYTES[type_char]])[0])
        p += lkey
    return out


def _number(text: str) -> float | str:
    try:
        return float(text)
    except ValueError:
        return text.strip()
