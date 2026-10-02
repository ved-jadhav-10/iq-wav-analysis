import argparse
import ipaddress
import math
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

import uvicorn

from backend import warm, window
from backend.analysis import Entries, analyse_recording
from backend.app import create_app, default_workspace
from backend.appdata import user_data_dir
from backend.inputs import FormatUnknownError, Input, RecordingError, expand, open_input
from backend.runrecord import PhaseTimer, run_record
from backend.sigmf_export import NotDescribable, annotated_meta, save_beside
from dsp.frame_table import FORMATS, render
from dsp.report_pdf import render_pdf
from dsp.results_table import render_csv
from dsp.sigmf_out import render_meta
from dsp.summary import render_summary

REPO_ROOT = Path(__file__).resolve().parents[3]


def _utf8_console() -> None:
    """Headlines carry symbols (an arrow, a middle dot) that a Windows console's code page can't
    encode: say them as UTF-8, replacing what the console can't show, rather than crash."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    _utf8_console()
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
    shown = parser.add_mutually_exclusive_group()
    shown.add_argument(
        "--browser",
        action="store_true",
        help="open the system browser instead of Sanket's own window",
    )
    shown.add_argument(
        "--no-open",
        action="store_true",
        help="only serve: open neither a window nor a browser (also SANKET_NO_OPEN or CI set)",
    )
    parser.add_argument(
        "--no-warm",
        action="store_true",
        help="don't compile the Numba kernels in the background at start-up",
    )
    commands = parser.add_subparsers(dest="command", metavar="{analyse,warm}")
    commands.add_parser(
        "warm",
        help="compile and cache the Numba kernels now, then exit (an installer can run this)",
        description="Compile the Numba kernels on tiny inputs and write the per-user cache, so "
        "that the first recording opened doesn't wait for it.",
    )
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
        "--sigmf",
        action="store_true",
        help="also write each recording's findings as SigMF annotations (<name>.sanket.sigmf-meta)",
    )
    analyse.add_argument(
        "--save-sigmf",
        action="store_true",
        help="for a raw file, write <name>.sigmf-meta beside it, naming it as the dataset",
    )
    analyse.add_argument(
        "--no-run-record",
        action="store_true",
        help="don't write the run record (timings, peak memory, machine class) beside the results",
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
    if args.command == "warm":
        print(f"Numba kernels ready in {warm.warm():.1f} s", flush=True)
        return 0

    dist = _frontend_dist()
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
    app = create_app(dist, workspace)
    if not (args.no_warm or os.environ.get("SANKET_NO_WARM")):
        warm.start()

    print(f"Sanket running at http://{args.host}:{args.port}", flush=True)
    if args.no_open or os.environ.get("SANKET_NO_OPEN") or os.environ.get("CI"):
        uvicorn.run(app, host=args.host, port=args.port)
        return 0
    return _serve_and_show(app, args.host, args.port, browser=args.browser)


def _frontend_dist() -> Path:
    """The built UI: SANKET_FRONTEND_DIST, else the copy bundled in a frozen build, else the
    repo's `frontend/dist`."""
    if override := os.environ.get("SANKET_FRONTEND_DIST"):
        return Path(override)
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "frontend" / "dist"
    return REPO_ROOT / "frontend" / "dist"


def _serve_and_show(app: Any, host: str, port: int, *, browser: bool) -> int:
    """Serve on a thread and show the UI: in Sanket's own window, or the system browser. Closing
    the window stops the server; with a browser the server runs until interrupted."""
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port))  # type: ignore[arg-type]
    thread = threading.Thread(target=server.run, name="sanket-server", daemon=True)
    thread.start()
    while not server.started and thread.is_alive():
        time.sleep(0.02)
    if not server.started:
        return 1  # uvicorn has said why (a port in use)
    # A wildcard bind is reached through loopback; the window shows only 127.0.0.1.
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '', 'localhost') else host}:{port}"
    try:
        if not browser:
            try:
                window.run(url, user_data_dir() / "window", busy=getattr(app.state, "busy", None))
                return 0
            except window.WindowUnavailable as exc:
                print(f"sanket: no desktop window: {exc}; opening {url} in the browser instead")
        if not webbrowser.open(url):
            print(f"sanket: could not open a browser; browse to {url}", file=sys.stderr)
        while thread.is_alive():
            thread.join(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.should_exit = True
        thread.join(5)
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
                not args.no_run_record,
                args.sigmf,
                args.save_sigmf,
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
    run_record_file: bool = True,
    sigmf: bool = False,
    save_sigmf: bool = False,
) -> None:
    opened = open_input(item, datatype)
    fmt = opened.recording.sample_format
    assert fmt is not None  # open_input raised for an UNKNOWN format
    if not fmt.is_complex and any(name == "iq_order" for name, _ in entries):
        raise RecordingError("IQ order applies to complex samples; this recording is real")
    timer = PhaseTimer()
    results, reports = analyse_recording(
        opened.recording,
        opened.container,
        entries,
        real=not fmt.is_complex,
        files=item.paths,
        timer=timer,
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
    if run_record_file:
        name = target.name.removesuffix(".results.json") + ".run.json"
        record = run_record(results, results.sanket_version, timer.phases)
        _write(target.with_name(name), record.to_json())
    if sigmf:
        name = target.name.removesuffix(".results.json") + ".sanket.sigmf-meta"
        try:
            meta = annotated_meta(results, item.paths, opened.recording)
            _write(target.with_name(name), render_meta(meta))
        except NotDescribable as exc:
            print(f"  no SigMF annotations: {exc}", file=sys.stderr)
    if save_sigmf:
        saved = save_beside(results, opened.recording)
        print(f"  SigMF description written: {saved}")
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
