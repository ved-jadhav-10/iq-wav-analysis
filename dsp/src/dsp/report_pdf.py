"""A results document as a PDF (PLAN §5 M7), for a report an analyst can read, print or file.

The page order is fixed: the title with the recording's files, the program and rule-set versions
and the results hash; the plain-language summary (`dsp.summary.render_summary`, verbatim, so the PDF
says nothing the results don't); the assumptions; capture quality; what needs review; then each
signal's headline, stages, proofs, warnings, unknowns, hypothesis ledger and first frames. Every
evidence level is a vector glyph and its word, never colour alone. An empty section says so.

The output is deterministic: the same results always give the same bytes (no clock, no random id).
Text is set in IBM Plex (SIL OFL, bundled in `dsp/fonts`); a character no bundled font has is drawn
as a visible `?` rather than failing the export, and `printable` says what will be drawn.
"""

from collections.abc import Sequence
from xml.sax.saxutils import escape

from dsp import _reportlab as rl
from dsp.evidence import EvidenceLevel, Parameter
from dsp.findings import Frame, Hypothesis, HypothesisSearch
from dsp.results import Results, Signal, StageResult, results_sha256
from dsp.summary import render_summary

MAX_FRAME_ROWS = 40
HEX_SHOWN = 64  # characters of a frame's payload (or header) shown before the ellipsis
HEADER_SHOWN = 32
ELLIPSIS = "…"

LEVEL_COLOR = {  # the light-theme tokens of frontend/src/styles/index.css
    EvidenceLevel.VERIFIED: "#1a7f37",
    EvidenceLevel.MEASURED: "#0b64c8",
    EvidenceLevel.ESTIMATED: "#7447d8",
    EvidenceLevel.HYPOTHESIS: "#946300",
    EvidenceLevel.UNKNOWN: "#59636e",
}
# Characters the bundled fonts lack, spelled in ASCII; any other missing character becomes "?".
TRANSLITERATIONS = {"≥": ">=", "≤": "<=", "→": "->", "←": "<-", "≈": "~"}
MUTED = "#59636e"
SANS, BOLD, MONO = "sans", "bold", "mono"


def _drawable(char: str) -> bool:
    return any(rl.has_glyph(font, char) for font in rl.FONT_CHAINS[SANS])


def printable(text: str) -> str:
    """The text as the PDF draws it: line breaks and controls become spaces, a few symbols the
    fonts lack are spelled in ASCII (>= <= -> <- ~), and any other missing character is a `?`."""
    out: list[str] = []
    for char in text:
        if char in "\r\n\t" or ord(char) < 32 or 0x7F <= ord(char) < 0xA0:
            out.append(" ")
        elif _drawable(char):
            out.append(char)
        else:
            out.append(TRANSLITERATIONS.get(char, "?"))
    return "".join(out)


def _font_for(char: str, style: str) -> str:
    chain = rl.FONT_CHAINS[style]
    return next((font for font in chain if rl.has_glyph(font, char)), chain[0])


def _markup(text: str, style: str) -> str:
    """ReportLab markup for `text`, switching font where the first font lacks a character."""
    runs: list[tuple[str, list[str]]] = []
    for char in printable(text):
        font = _font_for(char, style)
        if runs and runs[-1][0] == font:
            runs[-1][1].append(char)
        else:
            runs.append((font, [char]))
    base = rl.FONT_CHAINS[style][0]
    return "".join(
        escape("".join(chars))
        if font == base
        else f'<font name="{font}">{escape("".join(chars))}</font>'
        for font, chars in runs
    )


def _text(
    text: str,
    *,
    style: str = SANS,
    size: float = 8.5,
    color: str = "#1f2328",
    indent: float = 0.0,
    before: float = 0.0,
    after: float = 1.5,
    keep_next: bool = False,
) -> rl.Flowable:
    return rl.paragraph(
        _markup(text, style),
        font=rl.FONT_CHAINS[style][0],
        size=size,
        color=color,
        left_indent=indent,
        space_before=before,
        space_after=after,
        keep_with_next=keep_next,
    )


