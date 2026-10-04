import datetime
import json
import logging
import re
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager
from importlib.metadata import version
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field
from starlette.types import Scope

from dsp.detect import Detection, detection_parameters
from dsp.evidence import CamelModel, Parameter
from dsp.frame_table import MEDIA_TYPES, ExportFormat, render
from dsp.ingest.raw import RawRecording
from dsp.report import DetectionReport
from dsp.report_pdf import render_pdf
from dsp.results import Assumptions, Results
from dsp.results_table import render_csv
from dsp.sigmf_out import render_meta
from dsp.summary import render_summary

from . import samples
from .history import History
from .inputs import FormatUnknownError, RecordingError, expand
from .recordings import Recording, RecordingStore, results_for
from .runrecord import Phase, run_record
from .sigmf_export import NotDescribable, annotated_meta, save_beside
from .uploads import DEFAULT_MAX_UPLOAD_BYTES, UploadError, UploadStore

API_PREFIX = "/api/v1"


class _Frontend(StaticFiles):
    """The built UI. Its assets are named by content hash, but `index.html` is not: without a
    cache header the desktop window (whose cache outlives the process) can keep showing an old
    page after a rebuild. `no-cache` still lets it reuse the file when the ETag matches."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code in (200, 304) and Path(path).parts[:1] != ("assets",):
            response.headers["Cache-Control"] = "no-cache"
        return response


class SampleInfo(CamelModel):
    id: str
    title: str
    description: str
    synthetic: bool = True
    signals: int
    size_bytes: int


class OpenRecordingRequest(CamelModel):
    path: str
    sequence: bool = Field(
        default=False,
        description="Read the numbered files beside `path` (rec_000.cu8, rec_001.cu8, ...) as "
        "one recording.",
    )
    datatype: str | None = Field(
        default=None,
        description="The sample format of a raw file, when the sniffer can't tell: a SigMF "
        "datatype such as cu8 or cf32_le. Recorded as entered by the analyst.",
    )


class InputInfo(CamelModel):
    """One recording a path names: open it with `path` and `sequence`."""

    path: str = Field(
        description="The file to open; the first of the files when there are several."
    )
    name: str
    files: int = Field(ge=1)
    sequence: bool = Field(description="Several numbered files read as one recording.")


class InputsRequest(CamelModel):
    path: str
    sequence: bool = False


class UploadedFile(CamelModel):
    """Where an uploaded file landed; open a recording with this `path`."""

    path: str
    size: int


class AssumptionsRequest(CamelModel):
    """Values the analyst enters for what the file leaves UNKNOWN (or gets wrong). Each is
    recorded as MEASURED "entered by the analyst", replaces the file's own value, and restarts
    the analysis."""

    sample_rate: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    center_frequency: float | None = Field(default=None, allow_inf_nan=False)
    iq_order: Literal["IQ", "QI"] | None = Field(
        default=None,
        description="QI swaps the two components, which mirrors the spectrum: pick it when a "
        "known carrier sits on the wrong side. The samples can't tell the two apart.",
    )


class LevelInfo(CamelModel):
    level: int
    rows: int
    cols: int
    row_span: int


class Box(CamelModel):
    """A time/frequency rectangle in seconds and hertz (delta-f from capture centre), matching
    the frontend's `View`/waterfall coordinates."""

    t0: float
    t1: float
    f0: float
    f1: float


class DetectionInfo(CamelModel):
    """One detected signal's box, `detect`'s own evidence, and the full per-detection analysis
    (PLAN M3-M6): estimate, sync, classify, demod, FEC and framing, as far as the chain
    gets for this signal."""

    id: str
    box: Box
    parameters: tuple[Parameter, ...]
    # None while the background job hasn't reached this signal yet (`AnalysisProgress`).
    analysis: DetectionReport | None


class AnalysisProgress(CamelModel):
    """How far the background analysis has got: `done` of `total` detections have a report.
    `cancelled` is a job that was replaced (a new assumption restarted it) or stopped; its
    missing reports will not arrive."""

    state: Literal["running", "done", "cancelled"]
    done: int
    total: int


class HistoryEntry(CamelModel):
    id: str
    created_utc: str
    name: str
    container: str
    signals: int
    verified: int  # signals whose headline is VERIFIED
    results_sha256: str


