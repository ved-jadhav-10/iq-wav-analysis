"""Sample-rate and centre-frequency candidates for recordings whose metadata doesn't state them.

Nothing in the samples fixes the sample rate: every estimate is a fraction of it. So a recording
without metadata gets ranked candidates, never a silent pick (PLAN §5 M1):

1. hints in the file name: an explicit tag (`fs=2.4M`, `sr_250k`), the gqrx naming scheme
   (`gqrx_<date>_<time>_<centre Hz>_<rate>_fc.raw`), or a number with a rate unit (`2.4Msps`);
2. standard rates of common SDR receivers, those whose recorder writes the file's datatype first.

The sample rate stays UNKNOWN, with the candidates as its alternatives, until a structural match
promotes one to HYPOTHESIS: a recognised symbol rate equals the measured normalised symbol rate
times the candidate, within the tolerance. Every (candidate, symbol rate) pair is a hypothesis.
The pairs are tested in two tiers that share ALPHA equally (a weighted Bonferroni correction):
the file-name candidates alone, then every candidate. A tier's match counts only when the chance
that a random normalised rate lands in any of its pairs' windows is below its share of ALPHA, and
only when every match in it implies the same sample rate (1200 Bd at 48 kS/s and 2400 Bd at
96 kS/s look identical, and stay UNKNOWN).

Limits: the device rates are the commonly offered settings, not every rate a device supports.
The file-name schemes are recorder conventions, so file-name values are candidates, not facts.
At the clock tolerance the 39 device rates against the 16 symbol rates cover about 0.6 % of the
normalised-rate range, and the rates form ladders (9600 Bd at 2.4 MS/s is 4800 Bd at 1.2 MS/s),
so a device-rate match is often ambiguous and stays UNKNOWN; a file-name hint is tested on its
own first, where a match is rarely a coincidence. Centre-frequency hints come only from file
names.
"""

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from dsp.evidence import Alternative, EvidenceLevel, Parameter, revise
from dsp.ingest.assumptions import FREQUENCY_HINT, RATE_HINT

# Family-wise false-match rate for promoting a candidate, shared between the tiers.
ALPHA = 0.01
# Structural-match tolerance: never wider than the plan's 0.1 %, and at least the combined clock
# error of transmitter and receiver (an uncorrected RTL-SDR crystal can be tens of ppm off).
MAX_TOLERANCE = 1e-3
CLOCK_TOLERANCE = 1e-4
# The normalised symbol rates a random signal could have, for the chance of a coincidence:
# from 10^6 samples per symbol up to one.
MIN_NORMALISED_RATE = 1e-6
# How many candidates a Parameter lists as alternatives; the evidence states the full count.
MAX_ALTERNATIVES = 8

HintKind = Literal["sample_rate", "center_frequency"]


@dataclass(frozen=True)
class Hint:
    kind: HintKind
    value: float
    text: str  # the part of the name it came from
    source: str  # which scheme matched


@dataclass(frozen=True)
class DeviceRates:
    device: str
    datatypes: tuple[str, ...]  # what its usual recorder writes
    rates: tuple[float, ...]  # S/s


DEVICE_RATES: tuple[DeviceRates, ...] = (
    DeviceRates(
        "RTL-SDR (rtl_sdr)",
        ("cu8",),
        (250e3, 1.024e6, 1.2e6, 1.4e6, 1.8e6, 1.92e6, 2.048e6, 2.4e6, 2.56e6, 2.88e6, 3.2e6),
    ),
    DeviceRates(
        "HackRF (hackrf_transfer)",
        ("ci8",),
        (
            1.75e6,
            2e6,
            2.5e6,
            3.5e6,
            4e6,
            5e6,
            5.5e6,
            6e6,
            7e6,
            8e6,
            9e6,
            10e6,
            12e6,
            14e6,
            15e6,
            16e6,
            20e6,
        ),
    ),
    DeviceRates("Airspy (airspy_rx)", ("ci16_le", "cf32_le"), (2.5e6, 3e6, 6e6, 10e6)),
    DeviceRates(
        "USRP / PlutoSDR", ("ci16_le", "cf32_le"), (1e6, 2e6, 5e6, 10e6, 20e6, 30.72e6, 61.44e6)
    ),
    DeviceRates("LTE-related", (), (1.92e6, 3.84e6, 7.68e6, 15.36e6, 30.72e6)),
    DeviceRates(
        "sound-card I/Q (SDR#, HDSDR)",
        ("ri16_le", "ci16_le", "ri24_le", "ci24_le", "rf32_le", "cf32_le"),
        (44.1e3, 48e3, 96e3, 192e3),
    ),
)


