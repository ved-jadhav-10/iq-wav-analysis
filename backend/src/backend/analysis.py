"""One recording's analysis, shared by the server (`recordings.py`) and `sanket analyse`: the
analyst's entries applied to the file's Assumptions, one detection's chain run with its failure
contained, and the results document assembled from the reports.

The results document holds each signal's conclusions (PLAN §3): its stage results, its label,
headline and level, the hypothesis ledger and the frame table of its `DetectionReport`. The
constellation and the eye are for the live views and stay out of it.
"""

from collections.abc import Callable, Iterable, Sequence
from importlib.metadata import version
from pathlib import Path

from dsp.analyse import analyse, measure_symbol_rate
from dsp.detect import Detection, detect, detection_parameters
from dsp.evidence import EvidenceLevel, Parameter, revise
from dsp.ingest.audio import AudioRecording
from dsp.ingest.dispatch import AnyRecording
from dsp.ingest.rate import structural_parameter, structural_test
from dsp.ingest.raw import RawRecording
from dsp.ingest.recording import entered
from dsp.quality import capture_quality
from dsp.report import DetectionReport, StageReport, cap_digital_labels, note_rate_basis
from dsp.results import Assumptions, RecordingIdentity, Results, Signal, StageResult
from dsp.versions import catalogue_versions

from .identity import recording_identity

# Values the analyst entered, by assumption name; each replaces the file's own entry.
Entries = tuple[tuple[str, float | str], ...]


def assumptions_with(
    stated: Assumptions, entries: Entries, inferred_rate: Parameter | None = None
) -> Assumptions:
    """`stated` with each entry as MEASURED "entered by the analyst", conflicts warned.
    `inferred_rate`, from `infer_sample_rate`, stands in for a sample rate the file left UNKNOWN;
    an entered rate still replaces it."""
    fields = {name: getattr(stated, name) for name in Assumptions.model_fields}
    if inferred_rate is not None:
        fields["sample_rate"] = inferred_rate
    for name, value in entries:
        fields[name] = entered(name, value, prior=fields[name])
    return Assumptions.model_validate(fields)


def numeric_rate(assumptions: Assumptions) -> float | None:
    """The sample rate as a number, or None while it is UNKNOWN."""
    rate = assumptions.sample_rate.value
    return rate if isinstance(rate, int | float) else None


# Signals whose symbol rate is tested against the sample-rate candidates, strongest first.
MAX_RATE_SIGNALS = 3


