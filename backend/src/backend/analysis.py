"""One recording's analysis, shared by the server (`recordings.py`) and `sanket analyse`: the
analyst's entries applied to the file's Assumptions, one detection's chain run with its failure
contained, and the results document assembled from the reports.

The results document holds the per-stage conclusions only (PLAN §3). The frame table, the
hypothesis ledger and the constellation of a `DetectionReport` have no place in schema 0.4.0
yet; they arrive with the exports (PLAN §5 M7), and the server still shows them.
"""

from collections.abc import Callable, Sequence
from importlib.metadata import version

from dsp.analyse import analyse
from dsp.detect import Detection, detect, detection_parameters
from dsp.evidence import EvidenceLevel
from dsp.ingest.dispatch import AnyRecording
from dsp.ingest.recording import entered
from dsp.report import DetectionReport, StageReport
from dsp.results import Assumptions, Results, Signal, StageResult

# Values the analyst entered, by assumption name; each replaces the file's own entry.
Entries = tuple[tuple[str, float | str], ...]


def assumptions_with(stated: Assumptions, entries: Entries) -> Assumptions:
    """`stated` with each entry as MEASURED "entered by the analyst", conflicts warned."""
    fields = {name: getattr(stated, name) for name in Assumptions.model_fields}
    for name, value in entries:
        fields[name] = entered(name, value, prior=fields[name])
    return Assumptions.model_validate(fields)


def numeric_rate(assumptions: Assumptions) -> float | None:
    """The sample rate as a number, or None while it is UNKNOWN."""
    rate = assumptions.sample_rate.value
    return rate if isinstance(rate, int | float) else None


def failed_analysis(detection: Detection, error: str) -> DetectionReport:
    """`dsp.analyse.analyse` raised for this detection: report it honestly rather than failing
    the whole recording. The detect stage still stands (it's what produced the box); a second,
    failed stage carries the error, and the top-level level stays ESTIMATED - the level of the
    one stage that actually succeeded."""
    detect_stage = StageReport(
        id="detect",
        name="Detect",
        status="done",
        summary="Band found by the detector",
        level=EvidenceLevel.ESTIMATED,
        parameters=detection_parameters(detection),
    )
    failed_stage = StageReport(
        id="analyse",
        name="Analyse",
        status="failed",
        summary="Analysis raised an exception",
        error=error,
    )
    return DetectionReport(
        label="Signal",
        kind="unknown",
        level=EvidenceLevel.ESTIMATED,
        headline=f"Analysis failed: {error}",
        stages=(detect_stage, failed_stage),
        search=None,
        no_search_reason="Analysis failed before a search could run.",
        no_frames_reason="Analysis failed before any frames could be found.",
    )


def analyse_detection(
    source: AnyRecording, detection: Detection, *, sample_rate: float | None, swap_iq: bool = False
) -> DetectionReport:
    """The decode chain over one detection; a chain that raises becomes a failed report, so one
    bad signal never sinks the recording."""
    try:
        with source.reader(swap_iq=swap_iq) as reader:
            return analyse(reader, detection, sample_rate=sample_rate)
    except Exception as exc:
        return failed_analysis(detection, str(exc))


def signal_of(index: int, report: DetectionReport) -> Signal:
    """A report's stages as a results `Signal`, ids matching the API's (`signal_0`, ...)."""
    stages = tuple(
        StageResult(
            id=s.id,
            name=s.name,
            status=s.status,
            summary=s.summary,
            parameters=s.parameters,
            warnings=s.warnings,
            error=s.error,
        )
        for s in report.stages
    )
    return Signal(id=f"signal_{index}", stages=stages)


def analyse_recording(
    source: AnyRecording,
    container: str,
    entries: Entries = (),
    *,
    real: bool,
    on_detection: Callable[[int, int], None] | None = None,
) -> tuple[Results, Sequence[DetectionReport]]:
    """Detect and analyse every signal in a recording; the results document and the reports.

    Without a sample rate the bands are found but not analysed, as in the server: a box in
    seconds and hertz needs one, and the results say so. `on_detection(done, total)` is called
    after each one."""
    swap_iq = dict(entries).get("iq_order") == "QI"
    assumptions = assumptions_with(source.assumptions, entries)
    sample_rate = numeric_rate(assumptions)
    with source.reader(swap_iq=swap_iq) as reader:
        samples = reader.num_samples
        detections = detect(reader, real=real).detections
    ingest = StageResult(
        id="ingest",
        name="Ingest",
        status="done",
        summary=f"{container}: {samples:,} samples",
    )
    if sample_rate is None:
        detect_stage = StageResult(
            id="detect",
            name="Detect",
            status="done",
            summary=f"{len(detections)} band(s) found, not analysed: the sample rate is UNKNOWN",
        )
        return Results(
            sanket_version=version("sanket-backend"),
            assumptions=assumptions,
            stages=(ingest, detect_stage),
        ), ()
    reports: list[DetectionReport] = []
    for i, d in enumerate(detections):
        reports.append(analyse_detection(source, d, sample_rate=sample_rate, swap_iq=swap_iq))
        if on_detection:
            on_detection(i + 1, len(detections))
    detect_stage = StageResult(
        id="detect", name="Detect", status="done", summary=f"{len(detections)} signal(s) found"
    )
    results = Results(
        sanket_version=version("sanket-backend"),
        assumptions=assumptions,
        stages=(ingest, detect_stage),
        signals=tuple(signal_of(i, r) for i, r in enumerate(reports)),
    )
    return results, reports