@dataclass(frozen=True)
class RateCandidate:
    value: float  # S/s
    reason: str
    from_name: bool


@dataclass(frozen=True)
class SymbolRate:
    value: float  # Bd
    name: str


# Symbol rates common enough to identify a sample rate by, each with its public source.
RECOGNISED_SYMBOL_RATES: tuple[SymbolRate, ...] = (
    SymbolRate(45.45, "RTTY 45.45 Bd (amateur ITA2)"),
    SymbolRate(50.0, "RTTY/telex 50 Bd"),
    SymbolRate(75.0, "75 Bd telegraphy"),
    SymbolRate(100.0, "NAVTEX / DSC 100 Bd (ITU-R M.540, M.493)"),
    SymbolRate(300.0, "300 Bd"),
    SymbolRate(512.0, "POCSAG 512 bit/s (ITU-R M.584)"),
    SymbolRate(600.0, "600 Bd"),
    SymbolRate(1187.5, "RDS 1187.5 bit/s (IEC 62106)"),
    SymbolRate(1200.0, "1200 Bd (POCSAG, AFSK packet)"),
    SymbolRate(2400.0, "2400 Bd (POCSAG, ACARS)"),
    SymbolRate(4800.0, "4800 Bd (DMR, P25)"),
    SymbolRate(9600.0, "9600 Bd (AIS, ITU-R M.1371)"),
    SymbolRate(18000.0, "TETRA 18 kBd (ETSI EN 300 392-2)"),
    SymbolRate(19200.0, "19200 Bd"),
    SymbolRate(72000.0, "Meteor-M LRPT 72 kBd"),
    SymbolRate(1625e3 / 6, "GSM 270.833 kBd (3GPP TS 45.004)"),
)

_SCALE = {"": 1.0, "k": 1e3, "m": 1e6, "g": 1e9}
_NUMBER = r"(?P<num>\d+(?:\.\d+)?)(?P<scale>[kmg]?)"
_RATE_TAG = re.compile(
    r"(?<![a-z])(?:fs|sr|srate|samp_?rate|sample_?rate|rate)[=_\-]?"
    + _NUMBER
    + r"(?:s?ps|s/s|hz)?(?![a-z0-9])"
)
_FREQ_TAG = re.compile(
    r"(?<![a-z])(?:fc|cf|freq|f0|center|centre)[=_\-]?" + _NUMBER + r"(?:hz)?(?![a-z0-9])"
)
_RATE_UNIT = re.compile(r"(?<![a-z0-9.])" + _NUMBER + r"(?:sps|s/s)(?![a-z])")
_HZ = re.compile(r"(?<![a-z0-9.])" + _NUMBER + r"hz(?![a-z])")
_GQRX = re.compile(r"^gqrx_\d{8}_\d{6}_(?P<freq>\d+)_(?P<rate>\d+)_fc$")

_RANGES: dict[HintKind, tuple[float, float]] = {
    "sample_rate": (1e3, 1e10),
    "center_frequency": (1e3, 3e11),
}


def filename_hints(name: str) -> tuple[Hint, ...]:
    """Sample-rate and centre-frequency hints in a file name, strongest scheme first."""
    stem = name.lower().rsplit(".", 1)[0]
    hints: list[Hint] = []

    def add(kind: HintKind, value: float, text: str, source: str) -> None:
        low, high = _RANGES[kind]
        if low <= value <= high and all(h.kind != kind or h.value != value for h in hints):
            hints.append(Hint(kind, value, text, source))

    if gqrx := _GQRX.match(stem):
        add("center_frequency", float(gqrx["freq"]), gqrx["freq"], "gqrx file name")
        add("sample_rate", float(gqrx["rate"]), gqrx["rate"], "gqrx file name")
    patterns: tuple[tuple[re.Pattern[str], HintKind, str], ...] = (
        (_RATE_TAG, "sample_rate", "sample-rate tag in the file name"),
        (_FREQ_TAG, "center_frequency", "centre-frequency tag in the file name"),
        (_RATE_UNIT, "sample_rate", "number with a sample-rate unit in the file name"),
        (_HZ, "center_frequency", "number in Hz in the file name (SDR#, HDSDR)"),
    )
    for pattern, kind, source in patterns:
        for m in pattern.finditer(stem):
            add(kind, float(m["num"]) * _SCALE[m["scale"]], m.group(0), source)
    return tuple(hints)


