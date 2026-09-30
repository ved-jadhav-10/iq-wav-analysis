"""`bench`: generate the bench sets and score Sanket on them (PLAN §5 M1, bench v0).

    uv run bench generate dev|null|sealed [--limit N]   write SigMF files to bench/data/<set>/
    uv run bench run dev|null|sealed|torchsig           score them, write bench/results/

Every file follows from its seed (bench/presets.py), so only seeds and results are committed.
The sealed set's seeds live in bench/sealed/manifest.json and are never changed; its results
are written as totals only, never per file, so no one tunes against it. Run it only for a
release measurement, not during development.

Bench v0 scores ingest: whether SigMF ingest recovers the truth, whether the format sniffer,
reading each data file as a headerless raw file, proposes the right format or honestly ties, and
whether the true sample rate is among the rate candidates. The null set also runs the decode
chain (`dsp.analyse`) on every file, in parallel, and counts VERIFIED values and accepted
decodes: no null file carries a frame, so any accepted decode is a false accept.

The torchsig set comes from an independent generator (bench/torchsig/export.py, run under WSL2
with TorchSig); `bench run torchsig` scores it the same way against the labels in its manifest,
so the sniffer is measured on signals it was never tuned on.
"""

import argparse
import json
import os
import sys
import time
from collections import Counter
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from bench.presets import Draw, dev_draw, null_draw
from dsp.analyse import analyse
from dsp.detect import detect
from dsp.evidence import EvidenceLevel
from dsp.ingest.rate import rate_candidates
from dsp.ingest.sigmf import read_sigmf
from dsp.ingest.sniff import sniff
from dsp.synth.chain import GENERATOR_VERSION, generate, write_sigmf

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RESULTS = ROOT / "results"
SEALED = ROOT / "sealed" / "manifest.json"
BENCH_VERSION = "0.1.0"


@dataclass(frozen=True)
class BenchSet:
    name: str
    draw: Callable[[int], Draw]
    seeds: tuple[int, ...]
    totals_only: bool = False
    chain: bool = False  # also run the decode chain on every file


def sets() -> dict[str, BenchSet]:
    sealed = json.loads(SEALED.read_text(encoding="utf-8"))
    return {
        "dev": BenchSet("dev", dev_draw, tuple(range(200))),
        "null": BenchSet("null", null_draw, tuple(range(1000)), chain=True),
        "sealed": BenchSet("sealed", dev_draw, tuple(sealed["seeds"]), totals_only=True),
    }


def generate_set(bench: BenchSet, out: Path, limit: int | None = None) -> list[dict[str, Any]]:
    out.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    for seed in bench.seeds[:limit]:
        draw = bench.draw(seed)
        stem = out / f"{bench.name}-{seed}"
        write_sigmf(stem, generate(draw.scene, seed), draw.scene, draw.datatype)
        entries.append({"seed": seed, "file": stem.name, "datatype": draw.datatype})
    manifest = {"set": bench.name, "generator": GENERATOR_VERSION, "files": entries}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return entries


def score_file(meta_path: Path, bench: BenchSet, seed: int) -> dict[str, Any]:
    draw = bench.draw(seed)
    scene = draw.scene
    rec = read_sigmf(meta_path)
    a = rec.assumptions
    ingest_ok = (
        a.datatype.value == draw.datatype
        and a.datatype.level is EvidenceLevel.MEASURED
        and a.sample_rate.value == scene.sample_rate
        and a.center_frequency.value == scene.center_frequency
    )
    return {
        "seed": seed,
        "datatype": draw.datatype,
        "labels": draw.labels,
        "ingest": "ok" if ingest_ok else "mismatch",
        **score_raw(rec.data_path, draw.datatype, scene.sample_rate),
        "verified": sum(p.level is EvidenceLevel.VERIFIED for p in a.parameters()),
        "acceptedDecodes": 0,
    }


