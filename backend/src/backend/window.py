"""The desktop window: Sanket's own UI in a native window over the local server.

pywebview (BSD-3) is optional and imported only here, only when a window is asked for. Windows
uses Edge WebView2 (preinstalled on Windows 11 and on current Windows 10; the runtime is never
bundled), Linux GTK/WebKit2GTK. Never the Qt back end, which is GPL, and never the legacy
MSHTML renderer pywebview would silently fall back to: the back end is forced, so a missing
runtime is an error we report and answer with the browser.
"""

import importlib
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from backend.appdata import user_data_dir

TITLE = "Sanket"
SIZE = (1440, 900)
MIN_SIZE = (1024, 640)
# pywebview's names for the renderers we allow, by platform; anything else is left to it.
GUI = {"win32": "edgechromium", "linux": "gtk"}


def fit_size(screen: tuple[int, int] | None) -> tuple[int, int]:
    """The window's size for a screen of `screen` (width, height) in the units the GUI lays windows
    out in: the default size, shrunk to leave room for the taskbar and the title bar (a 900 px
    window does not fit a 960 px laptop screen with its taskbar, and its status bar ends up hidden),
    never below the minimum. No screen known: the default."""
    if screen is None:
        return SIZE
    width = max(MIN_SIZE[0], min(SIZE[0], int(screen[0] * 0.94)))
    height = max(MIN_SIZE[1], min(SIZE[1], int(screen[1] * 0.84)))
    return width, height


def _primary_screen(webview: Any) -> tuple[int, int] | None:
    try:
        primary = webview.screens[0]
        return int(primary.width), int(primary.height)
    except Exception:  # no screens API, or none reported: use the default size
        return None


class WindowUnavailable(Exception):
    """No window could be made (no pywebview, no web runtime); the message says why."""


def is_local(url: str) -> bool:
    """Only the loopback server may be shown in the window."""
    parts = urlsplit(url)
    return parts.scheme == "http" and parts.hostname == "127.0.0.1"


def run(url: str, storage: Path | None = None, busy: Callable[[], bool] | None = None) -> None:
    """Show `url` in a native window and return when the window is closed.

    `busy` says an analysis is still running: closing the window then asks first, and a "no"
    keeps it open. Blocks, and must be called from the main thread (the GUI loop's rule). Raises
    `WindowUnavailable` when there is no window to show; the caller then falls back to a browser.
    """
    if not is_local(url):
        raise WindowUnavailable(f"the window only shows the local server, not {url}")
    try:
        webview: Any = importlib.import_module("webview")
    except ImportError:
        raise WindowUnavailable("pywebview is not installed (uv sync --extra window)") from None
    try:
        width, height = fit_size(_primary_screen(webview))
        window = webview.create_window(
            TITLE, url, width=width, height=height, min_size=MIN_SIZE, text_select=True
        )
        # The page may link out; whatever the window ends up on that isn't ours is sent back.
        window.events.loaded += lambda: _keep_local(window, url)
        if busy is not None:
            window.events.closing += lambda: _confirm_close(window, busy)
        webview.start(
            gui=GUI.get(sys.platform),
            private_mode=False,  # the UI remembers its layout in local storage
            storage_path=str(storage or user_data_dir() / "window"),
        )
    except Exception as exc:  # the GUI libraries raise their own types; all mean "no window"
        raise WindowUnavailable(f"the window could not start ({exc})") from exc


def _confirm_close(window: Any, busy: Callable[[], bool]) -> bool:
    """The window's closing handler: False keeps it open. Only asks while an analysis runs."""
    if not busy():
        return True
    return bool(
        window.create_confirmation_dialog(
            TITLE,
            "An analysis is still running. Closing now stops it and loses its results."
            " Close anyway?",
        )
    )


def _keep_local(window: Any, home: str) -> None:
    current = window.get_current_url()
    if current and not is_local(current):
        window.load_url(home)
