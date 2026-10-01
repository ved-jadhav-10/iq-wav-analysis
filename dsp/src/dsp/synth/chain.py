"""The ground-truth generator: a scene of signals in noise, each built from bits up, written as
SigMF with the truth in annotations (PLAN §5 M1).

A signal's transmit chain, in order: random payload bytes -> frames (sync word, counter, payload,
CRC) -> optional scrambler (after the sync word, restarting each frame) -> optional Reed-Solomon
outer code -> optional byte interleaver -> optional inner code (convolutional, LDPC or
repetition) -> optional bit interleaver -> symbol mapping -> pulse shaping at an integer rate ->
resampling to the requested (possibly non-integer) samples per symbol -> impairments ->
frequency offset -> placement in the scene. Noise is added to the whole scene last.

The coded stream is continuous and the recording starts `stream_offset` coded bits into it,
as a real capture starts mid-stream. Blocks at the end of the stream are cut where the
recording ends. Everything follows from (scene, seed): `generate` twice gives identical samples
and bits, so a test can regenerate the exact bits behind any bench file.

Signal levels: each signal's power is `power_db` and the noise power per sample is `noise_db`,
both relative to 1. The truth records the per-sample SNR and, for digital signals, Es/N0 =
SNR + 10 log10(samples per symbol).
"""

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from dsp.ingest.formats import SampleFormat
from dsp.synth import fec as fec_
from dsp.synth import interleave as il
from dsp.synth.bits import (
    SCRAMBLERS,
    Bits,
    FrameSpec,
    SelfSyncScrambler,
    frames,
    to_bits,
    to_bytes,
)
from dsp.synth.impair import Impairments, apply, awgn
from dsp.synth.modulate import BITS_PER_SYMBOL, LINEAR, am, audio, fm, fsk, map_bits, pulse_shape
from dsp.synth.modulate import resample as resample_
from dsp.synth.systems import Dsc, Navtex, Pocsag

Complex = NDArray[np.complex128]
GENERATOR_VERSION = "0.1.0"
FSK = {"2fsk": 2, "4fsk": 4, "8fsk": 8}
ANALOG = ("am", "fm")
MODULATIONS = (*LINEAR, *FSK, *ANALOG, "noise")

InnerCode = fec_.Convolutional | fec_.Ldpc | fec_.Repetition
BitInterleaver = il.BlockInterleaver | il.Convolutional


@dataclass(frozen=True)
class SignalSpec:
    modulation: str = "qpsk"
    sps: float = 4.0  # samples per symbol; need not be an integer
    pulse: str = "rrc"  # "rrc" or "rect"
    rolloff: float = 0.35
    fsk_index: float = 1.0  # modulation index h: tones h * symbol rate apart
    # Gaussian premodulation filter bandwidth-time product (0 = an abrupt step at each symbol).
    # Default 0: a bt sweep over [0.02, 2.0] for the STANDARDS §8 false-detection target (PLAN
    # §5 M2) found a three-way conflict, not a single wrong-direction mistake. bt in roughly
    # [0.02, 0.15] does fix detection's splatter (dsp.detect.merge_tone_combs sees one blob
    # instead of several stray tones), but by then blurring 2/4/8-FSK's discrete tone histogram
    # toward FM's continuous one, it fails dsp.analog's kurtosis gate
    # (test_fsk_is_not_mistaken_for_fm_even_though_both_are_constant_envelope) and smears the
    # sharp transitions dsp.estimate.params.fsk_symbol_rate's edge-rate comb depends on
    # (test_fsk_symbol_rate_matches_the_true_rate). bt in [0.2, 0.4] fails two of the three at
    # once. Only bt=0 and bt >~ 0.5-2.0 (weak enough to be close to a no-op) pass every test, and
    # those barely move the bench numbers. Left as a lever for whoever revisits this, not turned
    # on by default; a real fix likely needs a filter that reduces splatter without erasing the
    # discrete-tone signature the other two stages read off the same trajectory.
    fsk_bt: float = 0.0
    frame: FrameSpec | None = field(default_factory=FrameSpec)
    # A known system's own transmission in place of the frame/code chain below (which then
    # does not apply): its bits are the coded stream.
    system: Pocsag | Navtex | Dsc | None = None
    scrambler: str | None = None
    outer: fec_.ReedSolomon | None = None
    byte_interleaver: il.Convolutional | None = None
    inner: InnerCode | None = None
    interleaver: BitInterleaver | None = None
    stream_offset: int = 0  # coded bits skipped before the recording starts
    fill: int | None = None  # constant payload byte (an idle pattern) instead of random data
    offset: float = 0.0  # carrier position, cycles/sample
    start: int = 0  # first sample of the burst
    duration: int | None = None  # burst length in samples; None runs to the end
    power_db: float = 0.0
    impairments: Impairments = field(default_factory=Impairments)
    audio_bandwidth: float = 0.02  # analog: message bandwidth, cycles/sample
    am_depth: float = 0.8
    fm_deviation: float = 0.02  # analog FM peak deviation, cycles/sample


