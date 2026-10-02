"""The run record: how an analysis went, kept apart from what it found (PLAN §3, §6).

`results.json` holds only conclusions and is byte-identical across runs; this holds what varies
with the run: the wall-clock time of each phase, the process's peak memory, when it finished, and
the class of machine. It names the results by their SHA-256, so a record and a document pair up.
It never holds a host name, a user name or a path. Nothing here is analysed or shown as evidence;
it exists so a slow or failed analysis can be traced afterwards.
"""

import datetime
import os
import platform
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal

from pydantic import Field

from dsp.evidence import CamelModel
from dsp.results import Results, results_sha256

RUN_SCHEMA_VERSION = "0.1.0"


class Phase(CamelModel):
    name: str = Field(min_length=1)
    seconds: float = Field(ge=0.0)


class RunRecord(CamelModel):
    schema_version: Literal["0.1.0"] = RUN_SCHEMA_VERSION  # type: ignore[assignment]
    sanket_version: str
    results_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    finished_utc: str = Field(description="When the record was made, UTC, to the second.")
    phases: tuple[Phase, ...]
    total_seconds: float = Field(ge=0.0)
    peak_memory_bytes: int | None = Field(
        description="Peak resident memory of the process so far; null where the OS gives none."
    )
    python: str
    platform: str = Field(description="OS and release, from platform.platform(); no host name.")
    machine: str
    logical_cores: int | None

    def to_json(self) -> str:
        return self.model_dump_json(indent=2) + "\n"


class PhaseTimer:
    """Collects the wall-clock seconds of named phases, in the order they ran."""

    def __init__(self) -> None:
        self.phases: list[Phase] = []

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self.phases.append(Phase(name=name, seconds=round(time.perf_counter() - start, 3)))


def peak_memory_bytes() -> int | None:
    """The process's peak resident memory: `PeakWorkingSetSize` on Windows, `ru_maxrss` where
    the `resource` module exists (kibibytes on Linux, bytes on macOS)."""
    if sys.platform == "win32":
        return _peak_working_set()
    try:
        import resource
    except ImportError:
        return None
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


def _peak_working_set() -> int | None:  # pragma: no cover - Windows only
    import ctypes
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = Counters()
    counters.cb = ctypes.sizeof(Counters)
    windll = getattr(ctypes, "windll", None)
    if windll is None:
        return None
    process = windll.kernel32.GetCurrentProcess()
    ok = windll.psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb)
    return int(counters.PeakWorkingSetSize) if ok else None


def run_record(results: Results, sanket_version: str, phases: list[Phase]) -> RunRecord:
    """The record of a finished run that produced `results`."""
    now = datetime.datetime.now(datetime.UTC).replace(microsecond=0)
    return RunRecord(
        sanket_version=sanket_version,
        results_sha256=results_sha256(results),
        finished_utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        phases=tuple(phases),
        total_seconds=round(sum(p.seconds for p in phases), 3),
        peak_memory_bytes=peak_memory_bytes(),
        python=platform.python_version(),
        platform=platform.platform(),
        machine=platform.machine(),
        logical_cores=os.cpu_count(),
    )
