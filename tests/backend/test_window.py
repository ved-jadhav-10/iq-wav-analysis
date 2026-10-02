"""The desktop window and how the CLI chooses between it, the browser and server-only, with a
fake `webview` module: no real window is ever created."""

import sys
import time
import types
from pathlib import Path
from typing import Any

import pytest

from backend import cli, window


class FakeEvents:
    def __init__(self) -> None:
        self.handlers: list[Any] = []

    def __iadd__(self, handler: Any) -> "FakeEvents":
        self.handlers.append(handler)
        return self


class FakeWindow:
    def __init__(self, url: str) -> None:
        self.url = url
        self.loaded_urls: list[str] = []
        self.events = types.SimpleNamespace(loaded=FakeEvents(), closing=FakeEvents())
        self.asked: list[str] = []
        self.answer = True

    def create_confirmation_dialog(self, title: str, message: str) -> bool:
        self.asked.append(message)
        return self.answer

    def get_current_url(self) -> str:
        return self.url

    def load_url(self, url: str) -> None:
        self.url = url
        self.loaded_urls.append(url)


def fake_webview(
    monkeypatch: pytest.MonkeyPatch, *, fail: Exception | None = None, drift: str | None = None
) -> dict[str, Any]:
    """Installs a `webview` module; `drift` is a page the window ends up on after loading."""
    seen: dict[str, Any] = {}

    def create_window(title: str, url: str, **kw: Any) -> FakeWindow:
        seen["window"] = FakeWindow(url)
        seen["create"] = (title, url, kw)
        return seen["window"]

    def start(**kw: Any) -> None:
        if fail:
            raise fail
        seen["start"] = kw
        win: FakeWindow = seen["window"]
        if drift:
            win.url = drift
        for handler in win.events.loaded.handlers:
            handler()

    module = types.ModuleType("webview")
    module.create_window = create_window  # type: ignore[attr-defined]
    module.start = start  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "webview", module)
    return seen


def test_only_the_loopback_server_is_local() -> None:
    assert window.is_local("http://127.0.0.1:8765/")
    for url in ("http://localhost:8765", "https://127.0.0.1:1", "http://example.com", "file:///x"):
        assert not window.is_local(url)


def test_the_window_shows_the_server_with_a_forced_renderer_and_stored_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen = fake_webview(monkeypatch)
    window.run("http://127.0.0.1:9000", tmp_path)
    assert seen["create"][:2] == ("Sanket", "http://127.0.0.1:9000")
    assert seen["start"]["private_mode"] is False
    assert seen["start"]["storage_path"] == str(tmp_path)
    assert seen["start"]["gui"] in (None, "edgechromium", "gtk")  # never qt, never mshtml
    assert seen["window"].loaded_urls == []


def test_a_page_that_is_not_ours_is_sent_back(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = fake_webview(monkeypatch, drift="https://example.com/")
    window.run("http://127.0.0.1:9000")
    assert seen["window"].loaded_urls == ["http://127.0.0.1:9000"]


def test_closing_asks_only_while_an_analysis_runs_and_a_no_keeps_the_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = fake_webview(monkeypatch)
    running = {"now": False}
    window.run("http://127.0.0.1:9000", busy=lambda: running["now"])
    win: FakeWindow = seen["window"]
    (closing,) = win.events.closing.handlers
    assert closing() is True and win.asked == []  # idle: closes without a question
    running["now"] = True
    win.answer = False
    assert closing() is False and len(win.asked) == 1  # busy and "no": stays open
    win.answer = True
    assert closing() is True  # busy and "yes": closes


def test_without_a_busy_check_the_window_never_intercepts_closing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = fake_webview(monkeypatch)
    window.run("http://127.0.0.1:9000")
    assert seen["window"].events.closing.handlers == []


def test_a_remote_url_is_refused_without_creating_a_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = fake_webview(monkeypatch)
    with pytest.raises(window.WindowUnavailable, match="local server"):
        window.run("http://example.com")
    assert "create" not in seen


def test_no_pywebview_is_unavailable_not_a_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "webview", None)  # an import of it raises ImportError
    with pytest.raises(window.WindowUnavailable, match="not installed"):
        window.run("http://127.0.0.1:9000")


def test_a_missing_web_runtime_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_webview(monkeypatch, fail=RuntimeError("WebView2 runtime not found"))
    with pytest.raises(window.WindowUnavailable, match="WebView2"):
        window.run("http://127.0.0.1:9000")


# -- how `sanket` chooses -------------------------------------------------------------------------


