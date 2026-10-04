from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>Sanket</title>")
    (dist / "assets" / "app.js").write_text("console.log('ok')")
    (tmp_path / "secret.txt").write_text("outside dist")
    return dist


@pytest.fixture
def client(dist: Path) -> TestClient:
    return TestClient(create_app(dist))


def test_health_reports_version(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_serves_spa_and_assets(client: TestClient) -> None:
    assert "<title>Sanket</title>" in client.get("/").text
    assert client.get("/assets/app.js").text == "console.log('ok')"


def test_page_is_revalidated_but_hashed_assets_are_not(client: TestClient) -> None:
    """A rebuilt UI must reach a window whose cache outlives the process."""
    assert client.get("/").headers["cache-control"] == "no-cache"
    assert client.get("/index.html").headers["cache-control"] == "no-cache"
    assert "cache-control" not in client.get("/assets/app.js").headers


def test_openapi_schema_is_versioned(client: TestClient) -> None:
    assert client.get("/api/v1/openapi.json").json()["info"]["title"] == "Sanket"


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_no_cdn_backed_doc_pages(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404


def test_unknown_api_route_is_404_not_spa(client: TestClient) -> None:
    assert client.get("/api/v1/nope").status_code == 404


def test_path_traversal_outside_dist_is_refused(client: TestClient) -> None:
    response = client.get("/..%2Fsecret.txt")
    assert response.status_code == 404
    assert "outside dist" not in response.text