@dataclass(frozen=True)
class Scene:
    samples: int
    signals: tuple[SignalSpec, ...]
    noise_db: float = -20.0
    sample_rate: float | None = None  # Hz; None keeps everything in cycles/sample
    center_frequency: float | None = None  # Hz


@dataclass
class SignalBits:
    """What one signal carried, for tests that need the exact bits."""

    payloads: NDArray[np.uint8]  # one row of payload bytes per frame
    framed: Bits  # frames, before any scrambling or coding
    coded: Bits  # the transmitted bit stream, from the recording's first symbol
    symbols: Complex  # the transmitted symbols (linear modulations)


@dataclass
class Generated:
    samples: Complex
    truth: dict[str, Any]
    signals: list[SignalBits]


def generate(scene: Scene, seed: int) -> Generated:
    rng = np.random.default_rng(seed)
    total = np.zeros(scene.samples, dtype=np.complex128)
    truths: list[dict[str, Any]] = []
    carried: list[SignalBits] = []
    for index, spec in enumerate(scene.signals):
        length = spec.duration or scene.samples - spec.start
        length = max(0, min(length, scene.samples - spec.start))
        x, bits, truth = _signal(spec, length, np.random.default_rng([seed, index]))
        x = apply(x, spec.impairments, np.random.default_rng([seed, index, 1]))
        x = x * np.exp(2j * np.pi * spec.offset * np.arange(length))
        total[spec.start : spec.start + length] += x
        snr = spec.power_db - scene.noise_db
        truth |= {"snrDb": round(snr, 6), "sampleStart": spec.start, "sampleCount": length}
        if spec.modulation in LINEAR or spec.modulation in FSK:
            truth["esn0Db"] = round(snr + 10 * math.log10(spec.sps), 6)
        if scene.sample_rate:
            truth |= _hertz(truth, spec, scene.sample_rate)
        truths.append(truth)
        carried.append(bits)
    total += awgn(rng, scene.samples, 10 ** (scene.noise_db / 10))
    return Generated(
        total,
        {
            "generator": f"dsp.synth {GENERATOR_VERSION}",
            "seed": seed,
            "samples": scene.samples,
            "noiseDb": scene.noise_db,
            "signals": truths,
        },
        carried,
    )