def infer_sample_rate(
    source: AnyRecording, detections: Sequence[Detection], *, swap_iq: bool = False
) -> Parameter | None:
    """The sample rate after a structural test, for a raw complex file that doesn't state one:
    each of the strongest linear signals' measured symbol rate, in symbols per sample, against
    the recognised symbol rates at every candidate sample rate (`dsp.ingest.rate`). `swap_iq`
    must be what `detections` were found with. Returns the HYPOTHESIS the test supports, or the
    UNKNOWN rate with every signal's findings added; None when there was nothing to test (a
    stated or real-valued recording, no candidates, no measurable symbol rate). Signals that
    decide on different rates decide nothing, and say so."""
    stated = source.assumptions.sample_rate
    fmt = source.sample_format
    if numeric_rate(source.assumptions) is not None or not isinstance(source, RawRecording):
        return None
    if fmt is None or not fmt.is_complex:
        return None  # a real channel's mirror image makes its bands ambiguous (capped later)
    candidates = source.rate_candidates
    signals = [d for d in detections if d.image_of is None]  # not a mirror image
    strongest = sorted(signals, key=lambda d: d.bandwidth * (d.stop - d.start), reverse=True)
    tried = strongest[:MAX_RATE_SIGNALS]
    measured: list[tuple[float, float]] = []
    for detection in tried:
        try:
            with source.reader(swap_iq=swap_iq) as reader:
                found = measure_symbol_rate(reader, detection)
        except (OSError, ValueError):
            continue  # one unreadable signal doesn't stop the others being tried
        if found is not None and 1e-6 <= found[0] <= 1:
            measured.append(found)
    if not candidates or not measured:
        return None
    # The error budget is divided over every signal tried, measurable or not.
    tests = [structural_test(r, u, candidates, searches=len(tried)) for r, u in measured]
    results = [structural_parameter(t, stated) for t in tests]
    rates = [t.decided.sample_rate for t in tests if t.decided and t.decided.sample_rate]
    agree = bool(rates) and all(abs(r / rates[0] - 1) < 1e-3 for r in rates)
    if agree and all(t.decided is not None for t in tests):
        first = results[0]
        extra = (
            f"All {len(tests)} signals tested agree on this rate.",
            *((f"{len(tried) - len(tests)} other signal(s) had no symbol rate to test.",)
              if len(tried) > len(tests) else ()),
        )  # fmt: skip
        return revise(first, evidence=(*first.evidence, *extra)) if len(tests) > 1 else first
    lines: list[str] = []
    for i, r in enumerate(results):
        new = (
            r.evidence
            if r.level is not EvidenceLevel.UNKNOWN
            else r.evidence[len(stated.evidence) :]
        )
        prefix = f"Signal {i + 1}: " if len(results) > 1 else ""
        lines += [prefix + line for line in new]
    if rates:
        lines.append(
            "The signals imply different sample rates, or some have no match, so none is preferred."
            if len(results) > 1
            else "No unambiguous match."
        )
    return revise(stated, evidence=(*stated.evidence, *lines))


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


def label_cap_reason(source: AnyRecording) -> str | None:
    """Why a digital signal's labels from this recording are capped at HYPOTHESIS, if they are:
    lossy audio distorts the phase the demodulator reads, and one real channel has no quadrature
    to tell a signal from its mirror image."""
    if isinstance(source, AudioRecording) and source.lossy:
        return "Lossy audio distorts the phase that digital demodulation relies on"
    fmt = source.sample_format
    if fmt is not None and not fmt.is_complex:
        return "A real-valued recording has no quadrature, so a signal and its mirror image agree"
    return None


def rate_note(assumptions: Assumptions) -> str | None:
    """Why values in hertz, baud or seconds are no firmer than the sample rate they rest on, when
    that rate is a HYPOTHESIS (a structural match): None when the file or the analyst stated it."""
    if assumptions.sample_rate.level is not EvidenceLevel.HYPOTHESIS:
        return None
    return (
        "Rests on the sample rate, which is a HYPOTHESIS from a structural match "
        "(see Assumptions); the normalised values do not depend on it"
    )


def analyse_detection(
    source: AnyRecording,
    detection: Detection,
    *,
    sample_rate: float | None,
    swap_iq: bool = False,
    rate_basis: str | None = None,
) -> DetectionReport:
    """The decode chain over one detection; a chain that raises becomes a failed report, so one
    bad signal never sinks the recording. On a recording that can't carry digital labels
    reliably (`label_cap_reason`), a digital signal's unproven labels are capped at HYPOTHESIS;
    `rate_basis` (from `rate_note`) is added to every value that rests on an inferred rate."""
    try:
        with source.reader(swap_iq=swap_iq) as reader:
            report = analyse(reader, detection, sample_rate=sample_rate)
        reason = label_cap_reason(source)
        report = cap_digital_labels(report, reason) if reason else report
        return note_rate_basis(report, rate_basis) if rate_basis else report
    except Exception as exc:
        return failed_analysis(detection, str(exc))


def signal_of(index: int, report: DetectionReport) -> Signal:
    """A report's conclusions as a results `Signal`, ids matching the API's (`signal_0`, ...):
    the stages, the headline with its level, the ledger and the frames, as the report has them."""
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
    return Signal(
        id=f"signal_{index}",
        label=report.label,
        kind=report.kind,
        level=report.level,
        headline=report.headline,
        stages=stages,
        search=report.search,
        no_search_reason=report.no_search_reason,
        frames=report.frames,
        no_frames_reason=report.no_frames_reason,
    )


