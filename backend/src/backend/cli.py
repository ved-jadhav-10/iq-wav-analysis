import argparse
import ipaddress
import math
import os
import sys
from pathlib import Path

import uvicorn

from backend.analysis import Entries, analyse_recording
from backend.app import create_app, default_workspace
from backend.inputs import FormatUnknownError, Input, RecordingError, expand, open_input
from dsp.frame_table import FORMATS, render
from dsp.report_pdf import render_pdf
from dsp.results_table import render_csv
from dsp.summary import render_summary

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
    commands = parser.add_subparsers(dest="command", metavar="{analyse}")
    analyse = commands.add_parser(
        "analyse",
        help="analyse recordings without the UI, one results JSON each",
        description="Analyse recordings and write each one's results JSON (the same document "
        "the UI exports). A folder is a batch of its files.",
    )
    analyse.add_argument("paths", nargs="+", type=Path, help="recording files or folders")
    analyse.add_argument(
        "--out", type=Path, default=Path("."), help="folder for the results (default: here)"
    )
    analyse.add_argument(
        "--sequence",
        action="store_true",
        help="read numbered files (rec_000.cu8, rec_001.cu8, ...) as one recording each",
    )
    analyse.add_argument(
        "--sample-rate", type=_rate, help="S/s the file doesn't state (e.g. 2.4M); entered, checked"
    )
    analyse.add_argument("--center-frequency", type=_rate, help="Hz the file doesn't state")
    analyse.add_argument(
        "--csv",
        action="store_true",
        help="also write each recording's values as a CSV table, one row per value",
    )
    analyse.add_argument(
        "--pdf",
        action="store_true",
        help="also write each recording's report as a PDF (summary, values, ledger, frames)",
    )
    analyse.add_argument(
        "--summary",
        action="store_true",
        help="also write each recording's plain-language summary as text",
    )
    analyse.add_argument(
        "--frames",
        choices=FORMATS,
        action="append",
        default=[],
        help="also write each signal's frame table in this format (repeatable)",
    )
    analyse.add_argument(
        "--datatype",
        help="sample format of a raw file the sniffer can't tell (cu8, ci16_le, cf32_le, ...)",
    )
    analyse.add_argument(
        "--iq-order",
        choices=("IQ", "QI"),
        help="QI swaps the two components (mirrors the spectrum)",
    )
    args = parser.parse_args(argv)
    if args.command == "analyse":
        return _analyse(args)

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


def _rate(text: str) -> float:
    """A number with an optional k, M or G suffix: 2.4M, 250k, 48000."""
    scale = {"k": 1e3, "M": 1e6, "G": 1e9}.get(text[-1:], 1.0)
    try:
        value = float(text[:-1] if scale != 1.0 else text) * scale
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a number like 2.4M or 250000") from None
    if not math.isfinite(value):
        raise argparse.ArgumentTypeError(f"{text!r} is not finite")
    return value


def _analyse(args: argparse.Namespace) -> int:
    entries: Entries = tuple(
        (name, value)
        for name, value in (
            ("sample_rate", args.sample_rate),
            ("center_frequency", args.center_frequency),
            ("iq_order", args.iq_order),
        )
        if value is not None
    )
    failed = False
    items: list[Input] = []
    for path in args.paths:
        try:
            items.extend(expand(path, sequence=args.sequence))
        except RecordingError as exc:
            print(f"sanket: {exc}", file=sys.stderr)
            failed = True
    args.out.mkdir(parents=True, exist_ok=True)
    written: set[Path] = set()
    for item in items:
        try:
            _analyse_one(
                item,
                entries,
                args.out,
                written,
                args.datatype,
                args.frames,
                args.csv,
                args.summary,
                args.pdf,
            )
        except FormatUnknownError as exc:
            print(f"sanket: {exc}: {', '.join(exc.candidates)} (pass --datatype)", file=sys.stderr)
            failed = True
        except RecordingError as exc:
            print(f"sanket: {item.name}: {exc}", file=sys.stderr)
            failed = True
    return 1 if failed else 0


def _analyse_one(
    item: Input,
    entries: Entries,
    out: Path,
    written: set[Path],
    datatype: str | None,
    frame_formats: list[str],
    csv_table: bool = False,
    summary: bool = False,
    pdf: bool = False,
) -> None:
    opened = open_input(item, datatype)
    fmt = opened.recording.sample_format
    assert fmt is not None  # open_input raised for an UNKNOWN format
    if not fmt.is_complex and any(name == "iq_order" for name, _ in entries):
        raise RecordingError("IQ order applies to complex samples; this recording is real")
    results, reports = analyse_recording(
        opened.recording,
        opened.container,
        entries,
        real=not fmt.is_complex,
        files=item.paths,
    )
    target = _unused(out / f"{item.paths[0].stem}.results.json", written)
    _write(target, results.to_json())
    if csv_table:
        _write(target.with_name(target.name.removesuffix(".json") + ".csv"), render_csv(results))
    if summary:
        _write(
            target.with_name(target.name.removesuffix(".results.json") + ".summary.txt"),
            render_summary(results),
        )
    if pdf:
        name = target.name.removesuffix(".results.json") + ".report.pdf"
        target.with_name(name).write_bytes(render_pdf(results))
    print(f"{item.name}: {len(reports)} signal(s) -> {target}")
    for i, report in enumerate(reports):
        print(f"  signal_{i}: {report.level.value} {report.headline}")
        for fmt in dict.fromkeys(frame_formats):  # each once, in the order given
            ext = fmt if fmt in ("json", "csv") else f"{fmt}.txt"
            name = target.name.removesuffix(".results.json")
            _write(
                out / f"{name}.signal_{i}.frames.{ext}",
                render(report.frames, fmt),  # type: ignore[arg-type]
            )
    if results.assumptions.sample_rate.value is None:
        print("  the sample rate is UNKNOWN; pass --sample-rate to analyse the bands")


def _write(path: Path, text: str) -> None:
    """Text as UTF-8 bytes exactly as given: `write_text` turns every newline into CRLF on
    Windows, which would make a file's bytes (and so its SHA-256) differ from the document the
    exports cite by hash."""
    path.write_bytes(text.encode("utf-8"))


def _unused(target: Path, written: set[Path]) -> Path:
    """`target`, or the first `name-2.results.json` not already written by this run."""
    base = target.name.removesuffix(".results.json")
    candidate, n = target, 1
    while candidate in written:
        n += 1
        candidate = target.with_name(f"{base}-{n}.results.json")
    written.add(candidate)
    return candidate
