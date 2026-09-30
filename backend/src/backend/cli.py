import argparse
import ipaddress
import os
import sys
from pathlib import Path

import uvicorn

from backend.app import create_app, default_workspace

REPO_ROOT = Path(__file__).resolve().parents[3]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sanket", description="Blind signal analysis, with evidence."
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="interface to bind (default: loopback only)"
    )
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="where uploaded recordings are kept (default: ~/.sanket/workspace, "
        "or SANKET_WORKSPACE)",
    )
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

    workspace = args.workspace or Path(os.environ.get("SANKET_WORKSPACE") or default_workspace())

    print(f"Sanket running at http://{args.host}:{args.port}", flush=True)
    uvicorn.run(create_app(dist, workspace), host=args.host, port=args.port)
    return 0


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
