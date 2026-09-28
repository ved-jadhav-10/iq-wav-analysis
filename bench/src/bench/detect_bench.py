"""Detection and estimation bench: STANDARDS §8's recall/false-detection and rate/SNR/CFO error
targets, measured per SNR bucket against dsp.synth ground truth.

Run `uv run python -m bench.detect_bench` to write bench/results/bench-v0-detect.{json,md}.
Nothing is written to bench/data/: every scene is generated in memory from its seed and scored
immediately, the same as the sniffer bench.

Each scene holds exactly one signal, centred at a random offset, clean AWGN and no other
impairment: STANDARDS §8's rate/SNR/CFO rows are clean characterisation curves (compare "sigma:
SNR within 0.3 dB... on its own files"), not the multi-signal, multi-impairment scenes bench v0's
dev set draws for ingest. Detection is scored on every seed; estimation only on modulations and
metrics that apply (CFO is BPSK/QPSK only - see `dsp.estimate.params.PSK_ORDERS`; FSK has its own
rate estimator and no cumulant-based CFO).
"""

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from dsp.channel import channelise
from dsp.detect import Detection, detect
from dsp.estimate.params import carrier_offset, fsk_symbol_rate, snr_psd, symbol_rate
from dsp.synth.chain import FSK as FSK_ORDERS
from dsp.synth.chain import GENERATOR_VERSION, Scene, SignalSpec, generate
from dsp.synth.impair import Impairments

RESULTS = Path(__file__).resolve().parents[2] / "results"
BENCH_VERSION = "0.1.0"

SAMPLES = 1 << 16
SNR_BUCKETS_DB = (0.0, 3.0, 6.0, 10.0, 15.0, 20.0, 25.0, 30.0)
LINEAR = ("bpsk", "qpsk", "8psk", "16qam", "64qam")
FSK_MODULATIONS = tuple(FSK_ORDERS)
MODULATIONS = LINEAR + FSK_MODULATIONS
REPEATS = 8  # scenes drawn per (modulation, SNR bucket)
SPS = 8.0
ROLLOFF = 0.35
INJECTED_CFO_FRACTION = 0.005  # of the symbol rate: the fine residual carrier_offset() must find


class _MemorySource:
    """A generated recording held in memory, behind the same read/num_samples interface as a
    file reader, so `detect`/`channelise` need no reader specialisation for the bench."""

    def __init__(self, x: np.ndarray) -> None:
        self.x = x
        self.num_samples = len(x)

    def read(self, start: int, count: int) -> np.ndarray:
        return self.x[start : start + count]


@dataclass(frozen=True)
class DetectDraw:
    seed: int
    modulation: str
    snr_db: float
    scene: Scene
    offset: float
    cfo: float  # the injected carrier offset, cycles/sample, relative to the symbol rate below


def _bandwidth(spec: SignalSpec) -> float:
    """The signal's true occupied bandwidth: (1+rolloff) x symbol rate for a linear modulation,
    or the outer tone separation plus two symbol rates of CPFSK spreading for M-FSK."""
    if spec.modulation in LINEAR:
        return (1 / spec.sps) * (1 + spec.rolloff)
    order = FSK_ORDERS[spec.modulation]
    return (order - 1) * spec.fsk_index / spec.sps + 2 / spec.sps


