"""NumPy `.npy` arrays: the header states the element type and shape, so the format is MEASURED.

A one-dimensional array is read as it is typed: complex floats as I/Q, anything else as real.
A two-column real array (N, 2) is proposed as I/Q pairs on a stated convention. The header is
parsed as a Python literal, never executed, and the data is never loaded whole.

Limits: planar layouts (I and Q as separate blocks: shape (2, N), or (N, 2) in Fortran order),
more than two dimensions, structured and object arrays, and element types with no sample format
(int64, float16, bool) are UNKNOWN with the reason. An .npy file records no sample rate or
centre frequency; both come from file-name candidates.
"""

import ast
import math
import struct
from pathlib import Path
from typing import Any, cast

from dsp.evidence import EvidenceLevel, Parameter, revise
from dsp.ingest.formats import SampleFormat
from dsp.ingest.rate import center_frequency_parameter, rate_candidates, sample_rate_parameter
from dsp.ingest.reader import Segment
from dsp.ingest.recording import Recording, clamp, stated, unknown

MAGIC = b"\x93NUMPY"
_KINDS = {"c": "f", "f": "f", "i": "i", "u": "u"}
_METHOD = ".npy header"


def read_npy(path: Path) -> Recording:
    size = path.stat().st_size
    with path.open("rb") as file:
        head = file.read(12)
        if head[:6] != MAGIC or len(head) < 10:
            raise ValueError(f"{path.name} is not a NumPy .npy file")
        major = head[6]
        if major == 1:
            (length,), start = struct.unpack("<H", head[8:10]), 10
        elif major in (2, 3):
            (length,), start = struct.unpack("<I", head[8:12]), 12
        else:
            raise ValueError(f"{path.name}: unsupported .npy version {major}")
        file.seek(start)
        text = file.read(min(length, 1 << 20)).decode("latin-1")
    try:
        header = ast.literal_eval(text)
    except (ValueError, SyntaxError) as error:
        raise ValueError(f"{path.name}: the .npy header isn't a literal dict: {error}") from error
    if not isinstance(header, dict):
        raise ValueError(f"{path.name}: the .npy header isn't a dict")
    fields = cast(dict[str, Any], header)
    offset = start + length
    descr, fortran, shape = fields.get("descr"), fields.get("fortran_order"), fields.get("shape")
    facts = f".npy header: dtype {descr!r}, shape {shape!r}, fortran_order {fortran!r}."
    datatype, convention, item = _datatype(descr, fortran, shape, facts)
    fmt_name = datatype.value if isinstance(datatype.value, str) else None
    elements = math.prod(cast(tuple[int, ...], shape)) if _is_shape(shape) else 0
    length_bytes, warnings = clamp(offset, elements * item, size, ".npy header")
    if warnings:
        datatype = revise(datatype, warnings=warnings)
    return Recording(
        name=path.name,
        segments=(Segment(path, offset, length_bytes),),
        datatype=datatype,
        data_offset=stated("data_offset", offset, f"{_METHOD}: the array data follows it"),
        sample_rate=sample_rate_parameter(
            rate_candidates(path.name, fmt_name),
            fmt_name,
            "Sample-rate candidates: file name and standard SDR device rates",
            "An .npy file doesn't record its sample rate.",
        ),
        center_frequency=center_frequency_parameter(
            path.name,
            "Centre-frequency candidates: file name",
            "An .npy file doesn't record its centre frequency.",
        ),
        iq_method="NumPy complex layout: the real part is stored first"
        if convention is None
        else "Two-column array: the first column is taken as I",
        iq_convention=convention,
    )


def _is_shape(shape: object) -> bool:
    return isinstance(shape, tuple) and all(
        isinstance(n, int) and n >= 0 for n in cast(tuple[object, ...], shape)
    )


def _datatype(
    descr: object, fortran: object, shape: object, facts: str
) -> tuple[Parameter, str | None, int]:
    """The datatype Parameter, the I/Q convention if one is needed, and the element size."""

    def refuse(why: str, hint: str) -> tuple[Parameter, str | None, int]:
        return unknown("datatype", _METHOD, f"{facts} {why}", hint), None, 0

    if not isinstance(descr, str) or not _is_shape(shape):
        return refuse(
            "Structured or malformed arrays hold no single sample stream.",
            "Save the samples as a plain numeric array.",
        )
    order, code = (descr[0], descr[1:]) if descr[:1] in "<>|=" else ("=", descr)
    kind, digits = code[:1], code[1:]
    if kind not in _KINDS or not digits.isdigit():
        return refuse(
            f"Element type {descr!r} isn't a sample format.", "Save the samples as numbers."
        )
    item = int(digits)
    bits = item * 8 // (2 if kind == "c" else 1)
    endian = {"<": "_le", ">": "_be"}.get(order, "")  # "=" is the writer's order, unknown here
    if bits == 8:
        endian = ""
    elif not endian:
        return refuse(
            f'Element type {descr!r} states no byte order ("=" means the writing machine\'s).',
            "Re-save the array with an explicit byte order.",
        )
    dims = tuple(n for n in cast(tuple[int, ...], shape) if n != 1) or (1,)
    two_columns = kind != "c" and len(dims) == 2 and dims[1] == 2 and fortran is False
    if len(dims) > 1 and not two_columns:
        planar = len(dims) == 2 and 2 in dims
        return refuse(
            "I and Q are stored as separate blocks (planar), not interleaved."
            if planar
            else f"A {len(dims)}-dimensional array isn't one sample stream.",
            "Save the samples as a 1-D complex array, or as (N, 2) rows of I and Q.",
        )
    shape_char = "c" if kind == "c" or two_columns else "r"
    datatype = f"{shape_char}{_KINDS[kind]}{bits}{endian}"
    try:
        known = SampleFormat.parse(datatype).is_sigmf
    except ValueError:
        known = False
    if not known:
        return refuse(f"Element type {descr!r} has no sample format.", "Convert the array.")
    if two_columns:
        convention = (
            "A real array with two columns is taken as rows of I and Q; nothing in the file "
            "says so. If the columns are separate signals, save one as a 1-D array."
        )
        param = stated(
            "datatype",
            datatype,
            _METHOD,
            level=EvidenceLevel.HYPOTHESIS,
            evidence=(facts,),
            convention=convention,
        )
        return param, convention, item
    return stated("datatype", datatype, _METHOD, evidence=(facts,)), None, item
