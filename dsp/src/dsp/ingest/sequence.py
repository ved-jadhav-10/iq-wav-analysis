"""Numbered file sequences read as one recording: `rec_000.cu8`, `rec_001.cu8`, ... in order.

Recorders split long captures into numbered files. `numbered_sequence` finds a file's siblings
that differ only in the last run of digits before the extension, ordered by that number; a gap
in the numbers is reported. The files must all be WAV or all be raw. WAV files must agree on format,
channels and sample rate; the first file's header, `auxi` chunk and quadrature check stand for
the sequence. Raw files are sniffed first and last, and must agree.

Limits: the samples are taken to run on from one file to the next with nothing missing; a
recorder that drops samples between files leaves a discontinuity this can't see.
"""

import re
from collections.abc import Sequence
from itertools import pairwise
from pathlib import Path

from dsp.evidence import Alternative, EvidenceLevel, Parameter, revise
from dsp.ingest.assumptions import FORMAT_HINT
from dsp.ingest.raw import read_raw
from dsp.ingest.reader import Segment
from dsp.ingest.recording import Recording
from dsp.ingest.sniff import detect_container, sniff
from dsp.ingest.wav import read_header, read_wav

_DIGITS = re.compile(r"(\d+)(?!.*\d)")


def _number(path: Path) -> re.Match[str] | None:
    """The last run of digits in the name before its extension (`cu8` is not a number)."""
    return _DIGITS.search(path.stem)


def numbered_sequence(path: Path) -> tuple[Path, ...]:
    """The file and its numbered siblings, in number order; just the file if it has no number."""
    match = _number(path)
    if match is None:
        return (path,)
    prefix, suffix = path.stem[: match.start()], path.stem[match.end() :] + path.suffix
    pattern = re.compile(re.escape(prefix) + r"(\d+)" + re.escape(suffix) + "$")
    found = [
        (int(m.group(1)), p)
        for p in path.parent.iterdir()
        if p.is_file() and (m := pattern.match(p.name))
    ]
    return tuple(p for _, p in sorted(found))


def read_sequence(paths: Sequence[Path]) -> Recording:
    """One recording from files whose samples follow on from each other, in the given order."""
    if not paths:
        raise ValueError("a sequence needs at least one file")
    heads = [_container(p) for p in paths]
    if len(set(heads)) > 1:
        raise ValueError("a sequence must be all WAV files or all raw files")
    notes = _gaps(paths)
    return _wav_sequence(paths, notes) if heads[0] == "wav" else _raw_sequence(paths, notes)


def _wav_sequence(paths: Sequence[Path], notes: list[str]) -> Recording:
    first = read_wav(paths[0])
    h0 = first.header
    segments: list[Segment] = []
    for path in paths:
        h = read_header(path)
        if (h.format_tag, h.channels, h.bits, h.sample_rate) != (
            h0.format_tag,
            h0.channels,
            h0.bits,
            h0.sample_rate,
        ):
            raise ValueError(
                f"{path.name} ({h.channels} ch, {h.encoding}, {h.sample_rate} S/s) doesn't match "
                f"{paths[0].name} ({h0.channels} ch, {h0.encoding}, {h0.sample_rate} S/s)"
            )
        segments.append(Segment(path, h.data_offset, h.data_bytes))
    a = first.assumptions
    return Recording(
        name=f"{paths[0].name} (+{len(paths) - 1} files)",
        segments=tuple(segments),
        datatype=_note(first.datatype, len(paths), notes),
        data_offset=a.data_offset,
        sample_rate=a.sample_rate,
        center_frequency=a.center_frequency,
        iq_method=a.iq_order.method if a.iq_order else "real-valued",
        iq_convention=a.iq_order.convention if a.iq_order else None,
        start_time=first.start_time,
    )


def _raw_sequence(paths: Sequence[Path], notes: list[str]) -> Recording:
    first = read_raw(paths[0])
    datatype = first.datatype
    if len(paths) > 1:
        last = sniff(paths[-1]).datatype
        if last.value != datatype.value:
            datatype = Parameter(
                id="datatype",
                name="Sample format",
                value=None,
                level=EvidenceLevel.UNKNOWN,
                method=datatype.method,
                evidence=(
                    f"The first file sniffs as {datatype.value} and the last as {last.value}; "
                    "a sequence has one format.",
                ),
                alternatives=tuple(
                    Alternative(value=v) for v in (datatype.value, last.value) if v is not None
                ),
                resolve_hint=FORMAT_HINT,
            )
    a = first.assumptions
    return Recording(
        name=f"{paths[0].name} (+{len(paths) - 1} files)",
        segments=tuple(Segment(p, 0, p.stat().st_size) for p in paths),
        datatype=_note(datatype, len(paths), notes),
        data_offset=a.data_offset,
        sample_rate=a.sample_rate,
        center_frequency=a.center_frequency,
        iq_method=a.iq_order.method if a.iq_order else "real-valued",
        iq_convention=a.iq_order.convention if a.iq_order else None,
    )


def _container(path: Path) -> str | None:
    with path.open("rb") as file:
        return detect_container(file.read(40))


def _gaps(paths: Sequence[Path]) -> list[str]:
    numbers = [int(m.group(1)) for p in paths if (m := _number(p))]
    if len(numbers) != len(paths):
        return []
    missing = [n for a, b in pairwise(numbers) if b > a + 1 for n in range(a + 1, b)]
    if not missing:
        return []
    shown = ", ".join(map(str, missing[:10])) + (" ..." if len(missing) > 10 else "")
    return [f"The sequence skips file number(s) {shown}: samples are missing there."]


def _note(datatype: Parameter, files: int, notes: list[str]) -> Parameter:
    return revise(
        datatype,
        evidence=(*datatype.evidence, f"Read as one recording of {files} files in number order."),
        warnings=(*datatype.warnings, *notes),
    )