class SavedSigmf(CamelModel):
    path: str  # where the metadata file was written, beside the raw file


class RecordingInfo(CamelModel):
    id: str
    container: str
    name: str
    num_samples: int
    real: bool
    recorder: str | None  # SigMF core:recorder, as the file states it
    synthetic: bool  # the file states it was generated by dsp.synth
    fft_size: int
    # Input samples per level-0 row: the FFT hop times the frames a row averages (the grid
    # folds several frames into a row to bound its cells), so a row maps to its true duration.
    hop: float
    sample_rate: float | None  # None when the Assumptions block leaves it UNKNOWN
    db_min: float
    db_max: float
    freqs_hz: tuple[float, ...] | None  # None alongside sample_rate: Hz needs a known rate
    # The same axis as fractions of the sample rate: always present, so a recording whose rate
    # is UNKNOWN can still be drawn, in normalised units.
    freqs_norm: tuple[float, ...]
    psd_db: tuple[float, ...]
    levels: tuple[LevelInfo, ...]
    assumptions: Assumptions
    # What the samples say about the capture (`dsp.quality`): clipping, DC offset, I/Q imbalance
    # (complex recordings), gaps; one UNKNOWN when the file is empty.
    capture_quality: tuple[Parameter, ...]
    analysis: AnalysisProgress
    # What SigMF output the recording supports: "save" a raw file (annotations, and a metadata
    # file written beside it), "annotate" a SigMF recording (annotations only), else "none".
    sigmf: Literal["annotate", "save", "none"]
    # Empty alongside sample_rate: a box in seconds/Hz needs a known rate, same as freqs_hz.
    detections: tuple[DetectionInfo, ...]


def _phases_of(rec: Recording) -> list[Phase]:
    """How the run went: the phases of opening, then each finished signal's analysis."""
    return [
        *rec.survey_phases,
        *(Phase(name=f"signal_{i}", seconds=round(s, 3)) for i, s in rec.job.timings()),
    ]


def _sigmf_support(rec: Recording) -> Literal["annotate", "save", "none"]:
    """What `sigmf_export` can do with this recording: the same two tests it applies."""
    if any(p.name.lower().endswith(".sigmf-meta") for p in rec.files):
        return "annotate"
    return "save" if isinstance(rec.source, RawRecording) else "none"


def _progress(rec: Recording) -> AnalysisProgress:
    job = rec.job
    return AnalysisProgress(state=job.state, done=job.done, total=job.total)


# A comment line sent when nothing changed, so a dead connection surfaces as a failed write.
SSE_KEEPALIVE_S = 10.0


def _progress_events(rec: Recording) -> Iterator[str]:
    """Server-sent events: one `progress` event now, one per finished detection, and the stream
    ends after a `done` or `cancelled` one."""
    version = -1
    while True:
        latest = rec.job.wait_for_change(version, SSE_KEEPALIVE_S)
        if latest == version:
            yield ": keepalive\n\n"
            continue
        version = latest
        progress = _progress(rec)
        yield f"event: progress\ndata: {json.dumps(progress.model_dump(by_alias=True))}\n\n"
        if progress.state != "running":
            return


def default_workspace() -> Path:
    """Where uploads live unless told otherwise (`sanket --workspace`, SANKET_WORKSPACE)."""
    return Path.home() / ".sanket" / "workspace"