def _heading(text: str, level: int = 1) -> rl.Flowable:
    sizes = {1: 13.0, 2: 10.5, 3: 9.0}
    return _text(
        text,
        style=BOLD,
        size=sizes[level],
        before={1: 12.0, 2: 8.0, 3: 5.0}[level],
        after=3.0,
        keep_next=True,
    )


def _cell(text: str, style: str = SANS, size: float = 7.5, color: str = "#1f2328") -> rl.Flowable:
    return _text(text, style=style, size=size, color=color, after=0.0)


def _level_badge(level: EvidenceLevel, size: float = 7.5) -> rl.Flowable:
    return rl.level_badge(level.value, LEVEL_COLOR[level], rl.FONT_CHAINS[BOLD][0], size)


def _value(p: Parameter) -> str:
    if p.value is None:
        return "no value"
    value = f"{p.value:.6g}" if isinstance(p.value, float) else str(p.value)
    if p.uncertainty is not None and isinstance(p.value, int | float):
        value += f" ± {p.uncertainty:.2g}"
    return f"{value} {p.unit}" if p.unit else value


def _truncate(text: str, shown: int) -> str:
    return text if len(text) <= shown else text[:shown] + ELLIPSIS


def _parameter_table(params: Sequence[Parameter]) -> rl.Flowable:
    widths = (140.0, 135.0, 78.0)
    widths = (*widths, rl.CONTENT_WIDTH - sum(widths))
    rows: list[list[rl.Flowable]] = [
        [_cell(h, BOLD) for h in ("Parameter", "Value", "Level", "Method")]
    ]
    for p in params:
        rows.append([_cell(p.name), _cell(_value(p)), _level_badge(p.level), _cell(p.method)])
    return rl.table(rows, widths)


def _notes(
    params: Sequence[Parameter], stage_warnings: Sequence[str] = (), *, say_none: bool
) -> list[rl.Flowable]:
    """What the tables can't hold: proofs, warnings, UNKNOWN reasons with what would settle
    them, and conventions. With `say_none`, an empty kind says so."""
    groups: list[tuple[str, list[str], str]] = [
        (
            "Proofs",
            [f"{p.name}: {p.proof.kind}, {p.proof.detail}" for p in params if p.proof],
            "none (no value is VERIFIED)",
        ),
        (
            "Warnings",
            [*stage_warnings, *(f"{p.name}: {w}" for p in params for w in p.warnings)],
            "none",
        ),
        (
            "Unknown",
            [
                f"{p.name}: {'; '.join(p.evidence)}. To resolve: {p.resolve_hint}"
                for p in params
                if p.level is EvidenceLevel.UNKNOWN
            ],
            "nothing is UNKNOWN",
        ),
        (
            "Taken on a convention",
            [f"{p.name}: {p.convention}" for p in params if p.convention],
            "none",
        ),
    ]
    out: list[rl.Flowable] = []
    for label, lines, empty in groups:
        if lines:
            out.append(
                _text(f"{label}:", style=BOLD, size=8, before=3.0, after=1.0, keep_next=True)
            )
            out += [_text(f"- {line}", size=8, indent=8.0) for line in lines]
        elif say_none:
            out.append(_text(f"{label}: {empty}.", size=8, color=MUTED))
    return out


def _title(results: Results, digest: str) -> list[rl.Flowable]:
    files = results.recording.files
    names = ", ".join(f.name for f in files) or "no recording files (analysed in memory)"
    story: list[rl.Flowable] = [
        _text("Sanket results report", style=BOLD, size=19, after=2.0),
        _text(names, style=BOLD, size=10.5, after=6.0),
    ]
    if files:
        widths = (140.0, 52.0, rl.CONTENT_WIDTH - 192.0)
        rows = [[_cell(h, BOLD) for h in ("File", "Bytes", "SHA-256")]]
        rows += [
            [_cell(f.name), _cell(f"{f.size_bytes:,}"), _cell(f.sha256, MONO, 6.8)] for f in files
        ]
        story.append(rl.table(rows, widths))
    else:
        story.append(_text("No file hashes: the recording was held in memory.", color=MUTED))
    catalogues = ", ".join(f"{c.name} {c.version}" for c in results.catalogues) or "none recorded"
    story += [
        _text(
            f"Container {results.recording.container}, {results.recording.samples:,} samples.",
            before=5.0,
        ),
        _text(f"Sanket version {results.sanket_version}."),
        _text(f"Catalogue versions: {catalogues}."),
        _text("Results SHA-256 (of the results JSON this report was made from):"),
        _text(digest, style=MONO, size=7.5, indent=8.0),
    ]
    return story


