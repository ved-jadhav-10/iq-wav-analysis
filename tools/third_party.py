"""Generate THIRD_PARTY.md from the lockfiles and enforce the licence policy (PLAN §2).

Covers only what ships in the product: Python runtime dependencies (no dev group, no ml/)
and non-dev npm packages. Run `uv run python tools/third_party.py` to regenerate, or with
`--check` in CI to fail on a stale file or a disallowed or unrecognised licence.
"""

import argparse
import json
import re
import subprocess
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "THIRD_PARTY.md"

ALLOWED = re.compile(
    r"MIT|BSD|Apache|ISC|PSF|Python Software Foundation|Python-2\.0|OFL|MPL|LGPL|Unlicense|CC0"
    r"|0BSD|Zlib|BlueOak",
    re.IGNORECASE,
)
# GPL/AGPL (but not LGPL), non-commercial and source-available licences are banned.
DENIED = re.compile(r"(?<!L)GPL|\bNC\b|Non-?Commercial|SSPL|BUSL|Commons Clause", re.IGNORECASE)


# The one GPL form allowed: a runtime library under the GCC Runtime Library Exception, which
# exists so that compiled programs may ship it under any licence.
RUNTIME_EXCEPTION = re.compile(r"^GPL-3\.0(-or-later)? WITH GCC-exception-3\.1$")

# Native libraries compiled into Python wheels, which package metadata doesn't list; each is
# checked by the same policy. Sources: the licence files bundled in each wheel.
BUNDLED: dict[str, tuple[tuple[str, str], ...]] = {
    "numpy": (
        ("OpenBLAS", "BSD-3-Clause"),
        ("LAPACK", "BSD-3-Clause-Open-MPI"),
        ("GCC runtime library", "GPL-3.0-or-later WITH GCC-exception-3.1"),
    ),
    "scipy": (
        ("OpenBLAS", "BSD-3-Clause"),
        ("LAPACK", "BSD-3-Clause-Open-MPI"),
        ("GCC runtime library", "GPL-3.0-or-later WITH GCC-exception-3.1"),
        ("libquadmath (Linux wheels)", "LGPL-2.1-or-later"),
    ),
    # ReportLab imports Pillow unconditionally; the libraries its wheels bundle (the Windows,
    # Linux and macOS wheels together; none holds libimagequant, the one GPL component in
    # Pillow's source SBOM).
    "pillow": (
        ("FreeType", "FreeType License (BSD-style, with attribution)"),
        ("HarfBuzz", "MIT"),
        ("libjpeg-turbo", "IJG; BSD-3-Clause"),
        ("libpng", "libpng License (BSD-style)"),
        ("libtiff", "libtiff License (BSD-style)"),
        ("libwebp", "BSD-3-Clause"),
        ("libavif", "BSD-2-Clause"),
        ("OpenJPEG", "BSD-2-Clause"),
        ("Little CMS 2", "MIT"),
        ("zlib-ng", "Zlib"),
        ("Brotli", "MIT"),
        ("xz (liblzma)", "0BSD"),
        ("Zstandard", "BSD-3-Clause"),
        ("libxcb and libXau", "MIT"),
    ),
    "soundfile": (
        ("libsndfile", "LGPL-2.1-or-later"),
        ("FLAC", "BSD-3-Clause"),
        ("Ogg Vorbis", "BSD-3-Clause"),
        ("Opus", "BSD-3-Clause"),
        ("mpg123", "LGPL-2.1"),
        ("LAME", "LGPL-2.0"),
    ),
}


def classify(licence: str) -> str:
    if not licence:
        return "unknown"
    if RUNTIME_EXCEPTION.match(licence):
        return "allowed"
    if DENIED.search(licence):
        return "denied"
    return "allowed" if ALLOWED.search(licence) else "unknown"


def python_packages() -> list[tuple[str, str, str]]:
    exported = subprocess.run(
        ["uv", "export", "--no-dev", "--no-hashes", "--no-emit-workspace", "--frozen"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    packages = []
    for line in exported.splitlines():
        match = re.match(r"^([A-Za-z0-9_.\-]+)==([^\s;]+)", line)
        if match:
            name, version = match.groups()
            packages.append((name, version, _python_licence(name)))
    return packages


def _python_licence(name: str) -> str:
    meta = metadata.metadata(name)
    if expression := meta.get("License-Expression"):
        return expression
    field = (meta.get("License") or "").strip()
    if field and "\n" not in field and len(field) <= 60:
        return field
    classifiers = [
        c.removeprefix("License :: OSI Approved :: ").removeprefix("License :: ")
        for c in meta.get_all("Classifier") or []
        if c.startswith("License ::")
    ]
    return "; ".join(classifiers)


def npm_packages() -> list[tuple[str, str, str]]:
    lock = json.loads((ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
    packages = []
    for path, entry in lock["packages"].items():
        if not path or entry.get("dev"):
            continue
        name = path.rsplit("node_modules/", 1)[-1]
        packages.append((name, entry["version"], entry.get("license", "")))
    return sorted(packages)


def bundled(python: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    """(library, the package that ships it, licence) for every bundled native library."""
    shipped = {name.lower() for name, _, _ in python}
    return [
        (library, package, licence)
        for package, libraries in sorted(BUNDLED.items())
        if package in shipped
        for library, licence in libraries
    ]


def render(
    python: list[tuple[str, str, str]],
    npm: list[tuple[str, str, str]],
    native: list[tuple[str, str, str]],
) -> str:
    lines = [
        "# Third-party software",
        "",
        "Generated by `tools/third_party.py` from `uv.lock` and `frontend/package-lock.json`;",
        "do not edit by hand. Lists only what ships in Sanket, not development tools.",
    ]
    for title, rows in (("Python", python), ("Frontend (npm)", npm)):
        lines += ["", f"## {title}", "", "| Package | Version | Licence |", "|---|---|---|"]
        lines += [f"| {name} | {version} | {licence} |" for name, version, licence in rows]
    lines += ["", "## Native libraries bundled in Python wheels", ""]
    lines += ["| Library | Shipped in | Licence |", "|---|---|---|"]
    lines += [f"| {library} | {package} | {licence} |" for library, package, licence in native]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if THIRD_PARTY.md is stale")
    args = parser.parse_args()

    python, npm = python_packages(), npm_packages()
    native = bundled(python)
    problems = [
        f"{name} {version}: {classify(licence)} licence {licence!r}"
        for name, version, licence in python + npm + native
        if classify(licence) != "allowed"
    ]
    for problem in problems:
        print(f"licence: {problem}", file=sys.stderr)

    content = render(python, npm, native)
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != content:
            print(
                "THIRD_PARTY.md is stale: run `uv run python tools/third_party.py`", file=sys.stderr
            )
            return 1
    else:
        OUTPUT.write_text(content, encoding="utf-8", newline="\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
