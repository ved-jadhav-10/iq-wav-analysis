"""Build the one-folder desktop program: the frontend, then PyInstaller on packaging/sanket.spec.

Run: uv run python tools/build.py [--skip-frontend]   ->   dist/sanket/sanket.exe
The sample recordings (data/demo) are made first when missing.

PyInstaller is a dev-only tool (GPL-2.0 with the bootloader exception, which lets the programs
it builds carry any licence); the product never imports it. The window needs pywebview, so
build from an environment that has it: `uv sync --extra window`.
"""

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "sanket"


def folder_size(folder: Path) -> int:
    return sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-frontend", action="store_true", help="reuse frontend/dist as it is")
    args = parser.parse_args()

    began = time.perf_counter()
    if not (ROOT / "data" / "demo" / "scene.sigmf-meta").is_file():
        subprocess.run([sys.executable, str(ROOT / "tools" / "make_demo.py")], cwd=ROOT, check=True)
    if not args.skip_frontend:
        npm = shutil.which("npm")
        if npm is None:
            print("build: npm not found; install Node or pass --skip-frontend", file=sys.stderr)
            return 1
        subprocess.run([npm, "run", "build"], cwd=ROOT / "frontend", check=True)
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(ROOT / "packaging" / "sanket.spec"),
        "--noconfirm",
        "--clean",
        "--distpath",
        str(ROOT / "dist"),
        "--workpath",
        str(ROOT / "build" / "pyinstaller"),
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    exe = OUT / ("sanket.exe" if sys.platform == "win32" else "sanket")
    if not exe.is_file():
        print(f"build: {exe} was not produced", file=sys.stderr)
        return 1
    print(
        f"built {exe} in {time.perf_counter() - began:.0f} s; "
        f"folder {folder_size(OUT) / 2**20:.0f} MiB"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