def score_chain(meta_path: Path) -> dict[str, Any]:
    """Detect and analyse every signal in one file with the decode chain. `acceptedDecodes` counts
    the detections whose hypothesis search accepted a chain (CRC passes significant after
    correction); `verifiedParameters` counts VERIFIED Parameters over every stage of every report,
    the same unit as the ingest half of `verified`; `blindSearched` and `blindIdentified` say how
    often the blind convolutional-code search ran and how often it named a code."""
    rec = read_sigmf(meta_path)
    fmt = rec.sample_format
    assert fmt is not None
    rate = rec.assumptions.sample_rate.value
    sample_rate = rate if isinstance(rate, int | float) else None
    started = time.perf_counter()
    with rec.reader() as reader:
        detections = detect(reader, real=not fmt.is_complex).detections
    accepted = verified = searched = identified = 0
    for d in detections:
        with rec.reader() as reader:
            report = analyse(reader, d, sample_rate=sample_rate)
        rows = report.search.rows if report.search else ()
        accepted += any(r.outcome == "accepted" for r in rows)
        verified += sum(
            p.level is EvidenceLevel.VERIFIED for stage in report.stages for p in stage.parameters
        )
        if report.search:
            searched += report.search.blind_searched
            identified += report.search.blind_identified
    return {
        "detections": len(detections),
        "acceptedDecodes": accepted,
        "verifiedParameters": verified,
        "blindSearched": searched,
        "blindIdentified": identified,
        "chainSeconds": round(time.perf_counter() - started, 2),
    }


def score_raw(data_path: Path, datatype: str, sample_rate: float | None) -> dict[str, Any]:
    """The sniffer's outcome on the data file read as headerless raw samples, and the rank of
    the true sample rate among the rate candidates."""
    param = sniff(data_path).datatype
    candidates = {alt.value for alt in param.alternatives}
    if param.value == datatype:
        sniffed = "correct, by convention" if param.convention else "correct"
    elif param.value is None:
        sniffed = "unknown, truth among candidates" if datatype in candidates else "unknown"
    elif param.convention and str(param.value)[1:] == datatype[1:]:
        sniffed = "layout by convention"
    else:
        sniffed = "wrong"
    rates = [c.value for c in rate_candidates(data_path.name, datatype)]
    rank = rates.index(sample_rate) + 1 if sample_rate in rates else None
    return {"sniffer": sniffed, "sniffed": param.value, "rateRank": rank}


def score_torchsig(meta_path: Path, entry: dict[str, Any], sample_rate: float) -> dict[str, Any]:
    """A TorchSig file: SigMF ingest must reproduce the stated datatype and rate, and leave the
    centre frequency, which TorchSig's baseband metadata doesn't state, UNKNOWN."""
    a = read_sigmf(meta_path).assumptions
    ingest_ok = (
        a.datatype.value == entry["datatype"]
        and a.datatype.level is EvidenceLevel.MEASURED
        and a.sample_rate.value == sample_rate
        and a.sample_rate.level is EvidenceLevel.MEASURED
        and a.center_frequency.level is EvidenceLevel.UNKNOWN
    )
    return {
        "file": entry["file"],
        "datatype": entry["datatype"],
        "labels": {"class": entry["class"]},
        "ingest": "ok" if ingest_ok else "mismatch",
        **score_raw(meta_path.with_suffix(".sigmf-data"), entry["datatype"], sample_rate),
        "verified": sum(p.level is EvidenceLevel.VERIFIED for p in a.parameters()),
        "acceptedDecodes": 0,
    }


