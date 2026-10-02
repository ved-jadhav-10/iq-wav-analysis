"""Entry point of the frozen `sanket.exe`: sets up the per-user Numba cache, then runs the CLI.

The cache location has to be in the environment before Numba is first imported (the first
`import dsp...` does that), so it is set here and nowhere later. The program folder may be on a
read-only disk, so the cache never goes beside it.
"""

import multiprocessing
import os
import sys


def main() -> int:
    multiprocessing.freeze_support()
    if getattr(sys, "frozen", False):
        # The cache folder is per user; Numba reads both variables when it is first imported
        # (the first `import dsp...`), so they are set here and nowhere later.
        from backend.appdata import numba_cache_dir

        if "NUMBA_CACHE_DIR" not in os.environ:
            cache = numba_cache_dir()
            cache.mkdir(parents=True, exist_ok=True)
            os.environ["NUMBA_CACHE_DIR"] = str(cache)
        os.environ.setdefault("NUMBA_CACHE_LOCATOR_CLASSES", "backend.numba_cache.FrozenLocator")
    from backend.cli import main as run

    return run()


if __name__ == "__main__":
    sys.exit(main())
