"""Smoke-test the frozen one-folder build (`dist/sanket/`): start it with networking to loopback
only, check that it serves the bundled UI, opens a recording, decodes it to VERIFIED and writes
the same results the source tree does.

Run after `uv run python tools/build.py` and `uv run python tools/make_demo.py`:
    uv run python tools/smoke_frozen.py [recording]      (default data/demo/scene_fsk.sigmf-meta)

Exits non-zero, with the reason, on the first thing that doesn't hold. A cold Numba cache is
used on purpose (a temporary workspace and home), so the first-analysis time is what a new
user sees.
"""

import contextlib
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "dist" / "sanket" / ("sanket.exe" if sys.platform == "win32" else "sanket")
START_TIMEOUT = 90.0
ANALYSIS_TIMEOUT = 600.0


def fail(message: str) -> int:
    print(f"smoke: FAIL: {message}", file=sys.stderr)
    return 1


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def get(url: str, *, data: bytes | None = None) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url, data=data, headers={"content-type": "application/json"} if data else {}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def main() -> int:
    recording = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "data/demo/scene_fsk.sigmf-meta")
    if not EXE.is_file():
        return fail(f"{EXE} not built (uv run python tools/build.py)")
    if not recording.is_file():
        return fail(f"{recording} missing (uv run python tools/make_demo.py)")

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory() as scratch:
        env = {
            **os.environ,
            "SANKET_WORKSPACE": str(Path(scratch) / "workspace"),
            "SANKET_NO_OPEN": "1",
            "LOCALAPPDATA": scratch,  # a cold per-user Numba cache (Windows)
            "XDG_CACHE_HOME": scratch,  # (Linux)
        }
        env.pop("NUMBA_CACHE_DIR", None)
        log = Path(scratch) / "server.log"
        with log.open("wb") as out:
            server = subprocess.Popen(
                [str(EXE), "--port", str(port), "--no-warm"], env=env, stdout=out, stderr=out
            )
            try:
                return _check(server, base, recording, log)
            finally:
                server.terminate()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    server.wait(10)
                server.kill()


def _check(server: subprocess.Popen[bytes], base: str, recording: Path, log: Path) -> int:
    began = time.monotonic()
    while True:
        if server.poll() is not None:
            return fail(f"the server exited ({server.returncode}):\n{log.read_text('utf-8')}")
        try:
            if get(f"{base}/api/v1/health")[0] == 200:
                break
        except OSError:
            pass
        if time.monotonic() - began > START_TIMEOUT:
            return fail(f"no answer within {START_TIMEOUT:.0f} s:\n{log.read_text('utf-8')}")
        time.sleep(0.3)
    print(f"smoke: server up in {time.monotonic() - began:.1f} s")

    status, page = get(f"{base}/")
    if status != 200 or b'<div id="root"' not in page:
        return fail(f"the bundled UI isn't served (HTTP {status})")

    status, body = get(
        f"{base}/api/v1/recordings", data=json.dumps({"path": str(recording)}).encode()
    )
    if status != 200:
        return fail(f"open returned HTTP {status}: {body.decode(errors='replace')}")
    rec_id = json.loads(body)["id"]

    began = time.monotonic()
    while True:
        status, results = get(f"{base}/api/v1/recordings/{rec_id}/results?format=json")
        if status == 200:
            break
        if status != 409:
            return fail(f"results returned HTTP {status}: {results.decode(errors='replace')}")
        if server.poll() is not None:
            return fail("the server died during the analysis")
        if time.monotonic() - began > ANALYSIS_TIMEOUT:
            return fail(f"the analysis didn't finish in {ANALYSIS_TIMEOUT:.0f} s")
        time.sleep(1)
    print(f"smoke: analysed in {time.monotonic() - began:.1f} s (cold Numba cache)")

    document = json.loads(results)
    verified = [s for s in document["signals"] if s.get("level") == "VERIFIED"]
    if not verified:
        return fail("no signal reached VERIFIED")
    print(
        f"smoke: {len(verified)} VERIFIED signal(s); results {hashlib.sha256(results).hexdigest()}"
    )
    print("smoke: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
