"""A plain-language summary of a results document (PLAN §5 M7), for the top of an export.

It is a fixed template over the document, never a model: every sentence comes from a value the
analysis reported, with that value's evidence level beside it, so the summary can say nothing the
results don't. What was proved comes first, then what was only estimated or assumed, then what is
still unknown and what would settle it. The output is deterministic.
"""

from dsp.evidence import EvidenceLevel, Parameter
from dsp.results import Results, Signal

PLAIN_LEVEL = {
    EvidenceLevel.VERIFIED: "proved on this recording",
    EvidenceLevel.MEASURED: "read from the file or entered",
    EvidenceLevel.ESTIMATED: "estimated",
    EvidenceLevel.HYPOTHESIS: "a hypothesis, not proved",
    EvidenceLevel.UNKNOWN: "unknown",
}
KEY_STAGES = ("estimate", "classify", "demod", "fec", "frame")


def _value(p: Parameter) -> str:
    value = f"{p.value:.6g}" if isinstance(p.value, float) else str(p.value)
    text = f"{value} {p.unit}" if p.unit else value
    if p.uncertainty is not None and isinstance(p.value, int | float):
        text += f" ± {p.uncertainty:.2g}"
    return text


def _line(p: Parameter) -> str:
    return f"{p.name}: {_value(p)} ({PLAIN_LEVEL[p.level]})"


def _signal(index: int, signal: Signal) -> list[str]:
    parameters = [p for stage in signal.stages for p in stage.parameters]
    lines = [f"Signal {index + 1} ({signal.id}), {signal.level.value}: {signal.headline}"]
    proved = [p for p in parameters if p.level is EvidenceLevel.VERIFIED]
    if proved:
        lines.append("  Proved:")
        lines += [f"    - {_line(p)}; {p.proof.kind if p.proof else ''}" for p in proved]
    passing = sum(f.crc == "pass" for f in signal.frames)
    if signal.frames:
        lines.append(f"  Frames in the table: {len(signal.frames)}, {passing} pass their CRC.")
    else:
        lines.append(f"  No frames: {signal.no_frames_reason}")
    lines.append("  Not proved:")
    others = [
        p
        for stage in signal.stages
        if stage.id in KEY_STAGES
        for p in stage.parameters
        if p.level not in (EvidenceLevel.VERIFIED, EvidenceLevel.UNKNOWN)
    ]
    lines += [f"    - {_line(p)}" for p in others] or ["    - nothing reported"]
    unknown = [p for p in parameters if p.level is EvidenceLevel.UNKNOWN]
    if unknown:
        lines.append("  Still unknown:")
        lines += [f"    - {p.name}: {p.resolve_hint}" for p in unknown]
    if signal.search is not None:
        s = signal.search
        lines.append(
            f"  The blind search counted {s.tried:,} hypotheses; thresholds are corrected for "
            f"that count, and {s.shuffled_accepts} of {s.shuffled_runs} shuffled-bit runs "
            "passed (0 is the expected number)."
        )
    return lines


def render_summary(results: Results) -> str:
    a = results.assumptions
    ingest = next((s for s in results.stages if s.id == "ingest"), None)
    lines = [f"Sanket {results.sanket_version} results summary", ""]
    if ingest is not None:
        lines.append(f"Recording: {ingest.summary}.")
    lines.append("Taken as given about the recording:")
    lines += [f"  - {_line(p)}" for p in a.parameters() if p.level is not EvidenceLevel.UNKNOWN]
    lines += [
        f"  - {p.name}: UNKNOWN; {p.resolve_hint}"
        for p in a.parameters()
        if p.level is EvidenceLevel.UNKNOWN
    ]
    detect = next((s for s in results.stages if s.id == "detect"), None)
    if detect is not None:
        lines.append(f"Detection: {detect.summary}.")
    for i, signal in enumerate(results.signals):
        lines += ["", *_signal(i, signal)]
    review = results.needs_review
    lines += [""]
    if review:
        lines.append(
            f"{len(review)} value(s) rest on a convention rather than evidence and need an "
            "analyst's review:"
        )
        lines += [f"  - {r.name} = {r.value}: {r.convention}" for r in review]
    else:
        lines.append("No value rests on a convention.")
    return "\n".join(lines) + "\n"
