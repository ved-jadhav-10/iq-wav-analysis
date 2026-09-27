from importlib.metadata import version
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

API_PREFIX = "/api/v1"


def create_app(frontend_dist: Path) -> FastAPI:
    # Swagger UI and ReDoc load their assets from a CDN, which the offline rule forbids.
    app = FastAPI(
        title="Sanket",
        version=version("sanket-backend"),
        docs_url=None,
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
    )

    @app.get(f"{API_PREFIX}/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": app.version}

    # Mounted last so every API route above takes precedence over the SPA files.
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    return app
