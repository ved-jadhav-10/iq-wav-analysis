"""`bench`: generate the bench sets and score Sanket on them (PLAN §5 M1, bench v0).

    uv run bench generate dev|null|sealed [--limit N]   write SigMF files to bench/data/<set>/
    uv run bench run dev|null|sealed                    score them, write bench/results/

Every file follows from its seed (bench/presets.py), so only seeds and results are committed.
The sealed set's seeds live in bench/sealed/manifest.json and are never changed; its results
are written as totals only, never per file, so no one tunes against it. Run it only for a
release measurement, not during development.

Bench v0 scores the stages that exist, which is ingest: whether SigMF ingest recovers the truth,
whether the format sniffer, reading each data file as a headerless raw file, proposes the right
format or honestly ties, and whether the true sample rate is among the rate candidates. For the
null set it counts VERIFIED values and accepted decodes; no stage can accept a decode yet, and
the results say so rather than reporting a meaningful zero.
"""

import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from bench.presets import Draw, dev_draw, null_draw
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


def sets() -> dict[str, BenchSet]:
    sealed = json.loads(SEALED.read_text(encoding="utf-8"))
    return {
        "dev": BenchSet("dev", dev_draw, tuple(range(200))),
        "null": BenchSet("null", null_draw, tuple(range(1000))),
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
    param = sniff(rec.data_path).datatype
    candidates = {alt.value for alt in param.alternatives}
    if param.value == draw.datatype:
        sniffed = "correct, by convention" if param.convention else "correct"
    elif param.value is None:
        sniffed = "unknown, truth among candidates" if draw.datatype in candidates else "unknown"
    elif param.convention and str(param.value)[1:] == draw.datatype[1:]:
        sniffed = "layout by convention"
    else:
        sniffed = "wrong"
    rates = [c.value for c in rate_candidates(rec.data_path.name, draw.datatype)]
    rate_rank = rates.index(scene.sample_rate) + 1 if scene.sample_rate in rates else None
    verified = sum(p.level is EvidenceLevel.VERIFIED for p in a.parameters())
    return {
        "seed": seed,
        "datatype": draw.datatype,
        "labels": draw.labels,
        "ingest": "ok" if ingest_ok else "mismatch",
        "sniffer": sniffed,
        "sniffed": param.value,
        "rateRank": rate_rank,
        "verified": verified,
        "acceptedDecodes": 0,
    }


def run_set(bench: BenchSet, data: Path) -> dict[str, Any]:
    manifest = json.loads((data / "manifest.json").read_text(encoding="utf-8"))
    rows = [
        score_file(data / f"{e['file']}.sigmf-meta", bench, e["seed"]) for e in manifest["files"]
    ]
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
        "decodingStages": [],
        "note": "No stage can accept a decode yet (FEC and framing are M5/M6), so acceptedDecodes "
        "is 0 by construction; the null-set gate becomes meaningful when they land.",
    }
    return {
        "benchVersion": BENCH_VERSION,
        "set": bench.name,
        "generator": GENERATOR_VERSION,
        "numpy": np.__version__,
        "summary": summary,
        "files": None if bench.totals_only else rows,
    }


def markdown(results: dict[str, Any]) -> str:
    s = results["summary"]
    lines = [
        f"# Bench v0: {results['set']} set",
        "",
        f"Generated by `uv run bench run {results['set']}` (bench {results['benchVersion']}, "
        f"generator {results['generator']}, NumPy {results['numpy']}). Do not edit by hand.",
        "",
        "| Measure | Value |",
        "|---|---|",
        f"| Files | {s['files']} |",
        f"| SigMF ingest disagreeing with the truth | {s['ingestMismatches']} |",
        f"| Sniffer: wrong format proposed | {s['snifferWrong']} |",
        f"| True sample rate among the rate candidates | {s['trueRateAmongCandidates']} of "
        f"{s['files']} (median rank {s['trueRateMedianRank']}) |",
        f"| VERIFIED values | {s['verifiedValues']} |",
        f"| Accepted decodes | {s['acceptedDecodes']} (no decoding stage exists yet) |",
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
        p.add_argument("set", choices=("dev", "null", "sealed"))
        p.add_argument("--data", type=Path, default=None, help="default: bench/data/<set>")
        if name == "generate":
            p.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    bench = sets()[args.set]
    data = args.data or DATA / bench.name
    if args.command == "generate":
        entries = generate_set(bench, data, args.limit)
        print(f"wrote {len(entries)} files to {data}")
        return 0
    results = run_set(bench, data)
    RESULTS.mkdir(exist_ok=True)
    stem = RESULTS / f"bench-v0-{bench.name}"
    stem.with_suffix(".json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    stem.with_suffix(".md").write_text(markdown(results), encoding="utf-8")
    print(json.dumps(results["summary"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