def rate_candidates(name: str, datatype: str | None) -> tuple[RateCandidate, ...]:
    """Ranked candidates: file-name hints, then device rates, matching recorders first."""
    out = [
        RateCandidate(h.value, f"{h.source}: {h.text!r}", True)
        for h in filename_hints(name)
        if h.kind == "sample_rate"
    ]
    for family in sorted(DEVICE_RATES, key=lambda d: datatype not in d.datatypes):
        native = f", whose recorder writes {datatype}" if datatype in family.datatypes else ""
        for rate in family.rates:
            if all(c.value != rate for c in out):
                out.append(RateCandidate(rate, f"standard {family.device} rate{native}", False))
    return tuple(out)


def sample_rate_parameter(
    candidates: Sequence[RateCandidate], datatype: str | None, method: str, reason: str
) -> Parameter:
    """UNKNOWN sample rate with the ranked candidates as alternatives; `reason` says why."""
    named = [c for c in candidates if c.from_name]
    order = f"; receivers whose recorder writes {datatype} are ranked first" if datatype else ""
    return Parameter(
        id="sample_rate",
        name="Sample rate",
        value=None,
        unit="S/s",
        level=EvidenceLevel.UNKNOWN,
        method=method,
        evidence=(
            reason,
            *(f"Candidate {_quantity(c.value, 'S/s')} from the {c.reason}." for c in named),
            f"{len(candidates) - len(named)} standard SDR device rates are also candidates{order}.",
            "No candidate is taken as fact: one becomes a hypothesis only when a recognised "
            "symbol rate matches it.",
        ),
        alternatives=tuple(Alternative(value=c.value) for c in candidates[:MAX_ALTERNATIVES]),
        resolve_hint=f"Choose one of the candidate rates or enter it. {RATE_HINT}",
    )


def center_frequency_parameter(name: str, method: str, reason: str) -> Parameter:
    """UNKNOWN centre frequency, with any file-name hints as alternatives."""
    hints = [h for h in filename_hints(name) if h.kind == "center_frequency"]
    return Parameter(
        id="center_frequency",
        name="Centre frequency",
        value=None,
        unit="Hz",
        level=EvidenceLevel.UNKNOWN,
        method=method,
        evidence=(
            reason,
            *(
                f"Candidate {_quantity(h.value, 'Hz')} from the {h.source}: {h.text!r}."
                for h in hints
            ),
        ),
        alternatives=tuple(Alternative(value=h.value) for h in hints),
        resolve_hint=f"Confirm the candidate or enter it. {FREQUENCY_HINT}"
        if hints
        else FREQUENCY_HINT,
    )


@dataclass(frozen=True)
class StructuralMatch:
    sample_rate: float
    symbol_rate: SymbolRate
    error: float  # relative: normalised rate x sample rate / symbol rate - 1


@dataclass(frozen=True)
class Tier:
    label: str
    hypotheses: int  # (candidate, symbol rate) pairs tried
    chance: float  # probability a log-uniform random normalised rate matches one of them
    alpha: float  # this tier's share of ALPHA
    matches: tuple[StructuralMatch, ...]
    tolerance: float

    @property
    def sample_rate(self) -> float | None:
        """The one sample rate every match implies, if significant; otherwise None."""
        rates = sorted({m.sample_rate for m in self.matches})
        if not rates or self.chance > self.alpha:
            return None
        if rates[-1] / rates[0] - 1 > 2 * self.tolerance:
            return None
        return rates[0]


@dataclass(frozen=True)
class StructuralTest:
    normalised_rate: float  # symbol rate / sample rate, measured
    tolerance: float  # relative
    tiers: tuple[Tier, ...]

    @property
    def hypotheses(self) -> int:
        return sum(t.hypotheses for t in self.tiers)

    @property
    def decided(self) -> Tier | None:
        return next((t for t in self.tiers if t.sample_rate is not None), None)


