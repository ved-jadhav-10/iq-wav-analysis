"""Where Sanket keeps per-user files that aren't recordings: the Numba cache, the window's
storage. Never next to the program, which may be on a read-only disk. Imports nothing heavy:
the frozen launcher uses it before Numba is imported."""

import os
import sys
from pathlib import Path


def user_data_dir() -> Path:
    """The per-user application data folder for Sanket (created on demand by its users)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "Sanket"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Sanket"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "sanket"


def numba_cache_dir() -> Path:
    return user_data_dir() / "numba-cache"