def _summary(results: Results) -> list[rl.Flowable]:
    story = [_heading("Summary")]
    for line in render_summary(results).rstrip("\n").split("\n"):
        if not line.strip():
            story.append(rl.spacer(4.0))
            continue
        indent = len(line) - len(line.lstrip(" "))
        story.append(_text(line.strip(), indent=indent * 3.0, after=1.0))
    return story


def _assumptions(results: Results) -> list[rl.Flowable]:
    params = results.assumptions.parameters()
    return [
        _heading("Assumptions"),
        _text("What the analysis took as given about the recording.", color=MUTED),
        _parameter_table(params),
        *_notes(params, say_none=False),
    ]


def _stage_lines(stage: StageResult) -> list[rl.Flowable]:
    story = [_text(f"{stage.name} ({stage.id}), {stage.status}: {stage.summary}", size=8.5)]
    if stage.error:
        story.append(_text(f"Error: {stage.error}", size=8, indent=8.0))
    return story


def _capture(results: Results) -> list[rl.Flowable]:
    story = [_heading("Capture quality")]
    stage = next((s for s in results.stages if s.id == "capture"), None)
    if stage is None:
        return [*story, _text("This document has no capture-quality stage.", color=MUTED)]
    story += _stage_lines(stage)
    if stage.parameters:
        story.append(_parameter_table(stage.parameters))
    else:
        story.append(_text("The stage reported no parameters.", color=MUTED))
    if stage.warnings:
        story.append(_text("Warnings:", style=BOLD, size=8, before=3.0, after=1.0, keep_next=True))
        story += [_text(f"- {w}", size=8, indent=8.0) for w in stage.warnings]
    else:
        story.append(_text("Warnings: none.", size=8, color=MUTED))
    story += _notes(stage.parameters, say_none=False)
    return story


def _needs_review(results: Results) -> list[rl.Flowable]:
    story = [_heading("Needs review")]
    items = results.needs_review
    if not items:
        return [*story, _text("Nothing rests on a convention.")]
    story.append(
        _text(
            f"{len(items)} value(s) rest on a convention rather than evidence and need an "
            "analyst's review.",
        )
    )
    widths = (110.0, 120.0, 90.0, rl.CONTENT_WIDTH - 320.0)
    rows = [[_cell(h, BOLD) for h in ("Where", "Parameter", "Value", "Convention")]]
    for item in items:
        where = " / ".join(x for x in (item.signal, item.stage) if x) or "assumptions"
        rows.append(
            [_cell(where), _cell(item.name), _cell(str(item.value)), _cell(item.convention)]
        )
    return [*story, rl.table(rows, widths)]


def _ledger(signal: Signal) -> list[rl.Flowable]:
    story = [_heading("Hypothesis ledger", 2)]
    search: HypothesisSearch | None = signal.search
    if search is None:
        return [*story, _text(f"No search ran: {signal.no_search_reason}")]
    story.append(
        _text(
            f"Hypotheses tried: {search.tried:,} (every hypothesis is counted, including ones "
            f"not listed below). Correction: {search.correction}; alpha {search.alpha:g}; "
            f"smallest corrected threshold {search.smallest_threshold:.3g}. Shuffled-bit runs: "
            f"{search.shuffled_runs}, of which {search.shuffled_accepts} passed (0 is expected); "
            f"{search.shuffled_blocked} chain(s) blocked. Blind rate-1/n search: "
            f"{search.blind_searched} branch(es) searched, {search.blind_identified} identified. "
            f"Known-system checks (Match): {search.match_tried}.",
            size=8,
        )
    )
    if not search.rows:
        return [*story, _text("The ledger lists no rows.", color=MUTED)]
    widths = (52.0, 100.0, 80.0, 42.0, 46.0, 46.0)
    widths = (*widths, rl.CONTENT_WIDTH - sum(widths))
    headers = ("Layer", "Candidate", "Statistic", "p", "Threshold", "Outcome", "Reason")
    rows = [[_cell(h, BOLD, 7.0) for h in headers]]
    for h in search.rows:
        rows.append(_ledger_row(h))
    return [*story, rl.table(rows, widths), _text(f"{len(search.rows)} row(s) listed.", size=8)]