def structural_test(
    normalised_rate: float,
    relative_uncertainty: float,
    candidates: Sequence[RateCandidate],
    symbol_rates: Sequence[SymbolRate] = RECOGNISED_SYMBOL_RATES,
    searches: int = 1,
) -> StructuralTest:
    """Test (candidate sample rate, recognised symbol rate) pairs against a measured rate.

    `normalised_rate` is the estimated symbol rate in cycles per sample, `relative_uncertainty`
    its 1-sigma relative uncertainty. The tolerance is 3 sigma, at least the clock floor, and
    never wider than 0.1 %: a measurement too imprecise for that matches nothing. `searches` is
    how many measured rates (signals) the caller tests in all; each tier's share of ALPHA is
    divided by it, so testing several signals does not raise the chance of a coincidence.
    """
    if not MIN_NORMALISED_RATE <= normalised_rate <= 1:
        raise ValueError(f"normalised symbol rate outside [1e-6, 1]: {normalised_rate}")
    if relative_uncertainty < 0:
        raise ValueError("uncertainty must be non-negative")
    tolerance = max(3 * relative_uncertainty, CLOCK_TOLERANCE)
    groups = [("file-name candidates", [c.value for c in candidates if c.from_name])]
    groups.append(("all candidates", [c.value for c in candidates]))
    groups = [(label, rates) for label, rates in groups if rates]
    tiers: list[Tier] = []
    for label, rates in groups:
        pairs = tuple(
            (fs, rs)
            for fs in sorted(set(rates))
            for rs in symbol_rates
            if MIN_NORMALISED_RATE <= rs.value / fs <= 1
        )
        usable = tolerance <= MAX_TOLERANCE and pairs
        matches = tuple(
            StructuralMatch(fs, rs, normalised_rate * fs / rs.value - 1)
            for fs, rs in (pairs if usable else ())
            if abs(normalised_rate * fs / rs.value - 1) <= tolerance
        )
        chance = _chance(pairs, tolerance) if usable else 1.0
        tiers.append(
            Tier(label, len(pairs), chance, ALPHA / (len(groups) * searches), matches, tolerance)
        )
    return StructuralTest(normalised_rate, tolerance, tuple(tiers))


def structural_parameter(test: StructuralTest, unknown: Parameter) -> Parameter:
    """The sample rate after a structural test: HYPOTHESIS on a significant, unambiguous match."""
    lines: list[str] = []
    for tier in test.tiers:
        lines.append(
            f"{tier.label}: {tier.hypotheses} (sample rate, recognised symbol rate) pairs at "
            f"±{tier.tolerance:.2%}; a coincidence would match one with probability "
            f"{tier.chance:.2g} (threshold {tier.alpha:.2g})."
        )
        lines += [
            f"{m.symbol_rate.name} fits {_quantity(m.sample_rate, 'S/s')} ({m.error:+.4%})."
            for m in tier.matches
        ]
    head = f"Normalised symbol rate {test.normalised_rate:.8g} cycles/sample."
    tier = test.decided
    if tier is None:
        if test.tolerance > MAX_TOLERANCE:
            why = f"The symbol rate is too uncertain to match within {MAX_TOLERANCE:.1%}."
        elif not any(t.matches for t in test.tiers):
            why = "No structural match."
        elif all(t.chance > t.alpha for t in test.tiers if t.matches):
            why = "The matches could be coincidences, given how many pairs were tried."
        else:
            why = "The matches imply different sample rates, so none is preferred."
        return revise(unknown, evidence=(*unknown.evidence, head, *lines, why))
    rate = tier.sample_rate
    assert rate is not None
    return Parameter(
        id=unknown.id,
        name=unknown.name,
        value=rate,
        unit="S/s",
        level=EvidenceLevel.HYPOTHESIS,
        method="Structural match: a recognised symbol rate over the measured normalised rate",
        evidence=(head, *lines, f"Decided on the {tier.label}."),
        convention="The rate rests on a recognised symbol rate fitting the measured one, not on "
        "anything the file says; confirm it, or enter the rate the receiver used.",
        alternatives=tuple(a for a in unknown.alternatives if a.value != rate)[:MAX_ALTERNATIVES],
    )


@lru_cache(maxsize=64)
def _chance(pairs: tuple[tuple[float, SymbolRate], ...], tolerance: float) -> float:
    """Share of the log normalised-rate range that the pairs' match windows cover."""
    low, high = math.log(MIN_NORMALISED_RATE), 0.0
    half = math.log1p(tolerance)
    windows = sorted(
        (max(math.log(rs.value / fs) - half, low), min(math.log(rs.value / fs) + half, high))
        for fs, rs in pairs
    )
    covered, end = 0.0, low
    for lo, hi in windows:
        if hi > end:
            covered += hi - max(lo, end)
            end = hi
    return covered / (high - low)


def _quantity(value: float, unit: str) -> str:
    return f"{value:,.10g}\N{NO-BREAK SPACE}{unit}"
