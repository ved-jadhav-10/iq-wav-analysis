import argparse
import ipaddress
import os
import sys
from pathlib import Path

import uvicorn

from backend.app import create_app

REPO_ROOT = Path(__file__).resolve().parents[3]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sanket", description="Blind signal analysis, with evidence."
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="interface to bind (default: loopback only)"
    )
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)

    dist = Path(os.environ.get("SANKET_FRONTEND_DIST", REPO_ROOT / "frontend" / "dist"))
    if not (dist / "index.html").is_file():
        print(
            f"sanket: no built frontend at {dist}; run `npm run build` in frontend/",
            file=sys.stderr,
        )
        return 1

    if not _is_loopback(args.host):
        print(
            f"sanket: warning: binding {args.host} exposes Sanket beyond this machine",
            file=sys.stderr,
        )

    print(f"Sanket running at http://{args.host}:{args.port}", flush=True)
    uvicorn.run(create_app(dist), host=args.host, port=args.port)
    return 0


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
