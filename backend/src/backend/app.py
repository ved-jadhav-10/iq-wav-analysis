from importlib.metadata import version
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles

from dsp.detect import Detection, detection_parameters
from dsp.evidence import CamelModel, Parameter
from dsp.results import Assumptions

from .recordings import Recording, RecordingError, RecordingStore

API_PREFIX = "/api/v1"


class OpenRecordingRequest(CamelModel):
    path: str


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
    """One detected signal's box and its own evidence (PLAN §5 M2). Only `detect`'s findings
    exist yet - estimate, sync, classify and the rest are still M3+ (PLAN §5)."""

    id: str
    box: Box
    parameters: tuple[Parameter, ...]


class RecordingInfo(CamelModel):
    id: str
    container: str
    name: str
    num_samples: int
    real: bool
    fft_size: int
    hop: int
    sample_rate: float | None  # None when the Assumptions block leaves it UNKNOWN
    db_min: float
    db_max: float
    freqs_hz: tuple[float, ...] | None  # None alongside sample_rate: Hz needs a known rate
    psd_db: tuple[float, ...]
    levels: tuple[LevelInfo, ...]
    assumptions: Assumptions
    # Empty alongside sample_rate: a box in seconds/Hz needs a known rate, same as freqs_hz.
    detections: tuple[DetectionInfo, ...]


def create_app(frontend_dist: Path) -> FastAPI:
    # Swagger UI and ReDoc load their assets from a CDN, which the offline rule forbids.
    app = FastAPI(
        title="Sanket",
        version=version("sanket-backend"),
        docs_url=None,
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    store = RecordingStore()

    @app.get(f"{API_PREFIX}/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": app.version}

    def _detection_info(d: Detection, index: int, sample_rate: float) -> DetectionInfo:
        box = Box(
            t0=d.start / sample_rate,
            t1=d.stop / sample_rate,
            f0=d.low * sample_rate,
            f1=d.high * sample_rate,
        )
        return DetectionInfo(id=f"signal_{index}", box=box, parameters=detection_parameters(d))

    def _to_info(rec: Recording) -> RecordingInfo:
        rate = rec.assumptions.sample_rate.value
        sample_rate = rate if isinstance(rate, int | float) else None
        detections = (
            tuple(_detection_info(d, i, sample_rate) for i, d in enumerate(rec.detections))
            if sample_rate
            else ()
        )
        return RecordingInfo(
            id=rec.id,
            container=rec.container,
            name=rec.name,
            num_samples=rec.num_samples,
            real=rec.real,
            fft_size=rec.pyramid.grid.nfft,
            hop=rec.pyramid.grid.hop,
            sample_rate=sample_rate,
            db_min=rec.pyramid.db_min,
            db_max=rec.pyramid.db_max,
            freqs_hz=tuple(f * sample_rate for f in rec.pyramid.freqs) if sample_rate else None,
            psd_db=tuple(rec.pyramid.psd_db),
            levels=tuple(
                LevelInfo(level=i, rows=lv.rows, cols=lv.cols, row_span=lv.row_span)
                for i, lv in enumerate(rec.pyramid.levels)
            ),
            assumptions=rec.assumptions,
            detections=detections,
        )

    @app.post(f"{API_PREFIX}/recordings", response_model=RecordingInfo)
    def open_recording(body: OpenRecordingRequest) -> RecordingInfo:
        try:
            recording = store.open(Path(body.path))
        except RecordingError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _to_info(recording)

    @app.get(f"{API_PREFIX}/recordings/{{recording_id}}", response_model=RecordingInfo)
    def get_recording(recording_id: str) -> RecordingInfo:
        recording = store.get(recording_id)
        if recording is None:
            raise HTTPException(status_code=404, detail="no such recording")
        return _to_info(recording)

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
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    return app