def _signal(
    spec: SignalSpec, length: int, rng: np.random.Generator
) -> tuple[Complex, SignalBits, dict[str, Any]]:
    truth: dict[str, Any] = {"modulation": spec.modulation, "offset": spec.offset}
    none = np.zeros(0, np.uint8)
    empty = SignalBits(np.zeros((0, 0), np.uint8), none, none, np.zeros(0, np.complex128))
    if spec.modulation == "noise":
        return awgn(rng, length, 1.0) * 10 ** (spec.power_db / 20), empty, truth
    if spec.modulation in ANALOG:
        message = audio(rng, length, spec.audio_bandwidth)
        x = (
            am(message, spec.am_depth)
            if spec.modulation == "am"
            else fm(message, spec.fm_deviation)
        )
        truth["audioBandwidth"] = spec.audio_bandwidth
        if spec.modulation == "am":
            truth["amDepth"] = spec.am_depth
        else:
            truth["fmDeviation"] = spec.fm_deviation
        return _normalise(x, spec.power_db), empty, truth
    if spec.modulation not in MODULATIONS:
        raise ValueError(f"unknown modulation {spec.modulation!r}")
    base = max(4, math.ceil(spec.sps))  # integer rate for shaping, then resampled
    symbols_needed = math.ceil(length / spec.sps) + 64
    width = BITS_PER_SYMBOL.get(spec.modulation) or int(math.log2(FSK[spec.modulation]))
    payloads, framed, coded = _bitstream(spec, symbols_needed * width + spec.stream_offset, rng)
    coded = coded[spec.stream_offset : spec.stream_offset + symbols_needed * width]
    if spec.modulation in FSK:
        symbols = np.zeros(0, np.complex128)
        x = fsk(coded, FSK[spec.modulation], base, spec.fsk_index / (2 * base), spec.fsk_bt)
        truth |= {"fskIndex": spec.fsk_index, "tones": FSK[spec.modulation], "fskBt": spec.fsk_bt}
    else:
        symbols = map_bits(coded, spec.modulation)
        x = pulse_shape(symbols, base, spec.pulse, spec.rolloff)
        truth |= {"pulse": spec.pulse, "rolloff": spec.rolloff if spec.pulse == "rrc" else None}
    if spec.sps != base:
        x = resample_(x, np.arange(length, dtype=np.float64) * float(base / spec.sps))
    x = x[:length]
    truth |= {
        "sps": spec.sps,
        "bitsPerSymbol": width,
        "streamOffsetBits": spec.stream_offset,
        "fill": None if spec.fill is None else f"0x{spec.fill:02X}",
        "frame": spec.frame.truth() if spec.frame and spec.system is None else None,
        "scrambler": spec.scrambler,
        "outerCode": spec.outer.truth() if spec.outer else None,
        "byteInterleaver": spec.byte_interleaver.truth() if spec.byte_interleaver else None,
        "innerCode": spec.inner.truth() if spec.inner else None,
        "interleaver": spec.interleaver.truth() if spec.interleaver else None,
        "impairments": spec.impairments.truth(),
    }
    if spec.system:  # only when set, so every other signal's truth is unchanged
        truth["system"] = spec.system.truth()
    return _normalise(x, spec.power_db), SignalBits(payloads, framed, coded, symbols), truth


def _bitstream(
    spec: SignalSpec, needed: int, rng: np.random.Generator
) -> tuple[NDArray[np.uint8], Bits, Bits]:
    """Payloads, framed bits and the coded stream, with at least `needed` coded bits."""
    if spec.system is not None:
        return spec.system.stream(needed, rng)
    frame = spec.frame
    payload_bytes = frame.payload_bytes if frame else 64
    count = 8
    while True:
        payloads = (
            np.full((count, payload_bytes), spec.fill, dtype=np.uint8)
            if spec.fill is not None
            else rng.integers(0, 256, (count, payload_bytes), dtype=np.uint8)
        )
        if frame:
            framed = frames(frame, payloads)
            stream = _scramble(framed, frame, spec.scrambler)
        else:
            framed = to_bits(payloads.tobytes())
            stream = framed
        coded = _encode(stream, spec, rng)
        if len(coded) >= needed:
            return payloads, framed, coded
        count *= 2


def _scramble(bits: Bits, frame: FrameSpec, scrambler: str | None) -> Bits:
    if scrambler is None:
        return bits
    s, n = SCRAMBLERS[scrambler], len(frame.sync_bits)
    if isinstance(s, SelfSyncScrambler):
        return s.apply(bits)  # the whole stream, sync word included
    rows = bits.reshape(-1, frame.length).copy()
    for row in rows:
        row[n:] = s.apply(row[n:])
    return rows.ravel()


