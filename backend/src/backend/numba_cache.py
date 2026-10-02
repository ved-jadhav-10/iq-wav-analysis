"""A Numba cache locator for the frozen program.

In a PyInstaller build a function's source file is a relative name inside the bundle
(`dsp\framing.py`) that exists nowhere on disk, so Numba's own locators skip
`NUMBA_CACHE_DIR` (they need the file to exist) and fall back to a folder named after the
current directory. This one writes to `NUMBA_CACHE_DIR` whatever the file, in a subfolder that
doesn't depend on where the program was started from. Numba already stamps a frozen function's
cache with the executable's own size and time, so a new build never reads an old build's cache.

The launcher selects it with `NUMBA_CACHE_LOCATOR_CLASSES=backend.numba_cache.FrozenLocator`
before Numba is imported; nothing else uses it.
"""

import hashlib
import os
from typing import Any

from numba.core import config  # pyright: ignore[reportMissingTypeStubs]
from numba.core.caching import UserProvidedCacheLocator  # pyright: ignore[reportMissingTypeStubs]

LOCATOR = "backend.numba_cache.FrozenLocator"


class FrozenLocator(UserProvidedCacheLocator):  # pyright: ignore[reportUntypedBaseClass]
    @classmethod
    def from_function(cls, py_func: Any, py_file: str) -> "FrozenLocator | None":
        if not getattr(config, "CACHE_DIR", ""):
            return None
        self = cls(py_func, py_file)
        try:
            self.ensure_cache_path()
        except OSError:  # not writable: let Numba try its other locators
            return None
        return self

    @classmethod
    def get_suitable_cache_subpath(cls, py_file: str) -> str:
        path = os.path.normpath(py_file)  # never abspath: that would be the current directory
        folder = os.path.basename(os.path.dirname(path))
        return f"{folder}_{hashlib.sha1(path.encode()).hexdigest()}"