def create_app(
    frontend_dist: Path,
    workspace: Path | None = None,
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
) -> FastAPI:
    # Kept analyses persist in the workspace when one is named; otherwise they live in memory.
    history = History(workspace / "history.sqlite3" if workspace else None)

    def keep(recording: Recording) -> None:
        """Keep a finished analysis. A failure here must never stop the analysis worker."""
        try:
            results = results_for(recording)
            run = run_record(results, results.sanket_version, _phases_of(recording))
            now = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            history.save(recording.name, results, run.to_json(), now)
        except Exception:  # the worker must survive a failed save
            logging.getLogger("sanket").exception("could not keep the finished analysis")

    store = RecordingStore(on_done=keep)
    uploads = UploadStore(workspace or default_workspace(), max_upload_bytes)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        store.close()
        history.close()

    # Swagger UI and ReDoc load their assets from a CDN, which the offline rule forbids.
    app = FastAPI(
        title="Sanket",
        version=version("sanket-backend"),
        docs_url=None,
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
        lifespan=lifespan,
    )

    @app.get(f"{API_PREFIX}/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": app.version}

    def _detection_info(
        d: Detection, analysis: DetectionReport | None, index: int, sample_rate: float
    ) -> DetectionInfo:
        box = Box(
            t0=d.start / sample_rate,
            t1=d.stop / sample_rate,
            f0=d.low * sample_rate,
            f1=d.high * sample_rate,
        )
        return DetectionInfo(
            id=f"signal_{index}",
            box=box,
            parameters=detection_parameters(d),
            analysis=analysis,
        )

    def _to_info(rec: Recording) -> RecordingInfo:
        rate = rec.assumptions.sample_rate.value
        sample_rate = rate if isinstance(rate, int | float) else None
        detections = (
            tuple(
                _detection_info(d, a, i, sample_rate)
                for i, (d, a) in enumerate(zip(rec.detections, rec.analyses, strict=True))
            )
            if sample_rate
            else ()
        )
        return RecordingInfo(
            id=rec.id,
            container=rec.container,
            name=rec.name,
            num_samples=rec.num_samples,
            real=rec.real,
            recorder=rec.recorder,
            synthetic=rec.synthetic,
            fft_size=rec.pyramid.grid.nfft,
            hop=rec.pyramid.grid.hop * rec.pyramid.grid.frames / rec.pyramid.grid.rows,
            sample_rate=sample_rate,
            db_min=rec.pyramid.db_min,
            db_max=rec.pyramid.db_max,
            freqs_hz=tuple(f * sample_rate for f in rec.pyramid.freqs) if sample_rate else None,
            freqs_norm=tuple(rec.pyramid.freqs),
            psd_db=tuple(rec.pyramid.psd_db),
            levels=tuple(
                LevelInfo(level=i, rows=lv.rows, cols=lv.cols, row_span=lv.row_span)
                for i, lv in enumerate(rec.pyramid.levels)
            ),
            assumptions=rec.assumptions,
            capture_quality=rec.quality,
            analysis=_progress(rec),
            sigmf=_sigmf_support(rec),
            detections=detections,
        )

    @app.put(f"{API_PREFIX}/uploads/{{batch}}/{{name}}", response_model=UploadedFile)
    async def upload_file(batch: str, name: str, request: Request) -> UploadedFile:
        declared = request.headers.get("content-length")
        try:
            path = await uploads.save(
                batch,
                name,
                request.stream(),
                int(declared) if declared and declared.isdigit() else None,
            )
        except UploadError as exc:
            raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
        return UploadedFile(path=str(path), size=path.stat().st_size)

    @app.post(f"{API_PREFIX}/inputs", response_model=tuple[InputInfo, ...])
    def list_inputs(body: InputsRequest) -> tuple[InputInfo, ...]:
        """The recordings a path names: itself, or a folder's files. Reads no samples."""
        try:
            items = expand(Path(body.path), sequence=body.sequence)
        except RecordingError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return tuple(
            InputInfo(
                path=str(item.paths[0]),
                name=item.name,
                files=len(item.paths),
                sequence=len(item.paths) > 1,
            )
            for item in items
        )

    @app.post(f"{API_PREFIX}/recordings", response_model=RecordingInfo | None)
    def open_recording(body: OpenRecordingRequest) -> RecordingInfo | JSONResponse:
        try:
            recording = store.open(Path(body.path), sequence=body.sequence, datatype=body.datatype)
        except FormatUnknownError as exc:
            # The analyst can settle it: the candidates ride along for the UI to offer.
            return JSONResponse(
                status_code=422,
                content={"detail": str(exc), "formatCandidates": list(exc.candidates)},
            )
        except RecordingError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _to_info(recording)

    @app.get(f"{API_PREFIX}/samples", response_model=tuple[SampleInfo, ...])
    def list_sample_recordings() -> tuple[SampleInfo, ...]:
        """The bundled synthetic sample recordings, for a first-time visitor to try."""
        return tuple(
            SampleInfo(
                id=s.id,
                title=s.title,
                description=s.description,
                signals=s.signals,
                size_bytes=s.size_bytes,
            )
            for s in samples.list_samples()
        )

    @app.post(f"{API_PREFIX}/samples/{{sample_id}}/open", response_model=RecordingInfo | None)
    def open_sample(sample_id: str) -> RecordingInfo:
        sample = samples.find(sample_id)
        if sample is None:
            raise HTTPException(status_code=404, detail="no such sample recording")
        try:
            recording = store.open(sample.path)
        except RecordingError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _to_info(recording)

    @app.get(f"{API_PREFIX}/recordings/{{recording_id}}", response_model=RecordingInfo)
    def get_recording(recording_id: str) -> RecordingInfo:
        recording = store.get(recording_id)
        if recording is None:
            raise HTTPException(status_code=404, detail="no such recording")
        return _to_info(recording)

    @app.put(f"{API_PREFIX}/recordings/{{recording_id}}/assumptions", response_model=RecordingInfo)
    def put_assumptions(recording_id: str, body: AssumptionsRequest) -> RecordingInfo:
        try:
            recording = store.assume(
                recording_id,
                sample_rate=body.sample_rate,
                center_frequency=body.center_frequency,
                iq_order=body.iq_order,
            )
        except RecordingError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if recording is None:
            raise HTTPException(status_code=404, detail="no such recording")
        return _to_info(recording)

    @app.get(f"{API_PREFIX}/recordings/{{recording_id}}/events")
    def recording_events(recording_id: str) -> StreamingResponse:
        recording = store.get(recording_id)
        if recording is None:
            raise HTTPException(status_code=404, detail="no such recording")
        return StreamingResponse(
            _progress_events(recording),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    def _finished_results(recording_id: str) -> tuple[Recording, Results]:
        """The recording and its results document, once the analysis has finished."""
        recording = store.get(recording_id)
        if recording is None:
            raise HTTPException(status_code=404, detail="no such recording")
        if any(report is None for report in recording.analyses):
            raise HTTPException(status_code=409, detail="the analysis has not finished")
        results = results_for(recording)
        return recording, results

    @app.get(f"{API_PREFIX}/recordings/{{recording_id}}/results")
    def get_results(
        recording_id: str, format: Literal["json", "csv", "txt", "pdf", "run", "sigmf"] = "json"
    ) -> Response:
        """The results document as a download: JSON is the schema-versioned document `sanket
        analyse` writes, CSV one row per reported value (`dsp.results_table`), text a
        plain-language summary (`dsp.summary`). Held back while
        the decode chain is still running, so a download is never a partial analysis."""
        recording, results = _finished_results(recording_id)
        stem = re.sub(r"[^A-Za-z0-9._-]+", "_", recording.path.stem) or "recording"
        return _download(
            format,
            results,
            stem,
            run=lambda: run_record(
                results, results.sanket_version, _phases_of(recording)
            ).to_json(),
            sigmf=lambda: render_meta(annotated_meta(results, recording.files, recording.source)),
        )

    def _download(
        format: str,
        results: Results,
        stem: str,
        *,
        run: Callable[[], str | None],
        sigmf: Callable[[], str] | None = None,
    ) -> Response:
        """One rendering of a results document as a download; shared by a live recording and a
        kept analysis, so both give the same bytes."""

        def need(make: Callable[[], str] | None) -> Callable[[], str | bytes]:
            def call() -> str | bytes:
                if make is None:
                    raise NotDescribable("this export is not kept with a finished analysis")
                return make()

            return call

        def run_or_refuse() -> str:
            text = run()
            if text is None:
                raise NotDescribable("no run record was kept for this analysis")
            return text

        content, media_type, name = {
            "json": (results.to_json, "application/json", f"{stem}.results.json"),
            "csv": (lambda: render_csv(results), "text/csv", f"{stem}.results.csv"),
            "txt": (lambda: render_summary(results), "text/plain", f"{stem}.summary.txt"),
            "pdf": (lambda: render_pdf(results), "application/pdf", f"{stem}.report.pdf"),
            "sigmf": (need(sigmf), "application/json", f"{stem}.sanket.sigmf-meta"),
            "run": (run_or_refuse, "application/json", f"{stem}.run.json"),
        }[format]
        try:
            body = content()
        except NotDescribable as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return Response(
            content=body,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    @app.get(f"{API_PREFIX}/history", response_model=list[HistoryEntry])
    def list_history() -> list[HistoryEntry]:
        """Finished analyses kept in the workspace, newest first."""
        return [
            HistoryEntry(
                id=e.id,
                created_utc=e.created_utc,
                name=e.name,
                container=e.container,
                signals=e.signals,
                verified=e.verified,
                results_sha256=e.results_sha256,
            )
            for e in history.entries()
        ]

    @app.get(f"{API_PREFIX}/history/{{entry_id}}/results")
    def get_history_results(
        entry_id: str, format: Literal["json", "csv", "txt", "pdf", "run"] = "json"
    ) -> Response:
        """A kept analysis as a download, in the formats a finished one has (not SigMF, which
        needs the recording's files); the JSON is the document as it was first produced."""
        kept = history.get(entry_id)
        if kept is None:
            raise HTTPException(status_code=404, detail="no such analysis")
        entry, results, run_json = kept
        stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(entry.name).stem) or "recording"
        return _download(format, results, stem, run=lambda: run_json)

    @app.delete(f"{API_PREFIX}/history/{{entry_id}}", status_code=204)
    def delete_history(entry_id: str) -> Response:
        """Delete a kept analysis and everything derived from it."""
        if not history.delete(entry_id):
            raise HTTPException(status_code=404, detail="no such analysis")
        return Response(status_code=204)

    @app.post(f"{API_PREFIX}/recordings/{{recording_id}}/sigmf", response_model=SavedSigmf)
    def save_as_sigmf(recording_id: str) -> SavedSigmf:
        """Save as SigMF: for a raw file, write `<name>.sigmf-meta` beside it, naming it as the
        dataset (the samples are not copied). The analyst asks for this on a recording whose
        sample format they have confirmed; what the results can't stand behind (a rate that is
        only a hypothesis) stays out of the standard fields (`dsp.sigmf_out`)."""
        recording, results = _finished_results(recording_id)
        try:
            saved = save_beside(results, recording.source)
        except NotDescribable as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RecordingError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return SavedSigmf(path=str(saved))

    @app.get(f"{API_PREFIX}/recordings/{{recording_id}}/detections/{{index}}/frames")
    def get_frames(recording_id: str, index: int, format: ExportFormat = "json") -> Response:
        """The signal's frame table as a download: JSON and CSV carry every frame with its CRC
        outcome, hex and bits only the frames that passed (`dsp.frame_table`)."""
        recording = store.get(recording_id)
        if recording is None:
            raise HTTPException(status_code=404, detail="no such recording")
        if not 0 <= index < len(recording.detections):
            raise HTTPException(status_code=404, detail="no such signal")
        report = recording.analyses[index]
        if report is None:
            raise HTTPException(status_code=409, detail="the analysis has not reached this signal")
        stem = re.sub(r"[^A-Za-z0-9._-]+", "_", recording.path.stem) or "recording"
        ext = format if format in ("json", "csv") else f"{format}.txt"
        return Response(
            content=render(report.frames, format),
            media_type=MEDIA_TYPES[format],
            headers={
                "Content-Disposition": f'attachment; filename="{stem}.signal_{index}.frames.{ext}"'
            },
        )

    @app.get(f"{API_PREFIX}/tiles/{{recording_id}}/{{level}}/{{row}}/{{col}}")
    def get_tile(recording_id: str, level: int, row: int, col: int) -> Response:
        recording = store.get(recording_id)
        if recording is None:
            raise HTTPException(status_code=404, detail="no such recording")
        if not 0 <= level < len(recording.pyramid.levels):
            raise HTTPException(status_code=404, detail="no such level")
        tile = recording.pyramid.tile(level, row, col)
        return Response(
            content=tile.tobytes(),
            media_type="application/octet-stream",
            headers={"X-Tile-Rows": str(tile.shape[0]), "X-Tile-Cols": str(tile.shape[1])},
        )

    # Mounted last so every API route above takes precedence over the SPA files.
    app.mount("/", _Frontend(directory=frontend_dist, html=True), name="frontend")
    app.state.busy = store.busy  # the desktop window asks before closing on a running analysis
    return app