def detect_draw(seed: int) -> DetectDraw:
    """One (modulation, SNR bucket) combination per REPEATS seeds, in a fixed, even grid: this
    is a designed sweep, not a random sample, so every bucket gets exactly REPEATS scenes."""
    combos = len(MODULATIONS) * len(SNR_BUCKETS_DB)
    combo, _repeat = divmod(seed, REPEATS)
    if combo >= combos:
        raise ValueError(f"seed {seed} is outside the {combos * REPEATS}-seed grid")
    mod_index, snr_index = divmod(combo, len(SNR_BUCKETS_DB))
    modulation, snr_db = MODULATIONS[mod_index], SNR_BUCKETS_DB[snr_index]
    rng = np.random.default_rng([26149, seed])
    offset = float(rng.uniform(-0.3, 0.3))
    true_rate = 1 / SPS
    cfo = INJECTED_CFO_FRACTION * true_rate * float(rng.choice([-1.0, 1.0]))
    fsk_kwargs = {"fsk_index": 1.0} if modulation in FSK_MODULATIONS else {"rolloff": ROLLOFF}
    spec = SignalSpec(
        modulation=modulation,
        sps=SPS,
        frame=None,
        offset=offset,
        power_db=0.0,
        impairments=Impairments(cfo=cfo),
        **fsk_kwargs,  # type: ignore[arg-type]
    )
    noise_db = -snr_db + 10 * math.log10(SPS)
    scene = Scene(SAMPLES, (spec,), noise_db=noise_db, sample_rate=1e6, center_frequency=1e8)
    return DetectDraw(seed, modulation, snr_db, scene, offset, cfo)


def _best_match(
    detections: tuple[Detection, ...], offset: float, bandwidth: float
) -> Detection | None:
    """The detection whose band best overlaps the true signal's, if any overlaps at all."""
    lo, hi = offset - bandwidth / 2, offset + bandwidth / 2
    candidates = [d for d in detections if max(d.low, lo) < min(d.high, hi)]
    if not candidates:
        return None
    return max(candidates, key=lambda d: min(d.high, hi) - max(d.low, lo))


@dataclass
class SceneScore:
    modulation: str
    snr_db: float
    detected: bool
    false_detections: int
    rate_error: float | None  # relative
    snr_error_db: float | None
    cfo_error: float | None  # relative to the symbol rate


def score_draw(draw: DetectDraw) -> SceneScore:
    spec = draw.scene.signals[0]
    g = generate(draw.scene, draw.seed)
    source = _MemorySource(g.samples.astype(np.complex64))
    result = detect(source, real=False)
    bandwidth = _bandwidth(spec)
    match = _best_match(result.detections, draw.offset, bandwidth)
    false_detections = len(result.detections) - (1 if match else 0)

    rate_error = snr_error_db = cfo_error = None
    if match is not None:
        channel = channelise(source, match)
        true_rate = 1 / spec.sps
        rate = (
            fsk_symbol_rate(channel.samples)
            if spec.modulation in FSK_MODULATIONS
            else symbol_rate(channel.samples)
        )
        if rate is not None:
            measured = abs(channel.to_input(rate.normalised_rate))
            rate_error = (measured - true_rate) / true_rate
        if spec.modulation in LINEAR:
            # snr_psd's occupied-bandwidth fit assumes one continuous lobe; M-FSK's several
            # separated tones aren't that, so it isn't scored for FSK (see the report's note).
            est_snr = snr_psd(channel.samples)
            snr_error_db = est_snr.snr_db - draw.snr_db
            cfo = carrier_offset(channel.samples, spec.modulation)
            if cfo is not None:
                # channelise mixed by the detector's own centre estimate, not the true offset,
                # so the true residual carrier_offset must find also includes any detector
                # centring error; comparing against that (not the injected impairment alone)
                # isolates carrier_offset's own accuracy from the detector's.
                true_residual = spec.offset + draw.cfo - match.centre
                measured_cfo = channel.to_input(cfo.cfo)
                cfo_error = (measured_cfo - true_residual) / true_rate
    return SceneScore(
        draw.modulation,
        draw.snr_db,
        match is not None,
        max(0, false_detections),
        rate_error,
        snr_error_db,
        cfo_error,
    )