def analyse_recording(
    source: AnyRecording,
    container: str,
    entries: Entries = (),
    *,
    real: bool,
    files: Iterable[Path] = (),
    on_detection: Callable[[int, int], None] | None = None,
) -> tuple[Results, Sequence[DetectionReport]]:
    """Detect and analyse every signal in a recording; the results document and the reports.

    Without a sample rate the bands are found but not analysed, as in the server: a box in
    seconds and hertz needs one, and the results say so. `on_detection(done, total)` is called
    after each one. `files` are the paths the recording was opened from, hashed into the
    document's identity (with the dataset a SigMF file names)."""
    swap_iq = dict(entries).get("iq_order") == "QI"
    with source.reader(swap_iq=swap_iq) as reader:
        samples = reader.num_samples
        detections = detect(reader, real=real).detections
    with source.reader(swap_iq=swap_iq) as reader:
        quality = capture_quality(reader)
    inferred = (
        None
        if dict(entries).get("sample_rate")
        else infer_sample_rate(source, detections, swap_iq=swap_iq)
    )
    assumptions = assumptions_with(source.assumptions, entries, inferred)
    sample_rate = numeric_rate(assumptions)
    reports: list[DetectionReport] = []
    if sample_rate is not None:
        for i, d in enumerate(detections):
            reports.append(
                analyse_detection(
                    source,
                    d,
                    sample_rate=sample_rate,
                    swap_iq=swap_iq,
                    rate_basis=rate_note(assumptions),
                )
            )
            if on_detection:
                on_detection(i + 1, len(detections))
    identity = recording_identity(container, samples, files, source)
    results = results_of(assumptions, identity, len(detections), reports, quality)
    return results, reports


def results_of(
    assumptions: Assumptions,
    identity: RecordingIdentity,
    detections: int,
    reports: Sequence[DetectionReport],
    quality: Sequence[Parameter] = (),
) -> Results:
    """The results document for a recording whose `detections` bands have `reports`, in order.
    With no reports the bands were found and not analysed (the sample rate is UNKNOWN), and the
    detect stage says so. `quality` (`dsp.quality.capture_quality`) becomes the capture stage."""
    ingest = StageResult(
        id="ingest",
        name="Ingest",
        status="done",
        summary=f"{identity.container}: {identity.samples:,} samples",
    )
    capture = (
        (
            StageResult(
                id="capture",
                name="Capture quality",
                status="done",
                summary=_quality_summary(quality),
                parameters=tuple(quality),
                warnings=tuple(w for p in quality for w in p.warnings),
            ),
        )
        if quality
        else ()
    )
    if not reports and numeric_rate(assumptions) is None:
        detect_stage = StageResult(
            id="detect",
            name="Detect",
            status="done",
            summary=f"{detections} band(s) found, not analysed: the sample rate is UNKNOWN",
        )
        return Results(
            sanket_version=version("sanket-backend"),
            recording=identity,
            catalogues=catalogue_versions(),
            assumptions=assumptions,
            stages=(ingest, *capture, detect_stage),
        )
    detect_stage = StageResult(
        id="detect", name="Detect", status="done", summary=f"{detections} signal(s) found"
    )
    return Results(
        sanket_version=version("sanket-backend"),
        recording=identity,
        catalogues=catalogue_versions(),
        assumptions=assumptions,
        stages=(ingest, *capture, detect_stage),
        signals=tuple(signal_of(i, r) for i, r in enumerate(reports)),
    )


def _quality_summary(quality: Sequence[Parameter]) -> str:
    """One line for the capture stage: what was found wrong, or that nothing was."""
    flagged = [p.name for p in quality if p.warnings]
    return "Flagged: " + ", ".join(flagged) if flagged else "No capture fault found"
