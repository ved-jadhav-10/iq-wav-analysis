from pathlib import Path
from typing import Any

import pytest

from backend import cli


@pytest.fixture
def dist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "index.html").write_text("<!doctype html>")
    monkeypatch.setenv("SANKET_FRONTEND_DIST", str(tmp_path))
    return tmp_path


@pytest.fixture
def served(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    calls: dict[str, Any] = {}
    monkeypatch.setattr(cli.uvicorn, "run", lambda app, **kw: calls.update(kw))
    return calls


def test_binds_loopback_by_default(dist: Path, served: dict[str, Any]) -> None:
    assert cli.main([]) == 0
    assert served == {"host": "127.0.0.1", "port": 8765}


def test_warns_when_binding_beyond_loopback(
    dist: Path, served: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["--host", "0.0.0.0"]) == 0
    assert "exposes Sanket beyond this machine" in capsys.readouterr().err


def test_missing_frontend_build_fails_with_instructions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    served: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("SANKET_FRONTEND_DIST", str(tmp_path / "missing"))
    assert cli.main([]) == 1
    assert "npm run build" in capsys.readouterr().err
    assert served == {}