def _ledger_row(h: Hypothesis) -> list[rl.Flowable]:
    p = "n/a" if h.p_value is None else f"{h.p_value:.3g}"
    cells = (h.layer, h.candidate, h.statistic, p, f"{h.threshold:.3g}", h.outcome, h.reason)
    return [_cell(c, SANS, 7.0) for c in cells]


def _frame_row(f: Frame) -> list[rl.Flowable]:
    return [
        _cell(str(f.index), size=7.0),
        _cell(str(f.start_bit), size=7.0),
        _cell(f.sync_word, MONO, 6.5),
        _cell(str(f.length_bits), size=7.0),
        _cell(f.crc, size=7.0),
        _cell(_truncate(f.header_hex, HEADER_SHOWN), MONO, 6.5),
        _cell(_truncate(f.payload_hex, HEX_SHOWN), MONO, 6.5),
    ]


def _frames(signal: Signal) -> list[rl.Flowable]:
    story = [_heading("Frames", 2)]
    frames = signal.frames
    if not frames:
        return [*story, _text(f"No frames: {signal.no_frames_reason}")]
    passing = sum(f.crc == "pass" for f in frames)
    story.append(_text(f"Frames in the table: {len(frames)}, {passing} pass their CRC.", size=8))
    widths = (24.0, 46.0, 62.0, 38.0, 46.0, 90.0)
    widths = (*widths, rl.CONTENT_WIDTH - sum(widths))
    headers = ("#", "Start bit", "Sync word", "Bits", "CRC", "Header", "Payload")
    rows = [[_cell(h, BOLD, 7.0) for h in headers]]
    rows += [_frame_row(f) for f in frames[:MAX_FRAME_ROWS]]
    story.append(rl.table(rows, widths))
    if len(frames) > MAX_FRAME_ROWS:
        more = len(frames) - MAX_FRAME_ROWS
        story.append(
            _text(
                f"Showing the first {MAX_FRAME_ROWS} of {len(frames)} frames; {more} more are "
                "not shown here (they are in the results document). Long payloads are cut at "
                f"{HEX_SHOWN} characters with an ellipsis.",
                size=8,
                color=MUTED,
            )
        )
    return story


def _signal(index: int, signal: Signal) -> list[rl.Flowable]:
    story: list[rl.Flowable] = [
        _heading(f"Signal {index + 1}: {signal.id}, {signal.label}", 2),
        _level_badge(signal.level, 9.0),
        _text(signal.headline, size=9.5, before=2.0, after=3.0),
    ]
    params = [p for stage in signal.stages for p in stage.parameters]
    for stage in signal.stages:
        story += _stage_lines(stage)
        if stage.parameters:
            story.append(_parameter_table(stage.parameters))
        else:
            story.append(_text("No parameters reported.", size=8, color=MUTED))
    if not signal.stages:
        story.append(_text("This signal reports no stages.", color=MUTED))
    stage_warnings = [f"{s.name}: {w}" for s in signal.stages for w in s.warnings]
    story += _notes(params, stage_warnings, say_none=True)
    return [*story, *_ledger(signal), *_frames(signal)]


def render_pdf(results: Results) -> bytes:
    """The PDF for a results document, byte-identical for identical results."""
    digest = results_sha256(results)
    story = [
        *_title(results, digest),
        *_summary(results),
        *_assumptions(results),
        *_capture(results),
        *_needs_review(results),
        _heading("Signals"),
    ]
    if results.signals:
        for i, signal in enumerate(results.signals):
            story += _signal(i, signal)
    else:
        story.append(_text("No signals are reported in this document."))
    names = ", ".join(f.name for f in results.recording.files)
    return rl.build_pdf(
        story,
        footer=printable(f"Sanket {results.sanket_version} · results SHA-256 {digest[:16]}"),
        title=printable(f"Sanket results report: {names or 'in-memory recording'}"),
        author=printable(f"Sanket {results.sanket_version}"),
        subject=f"Results SHA-256 {digest}",
    )
