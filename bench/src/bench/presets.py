"""Bench v0 presets: each bench file is a scene drawn from its seed, so a seed is the whole file.

The draws cover the generator's space: modulation x pulse shape x FEC x interleaver x framing,
samples per symbol jittered by 10-20 % around a nominal value, Es/N0 from 0 to 30 dB, mild
impairments, some multi-signal scenes, and a datatype and sample rate per file. Null files carry
nothing a decoder should accept: noise, uncoded random bits, a repetition code, or an idle
pattern.
"""

import math
from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np

from dsp.ingest.rate import DEVICE_RATES
from dsp.synth import fec
from dsp.synth import interleave as il
from dsp.synth.bits import FrameSpec
from dsp.synth.chain import Scene, SignalSpec
from dsp.synth.impair import Impairments

SAMPLES = 1 << 16
NULL_SAMPLES = 1 << 14
DATATYPES = ("cu8", "ci8", "ci16_le", "ci16_be", "cf32_le")
LINEAR = ("bpsk", "qpsk", "8psk", "16qam", "64qam")
FSK = ("2fsk", "4fsk", "8fsk")
_LDPC = fec.regular_ldpc(576, 3, 6, seed=26147)

# name -> the SignalSpec fields that make the chain
CHAINS: dict[str, dict[str, Any]] = {
    "uncoded": {},
    "conv 1/2": {"inner": fec.Convolutional(7, fec.K7)},
    "conv 3/4": {"inner": fec.Convolutional(7, fec.K7, fec.PUNCTURES["3/4"])},
    "conv 7/8": {"inner": fec.Convolutional(7, fec.K7, fec.PUNCTURES["7/8"])},
    "RS(255,223) + conv 1/2, CCSDS-like": {
        "scrambler": "CCSDS",
        "outer": fec.RS_CCSDS,
        "byte_interleaver": il.Convolutional(4, 17),
        "inner": fec.Convolutional(7, fec.K7),
    },
    "RS(204,188) + conv 2/3, DVB-like": {
        "outer": fec.RS_DVB,
        "byte_interleaver": il.Convolutional(12, 17),
        "inner": fec.Convolutional(7, fec.K7, fec.PUNCTURES["2/3"]),
    },
    "LDPC(576) + block": {"inner": _LDPC, "interleaver": il.Block(24, 48)},
    "conv 1/2 + block": {"inner": fec.Convolutional(7, fec.K7), "interleaver": il.Block(16, 36)},
    "conv 1/2 + helical": {
        "inner": fec.Convolutional(7, fec.K7),
        "interleaver": il.Helical(12, 12),
    },
    "conv 1/2 + convolutional": {
        "inner": fec.Convolutional(7, fec.K7),
        "interleaver": il.Convolutional(8, 4),
    },
    "conv 1/2 + LTE QPP": {"inner": fec.Convolutional(7, fec.K7), "interleaver": il.QPP[40]},
    "conv 1/2 + 802.11": {"inner": fec.Convolutional(7, fec.K7), "interleaver": il.Wifi(192, 4)},
    "RS(255,223)": {"outer": fec.RS_CCSDS},
}
FRAMES = (
    FrameSpec("CCSDS ASM", 16, 64, "CRC-16/CCITT-FALSE"),
    FrameSpec("Barker-13", 8, 32, "CRC-16/X-25"),
    FrameSpec("POCSAG", 16, 128, "CRC-32"),
)


@dataclass(frozen=True)
class Draw:
    """A bench file: its scene, how to write it, and the preset names behind it."""

    seed: int
    scene: Scene
    datatype: str
    labels: dict[str, Any] = field(default_factory=lambda: {})


def _rate(rng: np.random.Generator) -> float:
    if rng.random() < 0.6:
        family = DEVICE_RATES[int(rng.integers(len(DEVICE_RATES)))]
        return float(family.rates[int(rng.integers(len(family.rates)))])
    return float(round(10 ** rng.uniform(4.7, 7.0)))


def _jitter(rng: np.random.Generator, nominal: float) -> float:
    return round(nominal * (1 + rng.choice([-1, 1]) * rng.uniform(0.10, 0.20)), 4)


def _impairments(rng: np.random.Generator) -> Impairments:
    return Impairments(
        cfo=float(rng.uniform(-2e-3, 2e-3)),
        phase=float(rng.uniform(0, 2 * math.pi)),
        phase_noise=float(rng.choice([0.0, 1e-3, 5e-3])),
        iq_gain_db=float(rng.choice([0.0, 0.3, 1.0])),
        iq_phase_deg=float(rng.choice([0.0, 1.0, 3.0])),
        multipath=((0.0, 1.0, 0.0), (float(rng.uniform(1, 4)), 0.3, 1.0))
        if rng.random() < 0.2
        else (),
        clock_ppm=float(rng.choice([0.0, 20.0, 80.0])),
        agc_db=float(rng.choice([0.0, 2.0])),
        agc_period=20_000.0,
    )


