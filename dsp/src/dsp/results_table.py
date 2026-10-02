"""A results document as one CSV table of every reported value (PLAN §5 M7).

One row per `Parameter`: the recording's assumptions first (no signal, no stage), then the
whole-recording stages, then each signal's stages in order. The evidence level, the proof and
the convention stay in their own columns, so a spreadsheet can't show a number without them;
an UNKNOWN row has an empty value and carries its reason in `evidence`. The signal rows begin
with a `headline` row, so each signal's label and level are in the table as well; a VERIFIED
one cites its CRC-passing frames as the proof. The output is deterministic: the same results
always give the same bytes.
"""

import csv
import io
from collections.abc import Iterator

from dsp.evidence import Parameter
from dsp.results import Results, results_sha256

COLUMNS = (
    "signal",
    "stage",
    "id",
    "name",
    "value",
    "unit",
    "uncertainty",
    "level",
    "method",
    "proof",
    "convention",
    "evidence",
    "warnings",
)
JOINER = " | "


def _row(signal: str, stage: str, p: Parameter) -> list[object]:
    return [
        signal,
        stage,
        p.id,
        p.name,
        "" if p.value is None else p.value,
        p.unit or "",
        "" if p.uncertainty is None else p.uncertainty,
        p.level.value,
        p.method,
        f"{p.proof.kind}: {p.proof.detail}" if p.proof else "",
        p.convention or "",
        JOINER.join(p.evidence),
        JOINER.join(p.warnings),
    ]


def _fact(stage: str, id: str, name: str, value: str, method: str) -> list[object]:
    """A row that identifies the analysis (a file's hash, a rule set's version, the document's
    own hash): computed, so MEASURED, with no unit or uncertainty."""
    return ["", stage, id, name, value, "", "", "MEASURED", method, "", "", "", ""]


def _rows(results: Results) -> Iterator[list[object]]:
    yield _fact("document", "results_sha256", "Results SHA-256", results_sha256(results),
                "SHA-256 of the results JSON this table was made from")  # fmt: skip
    yield _fact("document", "sanket_version", "Sanket version", results.sanket_version, "Program")
    for c in results.catalogues:
        yield _fact("document", f"catalogue_{c.name}", f"Catalogue {c.name}", c.version, "Version")
    for f in results.recording.files:
        yield _fact(
            "recording", "sha256", f.name, f.sha256, f"SHA-256 of the file ({f.size_bytes} B)"
        )
    for p in results.assumptions.parameters():
        yield _row("", "assumptions", p)
    for stage in results.stages:
        for p in stage.parameters:
            yield _row("", stage.id, p)
    for signal in results.signals:
        passing = sum(f.crc == "pass" for f in signal.frames)
        yield [
            signal.id,
            "headline",
            "headline",
            signal.label,
            signal.headline,
            "",
            "",
            signal.level.value,
            "",
            f"crc: {passing} of {len(signal.frames)} frames in the table pass" if passing else "",
            "",
            "",
            "",
        ]
        for stage in signal.stages:
            for p in stage.parameters:
                yield _row(signal.id, stage.id, p)


def render_csv(results: Results) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    writer.writerows(_rows(results))
    return out.getvalue()
