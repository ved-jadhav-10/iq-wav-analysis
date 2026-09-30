"""The background analysis job's state (PLAN §5 M7)."""

import threading

import pytest

from backend.jobs import AnalysisJob, run_analysis
from dsp.evidence import EvidenceLevel
from dsp.report import DetectionReport, StageReport


def report(label: str = "Signal") -> DetectionReport:
    return DetectionReport(
        label=label,
        kind="unknown",
        level=EvidenceLevel.ESTIMATED,
        headline="h",
        stages=(StageReport(id="detect", name="Detect", status="done", summary="s"),),
        search=None,
        no_search_reason="r",
        no_frames_reason="r",
    )


def test_a_job_is_done_only_when_every_detection_has_a_report() -> None:
    job = AnalysisJob(2)
    assert (job.state, job.done, job.total) == ("running", 0, 2)
    job.record(0, report())
    assert (job.state, job.done) == ("running", 1)
    job.record(1, report())
    assert (job.state, job.done) == ("done", 2)


def test_a_job_with_nothing_to_do_is_done() -> None:
    assert AnalysisJob(0).state == "done"


def test_a_cancelled_job_with_reports_missing_is_cancelled_not_done() -> None:
    job = AnalysisJob(2)
    job.record(0, report())
    job.cancel()
    assert job.state == "cancelled"
    assert job.done == 1


def test_cancelling_stops_the_run_after_the_detection_in_flight() -> None:
    job = AnalysisJob(3)
    seen: list[int] = []

    def analyse_one(index: int) -> DetectionReport:
        seen.append(index)
        if index == 0:
            job.cancel()
        return report()

    run_analysis(job, job.total, analyse_one)
    assert seen == [0]
    assert job.state == "cancelled"


def test_a_listener_wakes_when_a_report_lands_and_times_out_when_none_does() -> None:
    job = AnalysisJob(1)
    assert job.wait_for_change(0, timeout=0.05) == 0  # nothing happened
    woke: list[int] = []
    waiter = threading.Thread(target=lambda: woke.append(job.wait_for_change(0, timeout=5)))
    waiter.start()
    job.record(0, report())
    waiter.join(timeout=5)
    assert woke == [1]


@pytest.mark.parametrize("total", [1, 4])
def test_reports_keep_their_detection_order(total: int) -> None:
    job = AnalysisJob(total)
    run_analysis(job, total, lambda i: report(f"S{i}"))
    assert [r.label for r in job.snapshot() if r] == [f"S{i}" for i in range(total)]
