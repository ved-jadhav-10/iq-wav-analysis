"""`bench run torchsig` scores files in the layout bench/torchsig/export.py writes."""

import json
from pathlib import Path

import numpy as np

from bench.cli import markdown, run_set
from dsp.ingest.formats import SampleFormat
from dsp.synth.waveforms import awgn, frequency_shift, psk_symbols, shape

RATE = 10_000_000


def export(out: Path, name: str, datatype: str, meta_datatype: str | None = None) -> dict:
    rng = np.random.default_rng(3)
    x = frequency_shift(shape(psk_symbols(rng, 4097, 4), 4, 0.35)[: 1 << 14], 0.1)
    x = 0.25 * (x + awgn(rng, len(x), 0.01)) / np.sqrt(np.mean(np.abs(x) ** 2))
    (out / f"{name}.sigmf-data").write_bytes(SampleFormat.parse(datatype).encode(x))
    meta = {
        "global": {"core:datatype": meta_datatype or datatype, "core:sample_rate": RATE},
        "captures": [{"core:sample_start": 0}],
        "annotations": [{"core:sample_start": 0, "core:label": "qpsk"}],
    }
    (out / f"{name}.sigmf-meta").write_text(json.dumps(meta), encoding="utf-8")
    return {"file": name, "class": "qpsk", "datatype": datatype}


def test_torchsig_files_are_scored_against_their_manifest(tmp_path: Path) -> None:
    files = [
        export(tmp_path, "ts-qpsk-0", "ci16_le"),
        export(tmp_path, "ts-qpsk-1", "cu8"),
        export(tmp_path, "ts-qpsk-2", "ci8", meta_datatype="cu8"),  # metadata disagrees
    ]
    manifest = {"generator": "torchsig 2.2.0", "sampleRate": RATE, "files": files}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    results = run_set(None, tmp_path)
    s = results["summary"]
    assert (results["set"], results["generator"]) == ("torchsig", "torchsig 2.2.0")
    assert (s["files"], s["ingestMismatches"], s["snifferWrong"]) == (3, 1, 0)
    assert [r["sniffer"] for r in results["files"]] == ["correct"] * 3
    assert s["trueRateAmongCandidates"] == 3
    assert "independent generator" in markdown(results)