def _encode(bits: Bits, spec: SignalSpec, rng: np.random.Generator) -> Bits:
    stream = bits
    if spec.outer:
        stream = _pad(stream, 8 * spec.outer.k, rng)
        data = spec.outer.encode(to_bytes(stream))
        if spec.byte_interleaver:
            data = spec.byte_interleaver.interleave(np.frombuffer(data, np.uint8)).tobytes()
        stream = to_bits(data)
    elif spec.byte_interleaver:
        stream = _pad(stream, 8, rng)
        stream = to_bits(
            spec.byte_interleaver.interleave(np.frombuffer(to_bytes(stream), np.uint8))
        )
    if isinstance(spec.inner, fec_.Ldpc):
        stream = spec.inner.encode(_pad(stream, spec.inner.k, rng))
    elif spec.inner is not None:
        stream = spec.inner.encode(stream)
    if isinstance(spec.interleaver, il.Convolutional):
        stream = spec.interleaver.interleave(stream)
    elif spec.interleaver is not None:
        stream = il.interleave(_pad(stream, spec.interleaver.size, rng), spec.interleaver)
    return stream


def _pad(bits: Bits, multiple: int, rng: np.random.Generator) -> Bits:
    short = -len(bits) % multiple
    return np.concatenate([bits, rng.integers(0, 2, short, dtype=np.uint8)]) if short else bits


def _normalise(x: Complex, power_db: float) -> Complex:
    power = float(np.mean(np.abs(x) ** 2))
    return x / math.sqrt(power) * 10 ** (power_db / 20) if power > 0 else x


def _hertz(truth: dict[str, Any], spec: SignalSpec, fs: float) -> dict[str, Any]:
    out: dict[str, Any] = {"offsetHz": spec.offset * fs}
    if "sps" in truth:
        out["symbolRate"] = fs / spec.sps
    return out


def write_sigmf(
    stem: Path,
    generated: Generated,
    scene: Scene,
    datatype: str = "cf32_le",
    level_dbfs: float = -12.0,
) -> Path:
    """Write `<stem>.sigmf-meta` and `<stem>.sigmf-data`; integers scaled to `level_dbfs` RMS."""
    fmt = SampleFormat.parse(datatype)
    x = generated.samples if fmt.is_complex else generated.samples.real
    if fmt.kind != "f":
        rms = math.sqrt(float(np.mean(np.abs(x) ** 2)) / (2 if fmt.is_complex else 1))
        x = x / rms * 10 ** (level_dbfs / 20)
    data = fmt.encode(x)
    clipped = int(np.sum(np.abs(np.real(x)) >= 1) + np.sum(np.abs(np.imag(x)) >= 1))
    stem.parent.mkdir(parents=True, exist_ok=True)
    stem.with_suffix(".sigmf-data").write_bytes(data)
    global_: dict[str, Any] = {
        "core:datatype": datatype,
        "core:version": "1.2.0",
        "core:recorder": f"sanket dsp.synth {GENERATOR_VERSION}",
        "core:description": "Synthetic recording with exact ground truth",
        "core:extensions": [{"name": "sanket", "version": GENERATOR_VERSION, "optional": True}],
        "sanket:truth": generated.truth | {"datatype": datatype, "clippedComponents": clipped},
    }
    if scene.sample_rate:
        global_["core:sample_rate"] = scene.sample_rate
    capture: dict[str, Any] = {"core:sample_start": 0}
    if scene.center_frequency is not None:
        capture["core:frequency"] = scene.center_frequency
    annotations = [_annotation(t, scene) for t in generated.truth["signals"]]
    meta = {"global": global_, "captures": [capture], "annotations": annotations}
    path = stem.with_suffix(".sigmf-meta")
    path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _annotation(truth: dict[str, Any], scene: Scene) -> dict[str, Any]:
    note: dict[str, Any] = {
        "core:sample_start": truth["sampleStart"],
        "core:sample_count": truth["sampleCount"],
        "core:label": truth["modulation"],
        "sanket:truth": truth,
    }
    if scene.sample_rate and scene.center_frequency is not None and "sps" in truth:
        half = scene.sample_rate / truth["sps"] * (1 + (truth.get("rolloff") or 0)) / 2
        centre = scene.center_frequency + truth["offsetHz"]
        note["core:freq_lower_edge"] = centre - half
        note["core:freq_upper_edge"] = centre + half
    return note