def _digital(
    rng: np.random.Generator, offset: float, power_db: float
) -> tuple[SignalSpec, dict[str, Any]]:
    modulation = str(rng.choice(LINEAR + FSK))
    chain = str(rng.choice(list(CHAINS)))
    fsk = modulation in FSK
    nominal = float(rng.choice([8, 16, 32] if fsk else [2, 4, 8, 16]))
    pulse = "rect" if not fsk and rng.random() < 0.2 else "rrc"
    frame = FRAMES[int(rng.integers(len(FRAMES)))]
    spec = SignalSpec(
        modulation=modulation,
        sps=_jitter(rng, nominal),
        pulse=pulse,
        rolloff=float(rng.choice([0.2, 0.25, 0.35, 0.5])),
        frame=frame,
        stream_offset=int(rng.integers(0, 4096)),
        offset=offset,
        power_db=power_db,
        impairments=_impairments(rng),
        **CHAINS[chain],
    )
    return spec, {"modulation": modulation, "chain": chain, "sync": frame.sync, "pulse": pulse}


def dev_draw(seed: int) -> Draw:
    rng = np.random.default_rng([26147, seed])
    count = 1 if rng.random() < 0.8 else int(rng.integers(2, 4))
    specs: list[SignalSpec] = []
    labels: list[dict[str, Any]] = []
    offsets = rng.permutation(np.linspace(-0.3, 0.3, count)) if count > 1 else [0.0]
    esn0 = float(rng.uniform(0, 30))
    for k in range(count):
        kind = rng.random()
        if kind < 0.8:
            spec, label = _digital(rng, float(offsets[k]), -float(k) * 3)
        elif kind < 0.9:
            spec = SignalSpec(str(rng.choice(["am", "fm"])), offset=float(offsets[k]), frame=None)
            label = {"modulation": spec.modulation}
        else:
            spec = SignalSpec("noise", frame=None, power_db=-float(k) * 3)
            label = {"modulation": "noise"}
        if count > 1:
            start = int(rng.integers(0, SAMPLES // 2))
            spec = replace(
                spec, start=start, duration=int(rng.integers(SAMPLES // 4, SAMPLES - start))
            )
        specs.append(spec)
        labels.append(label)
    first = specs[0]
    noise_db = -esn0 + 10 * math.log10(first.sps) if first.modulation in LINEAR + FSK else -esn0
    scene = Scene(
        SAMPLES,
        tuple(specs),
        noise_db=round(noise_db, 4),
        sample_rate=_rate(rng),
        center_frequency=float(round(10 ** rng.uniform(6.5, 9.3))),
    )
    return Draw(seed, scene, str(rng.choice(DATATYPES)), {"signals": labels})


NULL_KINDS = ("noise", "uncoded", "repetition", "idle")


def null_draw(seed: int) -> Draw:
    """Nothing here carries a decodable frame: a decoder that accepts one is wrong."""
    rng = np.random.default_rng([26148, seed])
    kind = NULL_KINDS[seed % len(NULL_KINDS)]
    modulation = str(rng.choice(LINEAR + FSK))
    sps = _jitter(rng, float(rng.choice([8, 16]) if modulation in FSK else rng.choice([2, 4, 8])))
    if kind == "noise":
        spec = SignalSpec("noise", frame=None)
    elif kind == "uncoded":
        spec = SignalSpec(modulation, sps=sps, frame=None)
    elif kind == "repetition":
        spec = SignalSpec(
            modulation, sps=sps, frame=None, inner=fec.Repetition(int(rng.integers(2, 6)))
        )
    else:
        # Idle: HDLC flags (0x7E) repeated, as a transmitter sends between frames.
        spec = SignalSpec(modulation, sps=sps, frame=None, fill=0x7E)
    esn0 = float(rng.uniform(0, 30))
    scene = Scene(
        NULL_SAMPLES,
        (spec,),
        noise_db=round(-esn0 + (10 * math.log10(sps) if kind != "noise" else 0), 4),
        sample_rate=_rate(rng),
        center_frequency=float(round(10 ** rng.uniform(6.5, 9.3))),
    )
    return Draw(
        seed, scene, str(rng.choice(DATATYPES)), {"null": kind, "modulation": spec.modulation}
    )