def run_set(bench: BenchSet | None, data: Path) -> dict[str, Any]:
    """Score a seeded set, or the TorchSig export when `bench` is None."""
    manifest = json.loads((data / "manifest.json").read_text(encoding="utf-8"))
    if bench is None:
        rate = float(manifest["sampleRate"])
        rows = [
            score_torchsig(data / f"{e['file']}.sigmf-meta", e, rate) for e in manifest["files"]
        ]
    else:
        rows = [
            score_file(data / f"{e['file']}.sigmf-meta", bench, e["seed"])
            for e in manifest["files"]
        ]
        if bench.chain:
            paths = [data / f"{e['file']}.sigmf-meta" for e in manifest["files"]]
            with ProcessPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) - 1)) as pool:
                chained = list(pool.map(score_chain, paths, chunksize=4))
            for row, result in zip(rows, chained, strict=True):
                row.update(result)
                row["verified"] += result["verifiedParameters"]
    ranks = [r["rateRank"] for r in rows if r["rateRank"] is not None]
    summary: dict[str, Any] = {
        "files": len(rows),
        "ingestMismatches": sum(r["ingest"] != "ok" for r in rows),
        "sniffer": dict(sorted(Counter(r["sniffer"] for r in rows).items())),
        "snifferWrong": sum(r["sniffer"] == "wrong" for r in rows),
        "trueRateAmongCandidates": len(ranks),
        "trueRateMedianRank": float(np.median(ranks)) if ranks else None,
        "verifiedValues": sum(r["verified"] for r in rows),
        "acceptedDecodes": sum(r["acceptedDecodes"] for r in rows),
        "decodingStages": ["analyse: sync, demod, FEC (catalogue and blind), framing"]
        if bench and bench.chain
        else [],
        "detectionsAnalysed": sum(r.get("detections", 0) for r in rows),
        "blindSearched": sum(r.get("blindSearched", 0) for r in rows),
        "blindIdentified": sum(r.get("blindIdentified", 0) for r in rows),
        "note": "The decode chain ran on every file: acceptedDecodes counts detections whose "
        "search accepted a chain, and no null file carries a frame, so each one is a false accept."
        if bench and bench.chain
        else "The decode chain is not run on this set; acceptedDecodes is 0 by construction.",
    }
    return {
        "benchVersion": BENCH_VERSION,
        "set": bench.name if bench else "torchsig",
        "generator": GENERATOR_VERSION if bench else manifest["generator"],
        "numpy": np.__version__,
        "summary": summary,
        "files": None if bench and bench.totals_only else rows,
    }


def markdown(results: dict[str, Any]) -> str:
    s = results["summary"]
    lines = [
        f"# Bench v0: {results['set']} set",
        "",
        f"Generated by `uv run bench run {results['set']}` (bench {results['benchVersion']}, "
        f"generator {results['generator']}, NumPy {results['numpy']}). Do not edit by hand.",
        "",
        *(
            [
                "An independent generator: TorchSig's signals, exported by "
                "`bench/torchsig/export.py` under WSL2. The sniffer was never tuned on them.",
                "",
            ]
            if results["set"] == "torchsig"
            else []
        ),
        "| Measure | Value |",
        "|---|---|",
        f"| Files | {s['files']} |",
        f"| SigMF ingest disagreeing with the truth | {s['ingestMismatches']} |",
        f"| Sniffer: wrong format proposed | {s['snifferWrong']} |",
        f"| True sample rate among the rate candidates | {s['trueRateAmongCandidates']} of "
        f"{s['files']} (median rank {s['trueRateMedianRank']}) |",
        f"| VERIFIED values | {s['verifiedValues']} |",
        f"| Accepted decodes | {s['acceptedDecodes']} "
        + (
            f"(decode chain run on {s['detectionsAnalysed']} detections)"
            if s["decodingStages"]
            else "(decode chain not run on this set)"
        )
        + " |",
        *(
            [
                "| Blind convolutional-code search | "
                f"ran on {s['blindSearched']} branches, named a code on {s['blindIdentified']} |"
            ]
            if s["decodingStages"]
            else []
        ),
        "",
        "Sniffer outcomes, reading each data file as headerless raw samples:",
        "",
        "| Outcome | Files |",
        "|---|---|",
        *(f"| {k} | {v} |" for k, v in s["sniffer"].items()),
        "",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bench", description="Generate and score bench sets.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("generate", "run"):
        p = sub.add_parser(name)
        seeded = ("dev", "null", "sealed")
        # The torchsig set is exported under WSL2 (bench/torchsig/export.py), only scored here.
        p.add_argument("set", choices=seeded if name == "generate" else (*seeded, "torchsig"))
        p.add_argument("--data", type=Path, default=None, help="default: bench/data/<set>")
        if name == "generate":
            p.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    bench = None if args.set == "torchsig" else sets()[args.set]
    data = args.data or DATA / args.set
    if args.command == "generate":
        assert bench is not None
        entries = generate_set(bench, data, args.limit)
        print(f"wrote {len(entries)} files to {data}")
        return 0
    results = run_set(bench, data)
    RESULTS.mkdir(exist_ok=True)
    stem = RESULTS / f"bench-v0-{args.set}"
    stem.with_suffix(".json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    stem.with_suffix(".md").write_text(markdown(results), encoding="utf-8")
    print(json.dumps(results["summary"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