class FakeServer:
    """Stands in for uvicorn.Server: up at once, runs until told to exit."""

    def __init__(self, config: Any) -> None:
        self.config = config
        self.started = False
        self.should_exit = False

    def run(self) -> None:
        self.started = True
        while not self.should_exit:
            time.sleep(0.005)


@pytest.fixture
def shown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    (tmp_path / "index.html").write_text("<!doctype html>")
    monkeypatch.setenv("SANKET_FRONTEND_DIST", str(tmp_path))
    monkeypatch.delenv("SANKET_NO_OPEN", raising=False)
    monkeypatch.delenv("CI", raising=False)
    calls: dict[str, Any] = {"browser": [], "servers": []}

    def make_server(config: Any) -> FakeServer:
        calls["servers"].append(FakeServer(config))
        return calls["servers"][-1]

    def open_browser(url: str) -> bool:
        calls["browser"].append(url)
        calls["servers"][0].should_exit = True  # the stand-in for the user pressing Ctrl+C
        return True

    monkeypatch.setattr(cli.uvicorn, "Server", make_server)
    monkeypatch.setattr(cli.uvicorn, "run", lambda *a, **kw: calls.update(served_only=True))
    monkeypatch.setattr(cli.warm, "start", lambda: None)
    monkeypatch.setattr(cli.webbrowser, "open", open_browser)
    return calls


def test_by_default_a_window_opens_and_closing_it_stops_the_server(
    shown: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[str] = []
    asked: list[Any] = []

    def show(url: str, storage: Path | None = None, busy: Any = None) -> None:
        opened.append(url)
        asked.append(busy)

    monkeypatch.setattr(cli.window, "run", show)
    assert cli.main(["--port", "9001"]) == 0
    assert opened == ["http://127.0.0.1:9001"]
    assert callable(asked[0]) and asked[0]() is False  # the store's own check: nothing running
    assert shown["browser"] == [] and "served_only" not in shown
    (server,) = shown["servers"]
    assert server.should_exit  # closing the window stopped it


def test_a_window_that_cannot_open_falls_back_to_the_browser_with_one_line(
    shown: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def refuse(url: str, storage: Path | None = None, busy: Any = None) -> None:
        raise window.WindowUnavailable("pywebview is not installed (uv sync --extra window)")

    monkeypatch.setattr(cli.window, "run", refuse)
    assert cli.main(["--port", "9002"]) == 0
    lines = [ln for ln in capsys.readouterr().out.splitlines() if "no desktop window" in ln]
    assert len(lines) == 1 and "not installed" in lines[0] and "http://127.0.0.1:9002" in lines[0]
    assert shown["browser"] == ["http://127.0.0.1:9002"]


def test_browser_flag_opens_the_browser_and_never_tries_the_window(
    shown: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("the window was requested")

    monkeypatch.setattr(cli.window, "run", forbidden)
    assert cli.main(["--browser", "--port", "9003"]) == 0
    assert shown["browser"] == ["http://127.0.0.1:9003"]


@pytest.mark.parametrize("how", ["flag", "SANKET_NO_OPEN", "CI"])
def test_server_only_opens_nothing(
    shown: dict[str, Any], monkeypatch: pytest.MonkeyPatch, how: str
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("something was opened")

    monkeypatch.setattr(cli.window, "run", forbidden)
    monkeypatch.setattr(cli.webbrowser, "open", forbidden)
    if how != "flag":
        monkeypatch.setenv(how, "1")
    assert cli.main(["--no-open"] if how == "flag" else []) == 0
    assert shown["served_only"] and shown["servers"] == []


def test_browser_and_no_open_are_exclusive() -> None:
    with pytest.raises(SystemExit):
        cli.main(["--browser", "--no-open"])


def test_the_window_is_shrunk_to_fit_the_screen_it_opens_on() -> None:
    # A 1536 x 960 laptop screen (125 % scaling, taskbar included) cannot hold 1440 x 900.
    assert window.fit_size((1536, 960)) == (1440, 806)
    assert window.fit_size((1920, 1080)) == (1440, 900)
    assert window.fit_size((3840, 2160)) == window.SIZE
    # Tiny or unknown screens never go below the minimum, and none known gives the default.
    assert window.fit_size((800, 600)) == window.MIN_SIZE
    assert window.fit_size(None) == window.SIZE


def test_the_window_asks_the_gui_for_the_fitted_size(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = fake_webview(monkeypatch)
    sys.modules["webview"].screens = [types.SimpleNamespace(width=1536, height=960)]  # type: ignore[attr-defined]
    window.run("http://127.0.0.1:8765")
    _title, _url, kw = seen["create"]
    assert (kw["width"], kw["height"]) == (1440, 806)