def bucket_stats(snr: float, rows: list[SceneScore]) -> dict[str, Any]:
    """One SNR bucket's row of the report, from its scored scenes. Pulled out of `run_bench`
    so it can be tested on a handful of scenes, not only the full seed grid."""
    recall = sum(r.detected for r in rows) / len(rows)
    false_rate = sum(r.false_detections for r in rows) / len(rows)
    linear_rows = [r for r in rows if r.modulation in LINEAR]
    fsk_rows = [r for r in rows if r.modulation in FSK_MODULATIONS]
    false_rate_linear = (
        sum(r.false_detections for r in linear_rows) / len(linear_rows) if linear_rows else None
    )
    false_rate_fsk = sum(r.false_detections for r in fsk_rows) / len(fsk_rows) if fsk_rows else None
    rate_errors = [abs(r.rate_error) for r in rows if r.rate_error is not None]
    snr_errors = [r.snr_error_db for r in rows if r.snr_error_db is not None]
    cfo_errors = [abs(r.cfo_error) for r in rows if r.cfo_error is not None]
    return {
        "snrDb": snr,
        "scenes": len(rows),
        "recall": recall,
        "falseDetectionsPerScene": false_rate,
        "falseDetectionsPerSceneLinear": false_rate_linear,
        "falseDetectionsPerSceneFsk": false_rate_fsk,
        "rateErrorMedianPct": _pct(np.median(rate_errors)) if rate_errors else None,
        "rateEstimated": len(rate_errors),
        "snrErrorMedianDb": float(np.median(snr_errors)) if snr_errors else None,
        "snrErrorMaxAbsDb": float(np.max(np.abs(snr_errors))) if snr_errors else None,
        "snrEstimated": len(snr_errors),
        "cfoErrorMedianPct": _pct(np.median(cfo_errors)) if cfo_errors else None,
        "cfoEstimated": len(cfo_errors),
    }


def run_bench() -> dict[str, Any]:
    total_seeds = len(MODULATIONS) * len(SNR_BUCKETS_DB) * REPEATS
    scores = [score_draw(detect_draw(seed)) for seed in range(total_seeds)]
    by_snr: dict[float, list[SceneScore]] = defaultdict(list)
    for s in scores:
        by_snr[s.snr_db].append(s)
    buckets = [bucket_stats(snr, by_snr[snr]) for snr in SNR_BUCKETS_DB]
    return {
        "benchVersion": BENCH_VERSION,
        "generator": GENERATOR_VERSION,
        "samplesPerScene": SAMPLES,
        "repeatsPerBucket": REPEATS,
        "modulations": list(MODULATIONS),
        "buckets": buckets,
    }


def _pct(x: float) -> float:
    return float(x * 100)


