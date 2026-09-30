"""Per-recording analysis as a background job (PLAN §5 M7, "Background analysis").

Opening a recording returns once its tiles and detections exist; running the decode chain over
each detection then happens here, one detection at a time, on a worker thread. The job holds the
finished reports and a version counter that any number of listeners (the SSE route) can wait on.

This is the in-memory half of PLAN §3's job runner: threads rather than a process pool, no
SQLite, nothing surviving a restart. Those arrive with the workspace; the contract the API and
the frontend see (a done/total count, a report per detection that appears when it is ready) does
not change when they do.
"""

from collections.abc import Callable
from threading import Condition, Event
from typing import Literal

from dsp.report import DetectionReport


class AnalysisJob:
    """The reports for one recording's detections, filled in as they finish."""

    def __init__(self, total: int) -> None:
        self._cond = Condition()
        self._reports: list[DetectionReport | None] = [None] * total
        self._version = 0
        self.cancelled = Event()

    @property
    def total(self) -> int:
        return len(self._reports)

    def record(self, index: int, report: DetectionReport) -> None:
        with self._cond:
            self._reports[index] = report
            self._version += 1
            self._cond.notify_all()

    def cancel(self) -> None:
        """Stop after the detection in flight and wake every listener."""
        self.cancelled.set()
        with self._cond:
            self._version += 1
            self._cond.notify_all()

    def snapshot(self) -> tuple[DetectionReport | None, ...]:
        with self._cond:
            return tuple(self._reports)

    @property
    def done(self) -> int:
        with self._cond:
            return sum(r is not None for r in self._reports)

    @property
    def state(self) -> Literal["running", "done", "cancelled"]:
        """`done` only when every detection has a report; `cancelled` when the job was stopped
        (a new assumption replaced it, or the server is closing) with reports still missing."""
        if self.done == self.total:
            return "done"
        return "cancelled" if self.cancelled.is_set() else "running"

    def wait_for_change(self, after: int, timeout: float) -> int:
        """Block until the version moves past `after`, or `timeout` seconds pass; return the
        current version either way (equal to `after` means the wait timed out)."""
        with self._cond:
            self._cond.wait_for(lambda: self._version > after, timeout=timeout)
            return self._version


def run_analysis(
    job: AnalysisJob,
    count: int,
    analyse_one: Callable[[int], DetectionReport],
) -> None:
    """Analyse detections 0..count-1 in order, recording each report as it is ready. A detection
    whose analysis raises must be turned into a failed report by `analyse_one`, so one bad
    signal never stops the ones after it."""
    for index in range(count):
        if job.cancelled.is_set():
            return
        job.record(index, analyse_one(index))