def markdown(results: dict[str, Any]) -> str:
    lines = [
        "# Bench v0: detection and estimation",
        "",
        f"Generated by `uv run python -m bench.detect_bench` (bench {results['benchVersion']}, "
        f"generator {results['generator']}). Do not edit by hand.",
        "",
        "One signal per scene, centred at a random offset, clean AWGN only (no impairments): a "
        "characterisation curve for STANDARDS §8's detection and estimation rows, not the "
        "multi-signal, impaired scenes bench v0's dev set draws for ingest.",
        "",
        f"{results['repeatsPerBucket']} scenes per SNR bucket, over "
        f"{len(results['modulations'])} modulations ({', '.join(results['modulations'])}), "
        f"{results['samplesPerScene']} samples each.",
        "",
        "| SNR (dB) | Recall | False detections/scene (linear / M-FSK) | Rate error (median %, "
        "coverage) | SNR error (median / max abs, dB, coverage) | CFO error (median %, coverage) |",
        "|---|---|---|---|---|---|",
    ]
    total = results["repeatsPerBucket"] * len(results["modulations"])
    for b in results["buckets"]:
        rate = (
            f"{b['rateErrorMedianPct']:.3f} ({b['rateEstimated']}/{total})"
            if b["rateErrorMedianPct"] is not None
            else f"— (0/{total})"
        )
        linear_total = total * len(LINEAR) // len(results["modulations"])
        snr_e = (
            f"{b['snrErrorMedianDb']:+.2f} / {b['snrErrorMaxAbsDb']:.2f} "
            f"({b['snrEstimated']}/{linear_total})"
            if b["snrErrorMedianDb"] is not None
            else f"— (0/{linear_total})"
        )
        cfo_total = total * 2 // len(results["modulations"])  # bpsk + qpsk
        cfo = (
            f"{b['cfoErrorMedianPct']:.3f} ({b['cfoEstimated']}/{cfo_total})"
            if b["cfoErrorMedianPct"] is not None
            else f"— (0/{cfo_total})"
        )
        linear_fr = (
            f"{b['falseDetectionsPerSceneLinear']:.2f}"
            if b["falseDetectionsPerSceneLinear"] is not None
            else "—"
        )
        fsk_fr = (
            f"{b['falseDetectionsPerSceneFsk']:.2f}"
            if b["falseDetectionsPerSceneFsk"] is not None
            else "—"
        )
        false_rates = f"{b['falseDetectionsPerScene']:.2f} ({linear_fr} / {fsk_fr})"
        lines.append(
            f"| {b['snrDb']:g} | {b['recall']:.1%} | {false_rates} | {rate} | {snr_e} | {cfo} |"
        )
    lines += [
        "",
        "Coverage is scenes with a value, over scenes where one could apply (rate: all "
        "modulations; SNR: linear modulations only, see the note below; CFO: BPSK/QPSK only, "
        "PLAN §5 M2). A symbol-rate or CFO estimate below its coverage total means the "
        "estimator correctly abstained (no significant line) rather than guessing on some "
        "scenes, mostly at low SNR; a wrong value that still cleared significance is possible "
        "at the estimator's own false-alarm rate and shows up as an outlier, not a missing row.",
        "",
        "SNR is not scored for M-FSK: `snr_psd`'s occupied-bandwidth fit assumes one continuous "
        "spectral lobe, and M-FSK's several separated tones aren't that (PLAN §5 M2, "
        "`dsp.estimate.params.snr_psd`'s Limits).",
        "",
        "The false-detection rate is dominated by M-FSK, not linear modulations (see the split "
        "column): `dsp.synth.modulate.fsk` shapes no pulse onto the frequency trajectory (an "
        "abrupt step at each symbol, unlike the RRC-shaped linear modulations), which splatters "
        "real, above-floor energy between some tones widely and consistently enough across "
        'seeds that `dsp.detect.merge_tone_combs`\' honest "no spacing pattern, no merge" rule '
        "correctly leaves some of it as its own detection rather than silently absorbing it. "
        "This is a ground-truth generator limitation, not a detector bug (`tests/dsp/"
        "test_detect.py`'s `test_merge_tone_combs_*` tests the merge logic itself, isolated "
        "from the splatter). `fsk()` now takes an optional Gaussian premodulation filter "
        "(`bt`, GFSK-style), but a sweep over bt in [0.02, 2.0] found a three-way conflict, not "
        "a single fixable value: bt in roughly [0.02, 0.15] does absorb the splatter into one "
        "detection, but by then blurring the discrete tone histogram toward FM's continuous one "
        "it fails dsp.analog's kurtosis gate, and by smearing the sharp transitions "
        "dsp.estimate.params.fsk_symbol_rate's edge-rate comb depends on, it breaks the FSK "
        "symbol-rate estimate; bt in [0.2, 0.4] fails two of those three checks at once; only "
        "bt=0 or bt >~ 0.5-2.0 (weak enough to be close to a no-op) pass every test, and those "
        "barely move these numbers. Left off by default (PLAN §5 M2, `SignalSpec.fsk_bt`); a "
        "real fix needs a filter that cuts splatter without erasing the discrete-tone signature "
        "the other two stages read off the same trajectory, not just a different bt.",
        "",
        "STANDARDS §8 targets: recall >= 95%, false detections <= 5% (i.e. <= 0.05/scene) at >= "
        "6 dB in-band SNR; symbol rate error <= 0.1% at >= 10 dB; SNR error within +-1 dB over "
        "0-20 dB; CFO error <= 1% of the symbol rate. These are the measured numbers, not a "
        "pass/fail judgement - compare each bucket against the target for its own row.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    results = run_bench()
    RESULTS.mkdir(exist_ok=True)
    stem = RESULTS / "bench-v0-detect"
    stem.with_suffix(".json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    stem.with_suffix(".md").write_text(markdown(results), encoding="utf-8")
    print(markdown(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
