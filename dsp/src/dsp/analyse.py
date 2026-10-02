"""Per-detection analysis (PLAN M3-M6): channelise, estimate, sync, demodulate, decode
and frame one detected signal, returning a `DetectionReport`.

The digital chain is a blind search over a small, fixed grid of hypotheses: modulation (ranked
by the fourth-order cumulant) x carrier rotation x inner code (none, conv K=7 r1/2 at both
bit alignments, its DVB-S punctured rates at every phase, or a rate-1/n convolutional code
found blind by `dsp.fec.convident`) x sync word x CRC. Every cell of the grid counts toward
`tried`, and a cell is accepted only when its CRC passes are significant at ALPHA / tried
(Bonferroni). An accepted cell promotes the modulation, rotation, code and framing to VERIFIED
with a `crc` proof; the accepted chain is also re-run on shuffled soft bits, which should never
pass.

The chain stops at the first stage that finds nothing, and says why; an analog (AM/FM) signal
skips the digital chain.
"""

import math
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, replace
from typing import Any, cast

import numpy as np

from dsp import _scipy, fsk
from dsp.analog import AnalogMeasurements, analog_detect, measure_analog
from dsp.blind_framing import (
    MAX_CANDIDATES,
    Z_MIN,
    BlindFrames,
    analyse_stream,
    structure_z,
)
from dsp.blind_interleaver import MAX_CANDIDATE_CELLS, BlindBlock, find_blocks
from dsp.channel import Channel, channelise
from dsp.deinterleave import (
    CATALOGUE,
    FORNEY_CATALOGUE,
    Block,
    Forney,
    Helical,
    Interleaver,
    deinterleave,
    deinterleave_forney,
)
from dsp.demod import (
    BITS_PER_SYMBOL,
    OFFSET_QPSK,
    OFFSET_QPSK_I_LATE,
    ORDERS,
    base_modulation,
    demap,
    rotate,
    rotations,
)
from dsp.detect import Detection, detection_parameters
from dsp.estimate.offset import OffsetRate, msk_symbol_rate, offset_symbol_rate
from dsp.estimate.params import (
    SymbolRate,
    cumulants,
    fsk_symbol_rates,
    rolloff_fit,
    snr_m2m4,
    snr_psd,
    symbol_rate,
)
from dsp.evidence import Alternative, EvidenceLevel, Parameter, Proof, promote
from dsp.eye import eye_diagram
from dsp.fec import rs
from dsp.fec.convident import (
    DEFAULT_MAX_CONSTRAINT,
    DEFAULT_MAX_N,
    MAX_INPUT_BITS,
    ConvIdentification,
    identify_convolutional,
)
from dsp.fec.puncture import PUNCTURES, depuncture
from dsp.fec.viterbi import K7_R12, ConvCode, decode, encode, syndrome_rates
from dsp.framing import (
    CRCS,
    SYNC_WORDS,
    Crc,
    DecodedFrame,
    FrameResult,
    SyncWord,
    binomial_tail,
    find_frames,
)
from dsp.report import (
    MAX_CONSTELLATION_POINTS,
    DetectionReport,
    Frame,
    Hypothesis,
    HypothesisSearch,
    StageReport,
)
from dsp.scramble import DESCRAMBLERS, Descrambler
from dsp.spectrum import welch, welch_freqs
from dsp.sync import Carrier, Timing, correct_carrier, recover_timing
from dsp.systems.match import (
    MATCH_ALPHA,
    Accepted,
    Candidate,
    Findings,
    MatchResult,
    match,
    relayout,
)

ALPHA = 0.01
MAX_LEDGER_ROWS = 12
# Branches per FSK symbol-rate candidate: 2-FSK, and the 4 and 8 tone orders each with the
# spectrum as received and mirrored.
FSK_BRANCHES = 1 + 2 + 2
SHUFFLED_RUNS = 3
# Significant chains checked against shuffled bits, best first, before acceptance gives up.
MAX_SHUFFLE_CANDIDATES = 3
MIN_SYMBOLS = 512
# An offset-QPSK candidate's symbol rate over the detected bandwidth, which is R (1 + roll-off).
OFFSET_BAND = (0.4, 1.2)
MIN_ENVELOPE_VARIATION = 0.01  # std / mean of |x|² below which a symbol-rate line isn't real
WEAK_ENVELOPE_LINE = 50.0  # |x|² line ratio below which the line doesn't rule out FSK
CODES: tuple[ConvCode | None, ...] = (K7_R12, None)
# Modulations whose 180° branch is the 0° branch inverted bit for bit (Gray QPSK's two bits both
# flip), which the K=7 code's odd-weight generators and the inverted sync word already cover.
INVERTING = ("BPSK", "QPSK")
# Interleavers (dsp.deinterleave.CATALOGUE: block, helical, 802.11, QPP; FORNEY_CATALOGUE:
# convolutional) are tried after the convolutional code; alignment by the code's parity
# syndrome, which sits near 0.5 when misaligned.
SYNDROME_SCREEN = 0.25
SCREEN_BITS = 2048  # at least this many coded bits per alignment tried
SCREEN_CHUNK = 256  # alignments screened per batch
# Every alignment is first screened on this many coded bits (both ends of the first block), and
# only the lowest COARSE_KEEP go on to the full SCREEN_BITS: a code's parity syndrome is far below
# chance even on a short stretch, so the right alignment survives (30 of the 30 catalogue cases a
# full screen finds at 3 % hard-decision errors, 27 with 8 kept and 512 bits) while most of the
# work is saved.
COARSE_BITS = 768
COARSE_KEEP = 32
# A punctured cell goes on to frame search only when re-encoding its Viterbi output matches the
# bits it actually received at least this well (a wrong pattern or phase matches barely more than
# chance; a right one matches all but the raw bit errors).
REENCODE_SCREEN = 0.25
REENCODE_SCREEN_STEPS = 2000  # the screen looks at this many code blocks, not the whole stream
# The blind convolutional-code search needs this many soft bits to have windows enough to test.
MIN_BLIND_BITS = 3000
# One data-chosen code per branch enters the grid; the search's own ledger corrects for how it
# was chosen (`identify_convolutional`).
BLIND_CELLS = 1

E = EvidenceLevel


def analyse(
    source: Any, detection: Detection, *, sample_rate: float | None = None
) -> DetectionReport:
    """Analyse one detection. `source` is an open reader (`read(start, count)`, `num_samples`);
    frequencies and times stay in cycles/sample and samples as in `dsp.detect`, and are also
    given in Hz and baud when `sample_rate` (the recording's stated rate) is known."""
    detect_stage = _stage(
        "detect",
        "Detect",
        "Band found by the detector",
        E.ESTIMATED,
        detection_parameters(detection),
    )
    channel = channelise(source, detection)
    x = channel.samples
    units = _Units(sample_rate, channel)

    # FM needs a near-constant envelope, which no pulse-shaped linear modulation has, so an FM
    # verdict stands on its own. AM is a varying envelope, which RRC ripple also gives, so an AM
    # verdict needs the absence of a symbol-rate line in |x|² as well.
    rate = symbol_rate(x)
    # A line in |x|^2 that is weak is noise (at high oversampling a noisy FSK signal shows one of
    # ratio ~20, where a linear modulation's is in the hundreds to thousands): it is no reason to
    # skip the FSK trial. The PSK path still uses `rate` if the trial decodes nothing.
    weak_line = rate is not None and rate.ratio < WEAK_ENVELOPE_LINE
    # Offset QPSK has no |x|^2 line, so the analog check below would read it as noise-like AM; its
    # own signature is a pair of lines in x^2, which two FSK tones also make (doubled). So it is
    # tried where AM would otherwise be the verdict, and otherwise only after the FSK trial: a
    # decode that verifies is proof either way, and one that fails stands unless FSK has a report.
    offset_trials: list[DetectionReport | None] = []

    def offset_report() -> DetectionReport | None:
        if not offset_trials:
            found = offset_symbol_rate(x) if rate is None or weak_line else None
            # The rate must fit the band that was detected: R is the band over (1 + roll-off),
            # so between about half of it and all of it. A spurious pair, or the half-rate alias
            # of a real one, does not.
            band = detection.bandwidth * channel.decimation
            usable = (
                found is not None
                and found.normalised_rate * len(x) >= MIN_SYMBOLS
                and OFFSET_BAND[0] <= found.normalised_rate / band <= OFFSET_BAND[1]
            )
            offset_trials.append(
                _offset_report(detect_stage, detection, units, x, found)
                if found is not None and usable
                else None
            )
        return offset_trials[0]

    analog = _analog(x, channel, detection)
    if analog is not None and analog[0] == "fm":
        # Noisy tones (M-FSK at moderate SNR) pull the frequency kurtosis toward FM's, so a
        # tone-transition comb gets its chance: a CRC-verified FSK decode outranks the rule.
        candidates = _fsk_candidates(x)
        tried = _fsk_report(detect_stage, detection, units, x, candidates)
        if tried is not None and tried.level is E.VERIFIED:
            return tried
    if analog is not None and analog[0] == "am" and rate is None:
        offered = offset_report()
        if offered is not None:
            return offered
    if analog is not None and (analog[0] == "fm" or rate is None):
        kind, param, measured = analog
        return DetectionReport(
            label=kind.upper(),
            kind="analog",
            level=E.ESTIMATED,
            headline=f"Analog {kind.upper()}: not sent to the digital chain",
            stages=(
                detect_stage,
                _analog_estimate(units, detection, kind, measured),
                _stage("classify", "Classify", f"Analog {kind.upper()}", E.ESTIMATED, (param,)),
            ),
            search=None,
            no_search_reason="An analog signal carries no bits, so no code or framing search ran.",
            no_frames_reason="An analog signal carries no bits.",
        )

    if rate is None or weak_line or _frequency_kurtosis(x, channel, detection) < FSK_KURTOSIS:
        # Constant envelope and not analog, or discrete tones (a bimodal instantaneous
        # frequency; PSK's is spiky, well above 0) even where the channel filter has trimmed
        # the tones' skirts into envelope ripple: try 2-FSK, whose rate is in the transitions.
        candidates = _fsk_candidates(x)
        if any(c.assumption for c in candidates):
            # The pair of lines behind an index-0.5 candidate is also what offset QPSK makes
            # (twice its symbol rate apart): that reading gets its decode first, and wins only
            # if a CRC proves it.
            proven = offset_report()
            if proven is not None and proven.level is E.VERIFIED:
                return proven
        report = _fsk_report(detect_stage, detection, units, x, candidates)
        if report is not None:
            return report

    offered = offset_report()
    if offered is not None:
        return offered
    if rate is None or rate.normalised_rate * len(x) < MIN_SYMBOLS:
        unknown = Parameter(
            id="symbol_rate",
            name="Symbol rate",
            value=None,
            level=E.UNKNOWN,
            method="|x|² spectral line (linear modulations); tone-transition comb (FSK)",
            evidence=(
                "No significant symbol-rate line in |x|² nor in the tone transitions: the "
                "signal is constant-envelope without FSK tone steps (rectangular-pulse PSK, CW) "
                "or too short/weak for either line to show."
                if rate is None
                else f"Only {rate.normalised_rate * len(x):.0f} symbols; {MIN_SYMBOLS} are needed.",
            ),
            resolve_hint="Entering the symbol rate, or a longer capture, would let the chain run.",
        )
        reason = "No symbol rate, so no symbols were recovered and nothing was decoded."
        return DetectionReport(
            label="Unknown",
            kind="unknown",
            level=E.ESTIMATED,
            headline="Detected; symbol rate unknown, not decoded",
            stages=(
                detect_stage,
                _stage("estimate", "Estimate", "Symbol rate unknown", E.UNKNOWN, (unknown,)),
            ),
            search=None,
            no_search_reason=reason,
            no_frames_reason=reason,
        )

    psd = welch(x, 1024)
    freqs = welch_freqs(len(x), 1024, False)
    rolloff = rolloff_fit(psd, freqs, rate.normalised_rate)
    timing = recover_timing(x, rate.normalised_rate, rolloff)
    ranked = _rank_modulations(timing.symbols)
    carriers: dict[str, Carrier] = {}
    search = _search(
        _psk_branches(timing.symbols, ranked, carriers),
        sum(len(rotations(m)) for m, _ in ranked),
        carriers,
    )
    return _report(
        detect_stage,
        detection,
        units,
        rate.normalised_rate,
        rate.uncertainty,
        rolloff,
        timing,
        ranked,
        search,
        x,
    )


def _analog_estimate(
    units: "_Units", detection: Detection, kind: str, m: AnalogMeasurements
) -> StageReport:
    """The carrier, bandwidth and message measurements of an analog signal as a stage. Each
    uncertainty is a statistical one from the sample count; the depth and deviation are RMS
    figures (a peak would need the message's crest factor, which is not known)."""
    to_input = 1.0 / units.channel.decimation
    carrier_value, carrier_unit, carrier_scale = units.frequency(
        units.channel.centre + m.carrier_offset * to_input
    )
    bw_value, bw_unit, bw_scale = units.frequency(detection.bandwidth)
    root_n = math.sqrt(max(m.message_samples, 1))
    params = [
        Parameter(
            id="carrier",
            name="Carrier frequency",
            value=carrier_value,
            unit=carrier_unit,
            uncertainty=(0.5 / detection.nfft + 1.0 / root_n * 1e-3) * carrier_scale,
            level=E.ESTIMATED,
            method="Detection centre plus the power-weighted mean frequency (lag-one phase)",
            evidence=("Relative to the capture centre.",),
        ),
        Parameter(
            id="bandwidth",
            name="Occupied bandwidth",
            value=bw_value,
            unit=bw_unit,
            uncertainty=bw_scale / detection.nfft,
            level=E.ESTIMATED,
            method="Detection band edges (dsp.detect)",
        ),
    ]
    if m.am_depth_rms is not None:
        params.append(
            Parameter(
                id="am_depth",
                name="AM modulation depth (RMS)",
                value=round(m.am_depth_rms, 4),
                uncertainty=round(max(0.02 * m.am_depth_rms, 1.0 / root_n), 4),
                level=E.ESTIMATED,
                method="Envelope coefficient of variation less the AWGN floor's, in quadrature: "
                "RMS message amplitude over carrier amplitude",
                evidence=("A peak depth would need the message's crest factor, which is unknown.",),
            )
        )
    if m.audio_bandwidth is not None:
        audio_value, audio_unit, audio_scale = units.frequency(m.audio_bandwidth * to_input)
        params.append(
            Parameter(
                id="audio_bandwidth",
                name="Audio bandwidth",
                value=audio_value,
                unit=audio_unit,
                uncertainty=0.1 * audio_value + audio_scale / 1024,
                level=E.ESTIMATED,
                method="99 % of the envelope's power above its noise floor",
            )
        )
    if m.fm_deviation_rms is not None:
        dev_value, dev_unit, dev_scale = units.frequency(m.fm_deviation_rms * to_input)
        params.append(
            Parameter(
                id="fm_deviation",
                name="FM deviation (RMS)",
                value=dev_value,
                unit=dev_unit,
                uncertainty=max(0.05 * dev_value, dev_scale / 1000),
                level=E.ESTIMATED,
                method="Instantaneous-frequency spread less the AWGN floor's, in quadrature",
                evidence=(
                    "A peak deviation would need the message's crest factor, which is unknown.",
                ),
            )
        )
    return _stage(
        "estimate",
        "Estimate",
        f"Analog {kind.upper()} carrier, bandwidth and message measurements",
        E.ESTIMATED,
        tuple(params),
    )


def _fsk_candidates(x: Any) -> list[SymbolRate]:
    """The symbol rates a 2-FSK trial should try: the tone-transition comb's, and, when the pair
    of lines in x² that MSK and GMSK make is not already explained by one of them, that pair's
    spacing (an index-0.5 hypothesis, stated on the candidate). The comb needs sharp
    transitions, which GMSK's Gaussian filter takes away; the pair does not need them. A pair
    whose spacing is a candidate's rate (index 0.5) or twice it (index 1) is that candidate."""
    comb = [r for r in fsk_symbol_rates(x) if r.normalised_rate * len(x) >= MIN_SYMBOLS]
    msk = msk_symbol_rate(x)
    if msk is None or msk.normalised_rate * len(x) < MIN_SYMBOLS:
        return comb
    for r in comb:
        for factor in (1.0, 0.5):  # the pair's spacing is R (index 0.5) or 2 R (index 1)
            if abs(msk.normalised_rate * factor / r.normalised_rate - 1) < 0.03:
                return comb
    return [*comb, msk]


def _offset_report(
    detect_stage: StageReport,
    detection: Detection,
    units: "_Units",
    x: Any,
    offset: OffsetRate,
) -> DetectionReport:
    """The chain on an offset-QPSK signal: timing from x², I read at the instant and Q half a
    symbol later, then the QPSK demapper and the same search as any other linear modulation."""
    psd = welch(x, 1024)
    freqs = welch_freqs(len(x), 1024, False)
    rolloff = rolloff_fit(psd, freqs, offset.normalised_rate)
    timing = recover_timing(x, offset.normalised_rate, rolloff, offset=True, cfo=offset.cfo)
    # Which of I and Q is the delayed stream is the quarter turn the carrier phase leaves open: the
    # two pairings are two modulations in the search, one of which is the transmitted one.
    ranked = ((OFFSET_QPSK, 0.5), (OFFSET_QPSK_I_LATE, 0.5))
    symbols = {OFFSET_QPSK: timing.symbols, OFFSET_QPSK_I_LATE: timing.alternate}
    carriers: dict[str, Carrier] = {}
    search = _search(
        _psk_branches(symbols, ranked, carriers),
        sum(len(rotations(m)) for m, _ in ranked),
        carriers,
    )
    return _report(
        detect_stage,
        detection,
        units,
        offset.normalised_rate,
        offset.uncertainty,
        rolloff,
        timing,
        ranked,
        search,
        x,
        offset,
    )


def measure_symbol_rate(source: Any, detection: Detection) -> tuple[float, float] | None:
    """A linear signal's symbol rate in symbols per *input* sample, with its relative 1-sigma
    uncertainty: the |x|² line alone, with no decode chain and no sample rate. It is what a
    structural sample-rate test needs (`dsp.ingest.rate.structural_test`). None when there is no
    line, or too few symbols for one to be trusted; FSK's rate is not measured here."""
    channel = channelise(source, detection)
    rate = symbol_rate(channel.samples)
    if rate is None or rate.normalised_rate * len(channel.samples) < MIN_SYMBOLS:
        return None
    power = np.abs(channel.samples) ** 2
    if power.std() < MIN_ENVELOPE_VARIATION * power.mean():
        return None  # a constant envelope has no symbol-rate line; one found is rounding noise
    return rate.normalised_rate / channel.decimation, rate.uncertainty / rate.normalised_rate


# --- analog ---------------------------------------------------------------------------------


def _analog(
    x: Any, channel: Channel, detection: Detection
) -> tuple[str, Parameter, AnalogMeasurements] | None:
    try:
        noise = snr_psd(x).noise_density
    except ValueError:
        return None
    # Band-limit to the detected band first: the channel keeps guard bands of noise around the
    # signal, which would swamp the discriminator's frequency spread. Noise power after the
    # filter is the density times the filter's (two-sided) passband.
    cutoff = min(0.45, 0.6 * detection.bandwidth * channel.decimation)
    taps = _scipy.kaiser_taps(0.1 * cutoff + 0.01)
    # "valid" drops the filter's start-up and tail, and 2 % more at each end drops the burst's
    # own edges, which the detection box only brackets: a ramp there reads as envelope
    # variation and a frequency spike.
    x = np.convolve(x, _scipy.kaiser_lowpass(taps, cutoff), mode="valid")
    trim = len(x) // 50
    x = x[trim : len(x) - trim]
    if len(x) < 1024:
        return None
    result = analog_detect(x, noise * 2 * cutoff)
    if result is None:
        return None
    m = result.metrics
    evidence = (
        f"Envelope variation {m.envelope_cv:.3f} vs AWGN floor {m.envelope_floor:.3f}",
        f"Frequency spread {m.frequency_std:.4f} vs floor {m.frequency_floor:.4f} cycles/sample",
        f"Frequency excess kurtosis {m.frequency_kurtosis:.2f} (FSK tones sit below -0.75)",
    )
    return (
        result.kind,
        Parameter(
            id="modulation",
            name="Modulation",
            value=f"Analog {result.kind.upper()}",
            level=E.ESTIMATED,
            method="Envelope and instantaneous-frequency spread vs their AWGN floors (dsp.analog)",
            evidence=evidence,
        ),
        measure_analog(x, result),
    )


FSK_KURTOSIS = (
    -0.75
)  # excess kurtosis of the instantaneous frequency below which tones are discrete


def _frequency_kurtosis(x: Any, channel: Channel, detection: Detection) -> float:
    """Excess kurtosis of the instantaneous frequency inside the detected band: about -2 for
    two discrete tones, about 0 for FM, large and positive for PSK's phase-jump spikes."""
    cutoff = min(0.45, 0.6 * detection.bandwidth * channel.decimation)
    taps = _scipy.kaiser_taps(0.1 * cutoff + 0.01)
    y = np.convolve(x, _scipy.kaiser_lowpass(taps, cutoff), mode="valid")
    if len(y) < 1024:
        return 0.0
    return _scipy.excess_kurtosis(np.angle(y[1:] * np.conj(y[:-1])))


# --- symbols --------------------------------------------------------------------------------


# Theoretical (|C40|, -C42) of unit-power symbols; noise shrinks both toward 0.
CUMULANTS = {
    "BPSK": (2.0, 2.0),
    "QPSK": (1.0, 1.0),
    "8PSK": (0.0, 1.0),
    "16QAM": (0.68, 0.68),
    "64QAM": (0.619, 0.619),
}


def _features(symbols: Any) -> tuple[float, float]:
    """(|C40|, -C42) after a 4th-power carrier lock, so a residual offset can't spin C40 away
    (8PSK has no 4th-power line, and its C40 is 0 anyway)."""
    c = cumulants(correct_carrier(symbols, 4).symbols)
    return abs(c.c40), -c.c42


def _rank_modulations(symbols: Any) -> tuple[tuple[str, float], ...]:
    """The catalogue ranked by distance from each one's theoretical fourth-order cumulants."""
    c40, c42 = _features(symbols)
    scores = {
        m: 1.0 / (1.0 + math.hypot(c40 - t40, c42 - t42)) for m, (t40, t42) in CUMULANTS.items()
    }
    total = sum(scores.values())
    return tuple(sorted(((m, v / total) for m, v in scores.items()), key=lambda m: -m[1]))


Branch = tuple[str, int, Any]  # modulation, carrier rotation in degrees, soft bits


@dataclass(frozen=True)
class _Chain:
    modulation: str
    rotation: int
    code: ConvCode | None
    alignment: int
    frames: FrameResult | None
    llr: Any
    p_value: float | None
    interleaver: str | None = None  # e.g. "block 16x36 from bit 123"
    syndrome: float | None = None  # the code-syndrome screen's rate, for interleaver cells
    outer: rs.StreamDecode | None = None  # the outer RS code, when the frames come through one
    blind: ConvIdentification | None = None  # set when the code was found by the blind search
    bits: Any = None  # the decoded bits the frames were searched in
    descrambler: Descrambler | None = None
    blind_frames: BlindFrames | None = None  # set when sync and CRC were found blind
    threshold: float | None = None  # this chain's own acceptance threshold, when not the grid's
    blind_block: BlindBlock | None = None  # set when the block interleaver was found blind

    def significant(self, threshold: float) -> bool:
        limit = self.threshold if self.threshold is not None else threshold
        return self.p_value is not None and self.p_value < limit

    @property
    def candidate(self) -> str:
        code = f"{self.code.name}, alignment {self.alignment}" if self.code else "uncoded"
        if self.blind:
            code += " (blind search)"
        if self.blind_frames:
            code += " · blind framing"
        if self.descrambler:
            code += f" · {self.descrambler.name}"
        deinterleave = f" · {self.interleaver}" if self.interleaver else ""
        outer = f" · {RS_NAME}" if self.outer else ""
        # For FSK the branch index is 2 * the candidate symbol rate + (spectrum mirrored), not a
        # carrier rotation.
        where = (
            f"rate candidate {self.rotation // 2 + 1}" + (", mirrored" if self.rotation % 2 else "")
            if self.modulation.endswith("FSK")
            else f"at {self.rotation}°"
        )
        return f"{self.modulation} {where}{deinterleave} · {code}{outer}"


@dataclass
class _BlindStats:
    """How often the blind convolutional-code search ran and how often it named a code."""

    searched: int = 0
    identified: int = 0


@dataclass(frozen=True)
class _Search:
    chains: tuple[_Chain, ...]
    tried: int
    threshold: float
    accepted: _Chain | None
    carriers: dict[str, Carrier]
    shuffled_accepts: int  # over every chain checked, blocked ones included
    blind: _BlindStats
    blocked: tuple[_Chain, ...] = ()  # significant, but the same chain also passed on shuffled bits
    shuffled_checked: int = 0  # chains run on shuffled bits (up to MAX_SHUFFLE_CANDIDATES)
    branches: tuple[Branch, ...] = ()  # every branch the walk demodulated, for Match


def _symbols_of(symbols: Any, modulation: str) -> Any:
    """One modulation's symbols from what `_psk_branches` was given (an array, or a dict)."""
    if isinstance(symbols, dict):
        return cast("dict[str, Any]", symbols)[modulation]
    return symbols


def _psk_branches(
    symbols: Any, ranked: tuple[tuple[str, float], ...], carriers: dict[str, Carrier]
) -> Iterator[list[Branch]]:
    """Per ranked modulation, best first: each of its carrier rotations as soft bits. Lazy, so
    modulations after an accepted one are never demodulated; `carriers` records each lock.
    `symbols` is one array, or one per modulation (offset QPSK's two I/Q pairings)."""
    for modulation, _ in ranked:
        carrier = correct_carrier(
            _symbols_of(symbols, modulation), ORDERS[base_modulation(modulation)]
        )
        carriers[modulation] = carrier
        yield [
            (modulation, rotation, demap(rotate(carrier.symbols, rotation), modulation).llr)
            for rotation in rotations(modulation)
        ]


def _descrambled_cells(
    modulation: str,
    rotation: int,
    code: ConvCode | None,
    alignment: int,
    llr: Any,
    bits: Any,
    word: SyncWord,
    extra: dict[str, Any],
) -> list[_Chain]:
    """The same decoded bits through each catalogued descrambler: the additive ones restart per
    frame inside `find_frames`, the self-synchronising ones act on the whole stream first."""
    out: list[_Chain] = []
    for d in DESCRAMBLERS:
        stream = d.stream(bits) if d.kind == "self-sync" else bits
        frames = find_frames(stream, word, descrambler=d if d.kind == "additive" else None)
        out.append(
            _Chain(
                modulation,
                rotation,
                code,
                alignment,
                frames,
                llr,
                _p_value(frames),
                bits=stream,
                descrambler=d,
                **extra,
            )
        )
    return out


def _decode_cell(
    modulation: str,
    rotation: int,
    code: ConvCode | None,
    alignment: int,
    llr: Any,
    **extra: Any,
) -> list[_Chain]:
    bits = decode(llr, code) if code else (llr < 0).astype(np.uint8)
    chains: list[_Chain] = []
    for word in SYNC_WORDS:
        chains += _descrambled_cells(modulation, rotation, code, alignment, llr, bits, word, extra)
        frames = find_frames(bits, word)
        chains.append(
            _Chain(
                modulation,
                rotation,
                code,
                alignment,
                frames,
                llr,
                _p_value(frames),
                bits=bits,
                **extra,
            )
        )
    return chains


def _punctured_cells(branch: Branch) -> list[_Chain]:
    """The K=7 code at each DVB-S punctured rate and each phase the stream can start at. Only a
    cell whose Viterbi output re-encodes close to the received bits goes on to the frame search;
    the others are counted as tried."""
    modulation, rotation, soft = branch
    chains: list[_Chain] = []
    if base_modulation(modulation) in INVERTING and rotation >= 180:
        return chains  # the K=7 code's odd-weight generators make an inverted stream equivalent
    for puncture in PUNCTURES:
        code = puncture.code()
        for phase in range(puncture.kept):
            llr = depuncture(soft, puncture, phase)
            if _reencode_mismatch(llr, code) >= REENCODE_SCREEN:
                chains.append(_Chain(modulation, rotation, code, phase, None, llr, None))
                continue
            chains += _decode_cell(modulation, rotation, code, phase, llr)
    return chains


def _reencode_mismatch(llr: Any, code: ConvCode) -> float:
    """Fraction of the received (non-erased) bits that the re-encoded Viterbi output disagrees
    with: about the raw bit error rate for the right code, well above it otherwise."""
    steps = min(len(llr) // code.n, REENCODE_SCREEN_STEPS)
    if steps <= code.constraint:
        return 0.5
    llr = np.asarray(llr, np.float64)[: steps * code.n]
    seen = llr != 0
    reencoded = encode(decode(llr, code), code)
    return float(((reencoded != (llr < 0))[seen]).mean()) if seen.any() else 0.5


def _blind_conv_cells(branch: Branch, stats: _BlindStats) -> list[_Chain]:
    """The convolutional code found blind on this branch's soft bits, if the search finds one
    that the catalogue doesn't already try; decoded from the block boundary it found, with the
    polarity it found."""
    modulation, rotation, soft = branch
    if base_modulation(modulation) in INVERTING and rotation >= 180:
        return []  # only inverts every bit of the 0°/90° branch, which the search reads itself
    llr = np.asarray(soft, np.float64)
    if len(llr) < MIN_BLIND_BITS:
        return []
    stats.searched += 1
    found = identify_convolutional(llr).found
    if found is not None:
        stats.identified += 1
    if found is None or (found.code.constraint, found.code.generators) == (
        K7_R12.constraint,
        K7_R12.generators,
    ):
        return []
    aligned = -llr[found.offset :] if found.inverted else llr[found.offset :]
    aligned = aligned[: len(aligned) // found.n * found.n]
    return _decode_cell(modulation, rotation, found.code, found.offset, aligned, blind=found)


def _interleaver_cells(branch: Branch) -> list[_Chain]:
    """Each catalogued block interleaver, at the alignment where the code's parity syndrome is
    lowest; only an alignment that passes the syndrome screen goes on to Viterbi and framing."""
    return _block_cells(branch, [(entry, None) for entry in CATALOGUE])


def _blind_block_cells(branch: Branch) -> list[_Chain]:
    """Block interleavers the stream's own structure names (`dsp.blind_interleaver`), less those
    the catalogue already tried, each then aligned and decided like a catalogued one."""
    modulation, rotation, soft = branch
    if base_modulation(modulation) in INVERTING and rotation >= 180:
        return []  # as for the catalogue: only inverts every bit of the 0°/90° branch
    known = {(type(e), e.rows, e.cols) for e in CATALOGUE if isinstance(e, Block | Helical)}
    found = find_blocks((np.asarray(soft) < 0).astype(np.uint8))
    return _block_cells(
        branch,
        [(b.block, b) for b in found if (type(b.block), b.block.rows, b.block.cols) not in known],
    )


def _block_cells(
    branch: Branch, entries: Sequence[tuple[Interleaver, BlindBlock | None]]
) -> list[_Chain]:
    modulation, rotation, soft = branch
    chains: list[_Chain] = []
    if base_modulation(modulation) in INVERTING and rotation >= 180:
        # Only inverts every bit of the 0°/90° branch, which the code (odd-weight generators)
        # and the inverted-sync check already cover: counted as tried, not run again.
        return chains
    for entry, blind in entries:
        offset, phase, rate = _interleaver_offset(soft, entry)
        label = f"{entry.label}{' (found blind)' if blind else ''} from bit {offset}" + (
            f", code phase {phase}" if phase else ""
        )
        if rate >= SYNDROME_SCREEN:
            chains.append(
                _Chain(
                    modulation,
                    rotation,
                    K7_R12,
                    0,
                    None,
                    soft,
                    None,
                    label,
                    rate,
                    blind_block=blind,
                )
            )
            continue
        llr = deinterleave(soft, entry, offset)[phase:]
        chains += _decode_cell(
            modulation,
            rotation,
            K7_R12,
            0,
            llr,
            interleaver=label,
            syndrome=rate,
            blind_block=blind,
        )
    return chains


def _forney_cells(branch: Branch) -> list[_Chain]:
    """Each convolutional (Forney) interleaver in front of the K=7 code, at the lane phase and
    code phase where the parity syndrome is lowest; only one that passes the screen goes on to
    Viterbi and framing."""
    modulation, rotation, soft = branch
    chains: list[_Chain] = []
    if base_modulation(modulation) in INVERTING and rotation >= 180:
        return chains  # counted as tried, as for the block interleavers
    llr = np.asarray(soft, np.float64)
    for entry in FORNEY_CATALOGUE:
        phase, offset, rate = _forney_alignment(llr, entry)
        label = f"{entry.label} from bit {phase}" + (f", code phase {offset}" if offset else "")
        if rate >= SYNDROME_SCREEN:
            chains.append(_Chain(modulation, rotation, K7_R12, 0, None, llr, None, label, rate))
            continue
        stream = deinterleave_forney(llr, entry, phase)[entry.lag + offset :]
        chains += _decode_cell(
            modulation, rotation, K7_R12, 0, stream, interleaver=label, syndrome=rate
        )
    return chains


def _forney_alignment(soft: Any, entry: Forney) -> tuple[int, int, float]:
    """The lane phase and code phase with the lowest parity-syndrome rate, and that rate. Each
    candidate reads SCREEN_BITS bits from past the start-up lag, so the zeros the delay lines
    start with are never screened."""
    n = K7_R12.n
    need = entry.lag + entry.branches + n + SCREEN_BITS
    if len(soft) < need:
        return 0, 0, 0.5
    head = np.asarray(soft)[:need]
    rows = [
        (deinterleave_forney(head, entry, phase)[entry.lag + offset :][:SCREEN_BITS] < 0).astype(
            np.uint8
        )
        for phase in range(entry.branches)
        for offset in range(n)
    ]
    rates = syndrome_rates(np.array(rows))
    best = int(np.argmin(rates))
    return best // n, best % n, float(rates[best])


def _search(
    groups: Iterable[list[Branch]],
    branch_count: int,
    carriers: dict[str, Carrier],
    settled: Callable[[], bool] = lambda: False,
) -> _Search:
    """Every branch x (inner code x alignment, or block interleaver x alignment with the
    convolutional code) x sync word x CRC, Bonferroni-corrected over the whole grid
    (`branch_count` branches). The grid is walked cheapest first and stops at the first group
    with an accepted chain; the threshold covers the cells never reached, so it stays honest.
    Interleaver cells rejected by the syndrome screen count as tried. The shuffled-bit control
    runs after the walk, on the best significant chains: one it blocks is rejected, but the walk
    had already stopped at it, so cells beyond are not tried (lost recall, not a false accept).
    `settled` says a known system's own check has passed on a group, which ends the walk the same
    way an accepted chain does (the blind searches beyond would only re-decode what is proven)."""
    per_branch = (
        sum(2 if c else 1 for c in CODES)
        + sum(p.kept for p in PUNCTURES)
        + BLIND_CELLS
        + sum(e.size for e in CATALOGUE)
        + sum(e.branches * K7_R12.n for e in FORNEY_CATALOGUE)
        + MAX_CANDIDATE_CELLS  # block interleavers found blind: every alignment of every candidate
    )
    # Each cell also with the outer RS code at every bit alignment and codeword phase.
    scrambles = 1 + len(DESCRAMBLERS)  # as decoded, and through each descrambler
    tried = (
        branch_count
        * per_branch
        * len(SYNC_WORDS)
        * scrambles
        * len(CRCS)
        * (1 + rs.GRID_HYPOTHESES)
    )
    threshold = ALPHA / tried

    def accepted() -> bool:
        return any(c.significant(threshold) for c in chains)

    chains: list[_Chain] = []
    seen: list[list[Branch]] = []
    blind = _BlindStats()
    stopped = False  # the walk ended on an accepted chain
    for group in groups:
        seen.append(group)
        for modulation, rotation, soft in group:
            for code in CODES:
                for alignment in range(2 if code else 1):
                    chains += _decode_cell(modulation, rotation, code, alignment, soft[alignment:])
            chains += _punctured_cells((modulation, rotation, soft))
        if accepted():
            stopped = True
            break
    # `settled` turns true while the generator is resumed for the next group, and it then ends
    # the walk by running out, not by `break`: so it is tested here, not in the loop.
    if not stopped and not settled():
        # No catalogued code fits: look for a rate-1/n convolutional code blind, then for a
        # catalogued interleaver in front of the K=7 code.
        for group in seen:
            for branch in group:
                chains += _blind_conv_cells(branch, blind)
            if accepted():
                break
        if not accepted():
            for group in seen:
                for branch in group:
                    chains += _interleaver_cells(branch)
                    if not accepted():
                        chains += _forney_cells(branch)
                    if not accepted():
                        chains += _blind_block_cells(branch)
                if accepted():
                    break
    chains += _outer_cells(chains, threshold)
    if not accepted() and not settled():
        chains += _blind_frame_cells(chains, threshold)
    significant = sorted(
        (c for c in chains if c.significant(threshold)),
        key=lambda c: (c.p_value or 1.0, c.outer is None, _unnamed_blind_crc(c)),
    )
    # The shuffled-bit control gates acceptance: a chain that also passes on shuffled bits is a
    # false alarm of the search itself, so it is blocked and the next candidate is tried.
    best: _Chain | None = None
    blocked: list[_Chain] = []
    shuffled = checked = 0
    for candidate in significant[:MAX_SHUFFLE_CANDIDATES]:
        accepts = _shuffled_accepts(candidate, threshold)
        checked += 1
        shuffled += accepts
        if accepts == 0:
            best = candidate
            break
        blocked.append(candidate)
    return _Search(
        tuple(chains),
        tried,
        threshold,
        best,
        carriers,
        shuffled,
        blind,
        tuple(blocked),
        checked,
        tuple(b for g in seen for b in g),
    )


def _unnamed_blind_crc(chain: _Chain) -> bool:
    """A blind CRC fit that matches no catalogued CRC. Complementing the whole stream leaves a
    fit valid (only its constant changes), so of two otherwise tied polarities the one whose CRC
    is a catalogue entry is the transmitted one."""
    return bool(chain.blind_frames and chain.blind_frames.crc and not chain.blind_frames.crc.name)


def _p_value(frames: FrameResult | None) -> float | None:
    """Chance of this many CRC passes if the frames were random bits."""
    if frames is None or frames.complete == 0:
        return None
    width = frames.crc.width if frames.crc else 16
    return binomial_tail(frames.passes, frames.complete, 2.0**-width)


def _shuffled_accepts(chain: _Chain, threshold: float) -> int:
    rng = np.random.default_rng(26147)
    accepts = 0
    for _ in range(SHUFFLED_RUNS):
        llr = np.asarray(rng.permutation(chain.llr), np.float64)
        bits = decode(llr, chain.code) if chain.code else (llr < 0).astype(np.uint8)
        if chain.blind_frames:  # the blind framing must not fire on shuffled bits either
            again = analyse_stream(bits) if structure_z(bits) >= Z_MIN else None
            accepts += int(
                again is not None
                and again.sync.verified
                and again.crc is not None
                and again.crc.p_value < (chain.threshold or threshold)
            )
            continue
        if chain.outer:
            outer = rs.decode_stream(bits)
            if outer is None:
                continue
            bits = outer.bits
        d = chain.descrambler
        if d is not None and d.kind == "self-sync":
            bits = d.stream(bits)
        frames = find_frames(
            bits,
            chain.frames.word if chain.frames else SYNC_WORDS[0],
            descrambler=d if d is not None and d.kind == "additive" else None,
        )
        p = _p_value(frames)
        accepts += int(p is not None and p < threshold)
        if chain.blind:  # the gate that chose the code must not fire on shuffled bits either
            accepts += int(identify_convolutional(llr).found is not None)
        if chain.blind_block:  # nor the stride scan that named the interleaver
            accepts += int(bool(find_blocks((llr < 0).astype(np.uint8))))
    return accepts


def _interleaver_offset(soft: Any, entry: Interleaver) -> tuple[int, int, float]:
    """The block alignment with the lowest parity-syndrome rate, the code phase (0, or 1 to drop
    the first deinterleaved bit: only a block of odd size can start in the middle of a code
    pair), and that rate: every offset's first blocks (at least SCREEN_BITS bits) deinterleaved
    and screened, the COARSE_KEEP best of a first pass over both ends of the first block on the full
    length. A
    block longer than SCREEN_BITS is screened on its first SCREEN_BITS deinterleaved bits alone,
    which are a stretch of the code's own stream."""
    n = entry.size
    hard = (np.asarray(soft) < 0).astype(np.uint8)
    take = min(n, SCREEN_BITS)
    blocks = min(max(2, -(-SCREEN_BITS // n)) if n <= SCREEN_BITS else 1, len(hard) // n - 1)
    if blocks < 1:
        return 0, 0, 0.5
    inverse = np.argsort(entry.permutation())[:take]  # deinterleaved[i] = interleaved[inverse[i]]
    within = (np.arange(blocks)[:, None] * n + inverse[None, :]).ravel()
    phases = (0, 1) if n % 2 else (0,)
    candidates = np.arange(n)

    def screen(offsets: Any, read: Any) -> Any:
        rates = [_screen(hard, offsets, read[phase:]) for phase in phases]
        return np.min(rates, axis=0), np.argmin(rates, axis=0)

    # The coarse pass reads both ends of the first block, COARSE_BITS / 2 each (a short block: its
    # first COARSE_BITS, over several blocks). An alignment a few bits out only spoils the rows
    # at one end of each block, so a read from the start alone would leave it tied with the right
    # one; the join between the two halves costs every alignment the same few windows.
    half = COARSE_BITS // 2
    coarse = (
        np.concatenate([within[:half], within[take - half : take]]) if n >= 2 * half else within
    )
    if len(within) > 2 * COARSE_BITS and n > COARSE_KEEP:
        coarse_rates, _ = screen(candidates, coarse[:COARSE_BITS])
        candidates = candidates[np.argsort(coarse_rates)[:COARSE_KEEP]]
    rates, phase = screen(candidates, within)
    best = int(np.argmin(rates))
    return int(candidates[best]), int(phase[best]), float(rates[best])


def _screen(hard: Any, offsets: Any, within: Any) -> Any:
    """The parity-syndrome rate of `hard` read at `within` from each of `offsets`, in batches."""
    rates = np.empty(len(offsets))
    for start in range(0, len(offsets), SCREEN_CHUNK):
        chunk = offsets[start : start + SCREEN_CHUNK]
        rates[start : start + len(chunk)] = syndrome_rates(hard[chunk[:, None] + within[None, :]])
    return rates


# --- blind framing --------------------------------------------------------------------------

# Crc fits tried per analysed stream: 2 stream variants x candidate periods x (width x reflection)
BLIND_FRAME_TESTS = 2 * MAX_CANDIDATES * 16


def _blind_frame_cells(chains: list[_Chain], threshold: float) -> list[_Chain]:
    """Sync word, frame length and CRC found blind, on decoded streams that show frame structure.

    Every cell's decoded bits get the cheap autocorrelation screen; those above `Z_MIN` go
    through `dsp.blind_framing`. A cell is accepted on the CRC's held-out passes alone, at
    ALPHA over every stream analysed and every fit tried (a second, separate error budget from
    the catalogue grid's)."""
    analysed: list[tuple[_Chain, BlindFrames]] = []
    seen: set[int] = set()
    tested = 0
    for chain in chains:
        if chain.bits is None or chain.descrambler is not None or id(chain.bits) in seen:
            continue  # descrambled streams were framed already; the rest are searched once each
        seen.add(id(chain.bits))
        if structure_z(chain.bits) < Z_MIN:
            continue
        tested += 1  # every stream that passes the screen is tried, not only those that frame
        found = analyse_stream(chain.bits)
        if found is not None and found.sync.verified and found.crc is not None:
            analysed.append((chain, found))
    if not analysed:
        return []
    limit = ALPHA / max(1, tested * BLIND_FRAME_TESTS)
    out: list[_Chain] = []
    for chain, found in analysed:
        fit = found.crc
        assert fit is not None
        out.append(
            replace(
                chain,
                frames=_frames_from_blind(found),
                p_value=fit.p_value,
                blind_frames=found,
                threshold=limit,
            )
        )
    return out


def _frames_from_blind(found: BlindFrames) -> FrameResult:
    """The blind result in the shape the report already draws: the constant prefix as the sync
    word, the fitted CRC as a catalogue-style CRC."""
    sync, fit = found.sync, found.crc
    assert fit is not None
    width = len(sync.word)
    value = int("".join(map(str, sync.word.tolist())), 2)
    word = SyncWord("constant prefix (found blind)", value, width)
    xorout = int(f"{fit.constant:0{fit.width}b}"[::-1], 2) if fit.refout else fit.constant
    crc = Crc(
        fit.name or f"CRC-{fit.width} poly 0x{fit.poly:X}",
        fit.width,
        fit.poly,
        0,
        fit.refin,
        fit.refout,
        xorout,
    )
    decoded: list[DecodedFrame] = []
    # The header is the run of constant and counter fields the blind analysis found after the
    # prefix (its bytes are counted from the data's own alignment, back from the CRC).
    header_end = max(
        (f.start + f.width for f in found.fields if f.kind in ("constant", "counter")),
        default=width,
    )
    for i, row in enumerate(found.frames):
        body = row[width:]
        # Whole bytes counted back from the CRC field: a prefix that stops a few bits short of
        # the true data leaves its constant tail at the front, which is not payload.
        data = body[: -fit.width]
        skip = len(data) % 8
        data = data[skip:]
        header = max(0, header_end - width - skip) // 8 * 8
        ok = fit.check(body)
        payload = np.packbits(data[header:]).tobytes()
        decoded.append(
            DecodedFrame(
                i + 1,
                sync.start + i * sync.period,
                sync.period,
                "pass" if ok else "fail",
                " ".join(f"{b:02X}" for b in np.packbits(data[:header]).tolist()),
                payload.hex().upper(),
                payload,
            )
        )
    passes = sum(f.crc == "pass" for f in decoded)
    return FrameResult(
        word,
        False,
        sync.hits,
        sync.period,
        sync.hits,
        crc,
        passes,
        len(decoded),
        tuple(decoded),
    )


# --- outer Reed-Solomon ---------------------------------------------------------------------

RS_NAME = "RS(255,223) CCSDS"


def _outer_cells(chains: list[_Chain], threshold: float) -> list[_Chain]:
    """The outer RS code on the most promising inner chain: the accepted one when some of its
    frames fail their CRC, else the one whose sync word recurs most."""
    framed = [c for c in chains if c.frames is not None]
    if not framed:
        return []
    ok = [c for c in framed if c.significant(threshold)]
    if ok:
        base = min(ok, key=lambda c: c.p_value or 1.0)
    else:
        base = max(framed, key=lambda c: c.frames.hits if c.frames else 0)
    f = base.frames
    if ok and f is not None and f.passes >= 0.9 * f.complete:
        return []
    bits = decode(base.llr, base.code) if base.code else (base.llr < 0).astype(np.uint8)
    outer = rs.decode_stream(bits)
    if outer is None:
        return []
    out: list[_Chain] = []
    for word in SYNC_WORDS:
        frames = find_frames(outer.bits, word)
        out.append(replace(base, frames=frames, p_value=_p_value(frames), outer=outer))
    return out


# --- report ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Units:
    sample_rate: float | None
    channel: Channel

    def rate(self, per_channel_sample: float) -> tuple[float, str, float]:
        """A rate in symbols per channel sample as (value, unit, scale to that unit)."""
        per_input = per_channel_sample / self.channel.decimation
        if self.sample_rate:
            return per_input * self.sample_rate, "Bd", self.sample_rate / self.channel.decimation
        return per_input, "symbols/sample", 1.0 / self.channel.decimation

    def frequency(self, cycles_per_input_sample: float) -> tuple[float, str, float]:
        if self.sample_rate:
            return cycles_per_input_sample * self.sample_rate, "Hz", self.sample_rate
        return cycles_per_input_sample, "cycles/sample", 1.0


def _early(chain: _Chain) -> bool:
    """An offset-QPSK chain on the pairing that reads the imaginary part half a symbol early."""
    return chain.modulation == OFFSET_QPSK_I_LATE


# Kurtosis E|s|^4 / E|s|^2^2 of each constellation, for the M2M4 estimator.
KURTOSIS = {"BPSK": 1.0, "QPSK": 1.0, "8PSK": 1.0, "16QAM": 1.32, "64QAM": 1.381}
# The Es/N0 range (dB) each estimator is trusted over, from the detection bench's scenes: the PSD
# moments need the symbol rate and read within 0.8 dB from 3 dB up, M2M4's scatter grows toward
# 0 dB and again above about 18 dB (a difference of nearly equal moments), and the EVM of the
# demapped constellation reads high below about 8 dB (decisions fall on the nearest point).
TRUST = {"PSD moments": (3.0, 40.0), "M2M4": (3.0, 18.0), "EVM": (8.0, 40.0)}


def _esn0_parameter(x: Any, timing: Timing, modulation: str, evm: float) -> Parameter:
    """Es/N0 from up to three estimators: the PSD's moments over the symbol rate (`snr_psd`),
    M2M4 on the recovered symbols (`snr_m2m4`) and the constellation's EVM. The value is the PSD
    reading when there is one (the most accurate over the whole range), else the EVM; the other
    readings are evidence, and the agreement of those inside their trusted range is the
    confidence (1 / (1 + spread in dB): a ranking of agreement, not a probability)."""
    readings: dict[str, float | None] = {"PSD moments": None, "M2M4": None, "EVM": None}
    try:
        est = snr_psd(x)
        readings["PSD moments"] = 10 * math.log10(
            est.signal_power / (est.noise_density * timing.rate)
        )
    except ValueError:
        pass
    readings["M2M4"] = snr_m2m4(timing.symbols, KURTOSIS.get(base_modulation(modulation), 1.0))
    readings["EVM"] = -20 * math.log10(max(evm, 1e-3))
    primary = readings["PSD moments"]
    method = "PSD moments over the symbol rate"
    if primary is None:
        primary, method = readings["EVM"], "EVM of the recovered constellation"
    assert primary is not None
    # Trust is judged on the primary reading, not each estimator's own: the EVM of a noisy
    # constellation reads high (decisions fall on the nearest point), so its own value says
    # nothing about whether it can be believed.
    counted = {
        name: v
        for name, v in readings.items()
        if v is not None and TRUST[name][0] <= primary <= TRUST[name][1]
    }
    spread = max(counted.values()) - min(counted.values()) if len(counted) > 1 else None
    lines: list[str] = []
    for name, v in readings.items():
        if v is None:
            lines.append(f"{name}: no result")
        elif name in counted:
            lines.append(f"{name}: {v:.1f} dB")
        else:
            lines.append(f"{name}: {v:.1f} dB (outside its trusted range, not in the agreement)")
    if spread is not None:
        lines.append(f"Trusted estimators agree to within {spread:.1f} dB.")
    return Parameter(
        id="esn0",
        name="Es/N0",
        value=round(primary, 1),
        unit="dB",
        # 0.2 dB scatter and a 0.1 dB bias for RRC pulses from 3 dB up on the detection bench; a
        # pulse without a fall-off (rectangular) reads up to 1.3 dB low, so the figure is 1 dB.
        uncertainty=1.0 if primary >= 3.0 and method.startswith("PSD") else 1.5,
        level=E.ESTIMATED,
        confidence=None if spread is None else round(1 / (1 + spread), 2),
        method=f"{method}; other estimators listed as evidence, their agreement as confidence",
        evidence=tuple(lines),
    )


def _shown(modulation: str) -> str:
    """The modulation as the reader sees it: both offset-QPSK pairings are `OFFSET_QPSK`."""
    return (
        OFFSET_QPSK
        if base_modulation(modulation) == "QPSK" and "OQPSK" in modulation
        else modulation
    )


def _stage(
    id: str, name: str, summary: str, level: EvidenceLevel | None, params: tuple[Parameter, ...]
) -> StageReport:
    return StageReport(
        id=id, name=name, status="done", summary=summary, level=level, parameters=params
    )


def _fmt_rate(value: float, unit: str) -> str:
    if unit == "Bd":
        return f"{value / 1000:.3g} kBd" if value >= 1000 else f"{value:.4g} Bd"
    return f"{value:.4g} {unit}"


def _report(
    detect_stage: StageReport,
    detection: Detection,
    units: _Units,
    rate: float,
    rate_uncertainty: float,
    rolloff: float,
    timing: Timing,
    ranked: tuple[tuple[str, float], ...],
    search: _Search,
    x: Any,
    offset: OffsetRate | None = None,
) -> DetectionReport:
    acc = search.accepted
    rate_value, rate_unit, rate_scale = units.rate(timing.rate)
    modulation = acc.modulation if acc else ranked[0][0]
    shown = _shown(modulation)  # the two offset-QPSK pairings are one modulation to the reader
    carrier = search.carriers[modulation]
    symbols = rotate(carrier.symbols, acc.rotation if acc else 0)
    soft = demap(symbols, modulation)
    esn0_param = _esn0_parameter(x, timing, modulation, soft.evm)
    esn0 = float(esn0_param.value or 0.0)
    # per input sample; offset QPSK also had `timing.cfo` (per channel sample) removed up front
    cfo_cycles = (carrier.cfo * timing.rate + timing.cfo) / units.channel.decimation
    carrier_value, carrier_unit, carrier_scale = units.frequency(units.channel.centre + cfo_cycles)

    estimate_params = (
        Parameter(
            id="symbol_rate",
            name="Symbol rate",
            value=rate_value,
            unit=rate_unit,
            uncertainty=max(rate_uncertainty, abs(timing.rate - rate)) * rate_scale,
            level=E.ESTIMATED,
            method=(
                "|x|² spectral line, refined by the timing loop's drift"
                if offset is None
                else "Pair of lines in x² at 2f ± Rs (offset QPSK has no |x|² line), "
                "refined by the timing loop's drift"
            ),
            evidence=(
                f"Timing drift followed: {timing.drift:+.3f} symbols over "
                f"{len(timing.symbols):,} symbols",
            )
            + (
                ()
                if offset is None
                else (f"The weaker x² line of the pair is {offset.ratio:.0f} times its level",)
            ),
        ),
        Parameter(
            id="rolloff",
            name="Roll-off",
            value=rolloff,
            uncertainty=0.05,
            level=E.ESTIMATED,
            method="Least-squares fit of the RRC PSD, snapped to a standard value",
        ),
        Parameter(
            id="carrier",
            name="Carrier frequency",
            value=carrier_value,
            unit=carrier_unit,
            uncertainty=(
                carrier.cfo_uncertainty * timing.rate / units.channel.decimation
                + 0.5 / detection.nfft
            )
            * carrier_scale,
            level=E.ESTIMATED,
            method=f"Detection centre plus the M-th power (M={carrier.order}) residual offset"
            if offset is None
            else "Detection centre plus the x² pair's offset and the 4th-power residual",
            evidence=("Relative to the capture centre.",),
        ),
        esn0_param,
    )
    estimate = _stage(
        "estimate",
        "Estimate",
        f"{_fmt_rate(rate_value, rate_unit)}, β {rolloff:g}, Es/N0 {esn0:.1f} dB",
        E.ESTIMATED,
        estimate_params,
    )

    proof = _proof(acc) if acc else None
    phase = Parameter(
        id="rotation",
        name="Phase ambiguity",
        value=f"{acc.rotation}°"
        + (", imaginary stream paired a symbol early" if _early(acc) else "")
        if acc
        else f"one of {', '.join(f'{r}°' for r in rotations(modulation))}",
        level=E.HYPOTHESIS,
        method=f"All {len(rotations(modulation))} rotations of the M-th power phase tried; "
        "the CRC decides",
    )
    timing_param = Parameter(
        id="timing",
        name="Timing recovery",
        value=round(timing.jitter, 4),
        unit="symbols RMS jitter",
        uncertainty=round(timing.jitter / 2, 4),
        level=E.ESTIMATED,
        method="RRC matched filter, Oerder-Meyr square-law timing per 256 symbols, unwrapped"
        if offset is None
        else "RRC matched filter, timing from the phase of the x² line per 256 symbols, unwrapped; "
        "Q read half a symbol after I",
    )
    sync_params = (timing_param, promote(phase, proof) if proof else phase)
    sync = _stage(
        "sync",
        "Sync",
        "Timing and carrier locked" if acc else "Timing recovered; phase unresolved",
        E.VERIFIED if acc else E.ESTIMATED,
        sync_params,
    )

    mod_param = Parameter(
        id="modulation",
        name="Modulation",
        value=shown,
        level=E.HYPOTHESIS,
        confidence=None if offset else round(dict(ranked)[modulation], 2),
        method=(
            "Nearest theoretical fourth-order cumulants (|C40|, -C42) on the carrier-locked "
            "symbols: BPSK (2, 2), QPSK (1, 1), 8PSK (0, 1), 16QAM (0.68, 0.68), 64QAM "
            "(0.62, 0.62); tried in rank order, the CRC decides"
            if offset is None
            else "No |x|² line but a balanced pair in x²: offset QPSK (I and Q half a symbol "
            "apart); its symbols are QPSK's once Q is brought back in line, so the CRC decides"
        ),
        evidence=("|C40| = {:.2f}, -C42 = {:.2f}".format(*_features(timing.symbols)),),
        alternatives=tuple(
            Alternative(value=m, confidence=round(c, 2)) for m, c in ranked if _shown(m) != shown
        ),
    )
    classify = _stage(
        "classify",
        "Classify",
        f"{shown}, confirmed by decode" if acc else f"{shown} (unconfirmed)",
        E.VERIFIED if acc else E.HYPOTHESIS,
        (promote(mod_param, proof) if proof else mod_param,),
    )

    evm_param = Parameter(
        id="evm",
        name="EVM",
        value=round(100 * soft.evm, 1),
        unit="% rms",
        uncertainty=round(100 * soft.evm / math.sqrt(max(len(symbols), 1)) * 2, 2),
        level=E.ESTIMATED,
        method=f"Error vector against the nearest ideal {base_modulation(modulation)} point",
    )
    n_bits = len(symbols) * BITS_PER_SYMBOL[base_modulation(modulation)]
    demod = _stage(
        "demod",
        "Demodulate",
        f"{n_bits:,} soft bits, EVM {100 * soft.evm:.0f} %",
        E.ESTIMATED,
        (evm_param,),
    )

    stages: list[StageReport] = [detect_stage, estimate, sync, classify, demod]
    decode_stages, frames = _decode_stages(
        search, proof, f"{'/'.join(m for m, _ in ranked)} x rotation"
    )
    stages += decode_stages
    findings = Findings(
        modulation=shown,
        symbol_rate=rate_value if rate_unit == "Bd" else None,
        rate_uncertainty=estimate_params[0].uncertainty if rate_unit == "Bd" else None,
    )
    matched = _run_match([Candidate(shown, findings, _hard_bits(soft.llr))], search, findings)
    stages.append(matched.stage)
    frames = frames or matched.frames
    if matched.verified:
        frames = relayout(frames, matched.verified)

    ledger = _ledger(search, matched)
    label = shown if acc else f"{shown}?"
    if acc and acc.frames:
        code_name = _code_label(acc)
        f = acc.frames
        headline = (
            f"{shown} {_fmt_rate(rate_value, rate_unit)} → {code_name} → {f.word.name} "
            f"frames, {f.passes}/{f.complete} CRC pass"
        )
    else:
        headline = f"{shown}? {_fmt_rate(rate_value, rate_unit)}, not decoded"
    headline = _with_system(headline, matched, bool(acc and acc.frames))
    points = symbols[:MAX_CONSTELLATION_POINTS]
    return DetectionReport(
        label=label,
        kind="psk",
        level=E.VERIFIED if frames and any(fr.crc == "pass" for fr in frames) else E.ESTIMATED,
        headline=headline,
        stages=tuple(stages),
        search=ledger,
        frames=frames,
        no_frames_reason=None
        if frames
        else "No sync word recurred with passing CRCs under any hypothesis, so no frame "
        "boundaries are claimed.",
        constellation=tuple((round(float(p.real), 4), round(float(p.imag), 4)) for p in points),
        eye=None if offset else eye_diagram(timing, symbols),
    )


def _fsk_rate_parameter(
    rate: SymbolRate, value: float, unit: str, scale: float, proof: Proof | None
) -> Parameter:
    """The FSK symbol rate: ESTIMATED from the tone-transition comb, or a HYPOTHESIS naming the
    index-0.5 convention when it came from the MSK line pair (promoted by a proof, which settles
    the convention on this recording)."""
    if rate.assumption is None:
        return Parameter(
            id="symbol_rate",
            name="Symbol rate",
            value=value,
            unit=unit,
            uncertainty=rate.uncertainty * scale,
            level=E.ESTIMATED,
            method="Tone-transition comb: lowest significant line in the discriminator's "
            "edge energy",
        )
    parameter = Parameter(
        id="symbol_rate",
        name="Symbol rate",
        value=value,
        unit=unit,
        uncertainty=rate.uncertainty * scale,
        level=E.HYPOTHESIS,
        method="Spacing of the pair of lines in x² (MSK and GMSK; no tone-transition comb "
        "survives a Gaussian filter)",
        convention=rate.assumption,
    )
    return promote(parameter, proof) if proof else parameter


def _fsk_report(
    detect_stage: StageReport,
    detection: Detection,
    units: _Units,
    x: Any,
    rates: list[SymbolRate],
) -> DetectionReport | None:
    """2-FSK at each candidate rate in turn (a rate is a hypothesis the CRC settles, like a
    carrier rotation); None if no candidate demodulates."""
    if not rates:
        return None
    demodulated: dict[int, tuple[SymbolRate, fsk.FskSymbols]] = {}
    settled = False  # a known system's own check passed on a candidate

    def groups() -> Iterator[list[Branch]]:
        nonlocal settled
        for i, r in enumerate(rates):
            try:
                demodulated[i] = (r, fsk.demodulate(x, r.normalised_rate))
            except ValueError:
                continue
            symbols = demodulated[i][1]
            name = f"{symbols.order}FSK"
            # The branch index is 2 * rate candidate + (spectrum mirrored). Mirroring a 2-FSK
            # spectrum inverts every bit, which the sync search reads itself; for more tones it
            # flips each label's first bit, so it is a branch of its own.
            branches: list[Branch] = [(name, 2 * i, symbols.llr)]
            if symbols.order > 2:
                branches.append((name, 2 * i + 1, fsk.mirror_first_bit(symbols.llr, symbols.order)))
            yield branches
            # Control is back here only when the walk found no accepted chain in this group. A
            # system whose own check passes on the raw bits ends the search: the blind stages
            # beyond could only re-decode what its proof already covers (the Match stage below
            # reruns the check with every candidate counted).
            # Alpha is split over every candidate that could still be checked, so this stop
            # rule is never looser than the final Holm correction over all of them.
            if match(
                [_fsk_candidate(i, r, symbols, units)], None, MATCH_ALPHA / len(rates)
            ).verified:
                settled = True
                return

    # Per rate: the tone count is chosen from the data, so every order's branches are counted.
    search = _search(groups(), len(rates) * FSK_BRANCHES, {}, lambda: settled)
    if not demodulated:
        return None
    acc = search.accepted
    candidates = [_fsk_candidate(i, r, s, units) for i, (r, s) in sorted(demodulated.items())]
    index = acc.rotation // 2 if acc else min(demodulated)
    own = next(c for c in candidates if c.key == index)
    matched = _run_match(candidates, search, own.findings)
    if not acc and matched.verified:
        index = matched.key  # the demodulation the system's check passed on
    rate, symbols = demodulated[index]
    name = f"{symbols.order}FSK"
    mirrored = bool(acc and acc.rotation % 2)
    proof = _proof(acc) if acc else matched.proof
    rate_value, rate_unit, rate_scale = units.rate(rate.normalised_rate)
    to_input = 1.0 / units.channel.decimation  # cycles/channel sample -> cycles/input sample
    shift_value, shift_unit, _ = units.frequency(symbols.shift * to_input)
    carrier_value, carrier_unit, carrier_scale = units.frequency(
        units.channel.centre + symbols.centre * to_input
    )
    estimate = _stage(
        "estimate",
        "Estimate",
        f"{_fmt_rate(rate_value, rate_unit)}, tones {shift_value:.4g} {shift_unit} apart",
        E.ESTIMATED,
        (
            _fsk_rate_parameter(rate, rate_value, rate_unit, rate_scale, proof),
            Parameter(
                id="tone_spacing",
                name="Tone spacing",
                value=shift_value,
                unit=shift_unit,
                uncertainty=0.05 * abs(shift_value),
                level=E.ESTIMATED,
                method="Medians of the discriminator's two frequency clusters"
                if symbols.order == 2
                else f"Equally spaced levels fitted to the {symbols.order} tones' frequencies",
            ),
            Parameter(
                id="carrier",
                name="Carrier frequency",
                value=carrier_value,
                unit=carrier_unit,
                uncertainty=0.5 / detection.nfft * carrier_scale,
                level=E.ESTIMATED,
                method="Detection centre plus the midpoint between the two tones",
                evidence=("Relative to the capture centre.",),
            ),
        ),
    )
    sync = _stage(
        "sync",
        "Sync",
        "Symbol timing from the tone transitions",
        E.ESTIMATED,
        (
            Parameter(
                id="timing",
                name="Timing recovery",
                value=round(symbols.jitter, 4),
                unit="symbols RMS jitter",
                uncertainty=round(symbols.jitter / 2, 4),
                level=E.ESTIMATED,
                method="Edge-energy spike folded per 256 symbols, line-fitted across the burst",
            ),
        ),
    )
    mod_param = Parameter(
        id="modulation",
        name="Modulation",
        value=name,
        level=E.HYPOTHESIS,
        method="Constant envelope with a tone-transition comb; discrete tones, so not analog FM. "
        "The tone count is the one whose equally spaced, equally likely levels fit the symbol "
        "frequencies best",
        evidence=(
            "Log-likelihood of the symbol frequencies by number of tones: "
            + ", ".join(f"{m} tones {ll:.0f}" for m, ll in symbols.fits),
        )
        if symbols.fits
        else (),
    )
    classify = _stage(
        "classify",
        "Classify",
        f"{name}, confirmed by decode" if proof else f"{name} (unconfirmed)",
        E.VERIFIED if proof else E.HYPOTHESIS,
        (promote(mod_param, proof) if proof else mod_param,),
    )
    inverted = bool(acc and acc.frames and acc.frames.inverted) or (not acc and matched.inverted)
    if symbols.order == 2:
        mapping_value = "upper tone = 0" if inverted else "lower tone = 0"
        mapping_method = (
            "Per-symbol tone energies over the symbol interior; the sync word's polarity "
            "decides which tone is 0"
        )
    else:
        mapping_value = (
            "Gray labels, highest tone = 0…0" if mirrored else "Gray labels, lowest tone = 0…0"
        )
        mapping_method = (
            "Per-symbol tone energies over the symbol interior; tone p carries the Gray label "
            "p ^ (p >> 1), read from the lowest tone up or, for a mirrored spectrum, from the "
            "highest down, which the CRC decides"
        )
    mapping = Parameter(
        id="bit_mapping",
        name="Bit mapping",
        value=mapping_value,
        level=E.HYPOTHESIS,
        method=mapping_method,
    )
    demod = _stage(
        "demod",
        "Demodulate",
        f"{len(symbols.llr):,} soft bits, non-coherent",
        E.ESTIMATED,
        (promote(mapping, proof) if proof else mapping,),
    )
    stages = [detect_stage, estimate, sync, classify, demod]
    decode_stages, frames = _decode_stages(search, proof, f"{name} x both polarities")
    stages += decode_stages
    stages.append(matched.stage)
    frames = frames or matched.frames
    if matched.verified:
        frames = relayout(frames, matched.verified)
    if acc and acc.frames:
        code_name = _code_label(acc)
        headline = (
            f"{name} {_fmt_rate(rate_value, rate_unit)} → {code_name} → {acc.frames.word.name} "
            f"frames, {acc.frames.passes}/{acc.frames.complete} CRC pass"
        )
    else:
        headline = f"{name}? {_fmt_rate(rate_value, rate_unit)}, not decoded"
    headline = _with_system(headline, matched, bool(acc and acc.frames))
    return DetectionReport(
        label=name if acc or matched.verified else f"{name}?",
        kind="fsk",
        level=E.VERIFIED if any(fr.crc == "pass" for fr in frames) else E.ESTIMATED,
        headline=headline,
        stages=tuple(stages),
        search=_ledger(search, matched),
        frames=frames,
        no_frames_reason=None
        if frames
        else "No sync word recurred with passing CRCs under any hypothesis, so no frame "
        "boundaries are claimed.",
    )


def _decode_stages(
    search: _Search, proof: Proof | None, grid: str
) -> tuple[list[StageReport], tuple[Frame, ...]]:
    """The FEC and frame stages, from the accepted chain or, failing one, why none was."""
    acc = search.accepted
    stages: list[StageReport] = []
    frames: tuple[Frame, ...] = ()
    if acc and acc.frames and proof:
        f = acc.frames
        code_value = acc.code.name if acc.code else "Uncoded"
        summary = _code_label(acc) if acc.code else "Uncoded"
        if acc.interleaver:
            param = Parameter(
                id="interleaver",
                name="Interleaver",
                value=acc.interleaver,
                level=E.HYPOTHESIS,
                method=(
                    "Block interleaver found blind (stride scan on the K=7 code's parity "
                    "syndrome, row length from the folded failures); alignment by the same "
                    "syndrome, decided by the CRC"
                    if acc.blind_block
                    else "Interleaver catalogue (block, helical, 802.11, QPP, convolutional); "
                    "alignment by the inner code's parity syndrome, decided by the CRC"
                ),
                evidence=(
                    *((acc.blind_block.evidence,) if acc.blind_block else ()),
                    f"Syndrome rate {acc.syndrome or 0:.3f} here (0.5 if wrong)",
                ),
            )
            stages.append(
                _stage(
                    "deinterleave",
                    "Deinterleave",
                    acc.interleaver,
                    E.VERIFIED,
                    (promote(param, proof),),
                )
            )
        code_params = [
            promote(
                Parameter(
                    id="code",
                    name="Code",
                    value=code_value,
                    level=E.HYPOTHESIS,
                    method=(
                        "Blind convolutional-code search (GF(2) rank scan and parity checks), "
                        "soft Viterbi, decided by the CRC"
                        if acc.blind
                        else "Catalogue search (soft Viterbi), decided by the CRC"
                    ),
                    evidence=_blind_evidence(acc.blind) if acc.blind else (),
                    warnings=_BLIND_WARNING if acc.blind else (),
                ),
                proof,
            )
        ]
        if acc.blind:
            code_params += _blind_parameters(acc.blind, proof)
        if acc.outer:
            o = acc.outer
            code_params.append(
                promote(
                    Parameter(
                        id="outer_code",
                        name="Outer code",
                        value=RS_NAME,
                        level=E.HYPOTHESIS,
                        method="Codeword grid from an error-free codeword (zero syndrome) over "
                        "every bit alignment and byte phase, then decoded (galois)",
                        evidence=(
                            f"{o.codewords} codewords from byte {o.phase} (bit alignment "
                            f"{o.alignment}): {o.corrected} bytes corrected, {o.failed} "
                            "uncorrectable",
                        ),
                    ),
                    proof,
                )
            )
            summary = f"{summary} + {RS_NAME}"
        stages.append(_stage("fec", "FEC", summary, E.VERIFIED, tuple(code_params)))
        frame_params = (
            promote(
                Parameter(
                    id="sync_word",
                    name="Sync word",
                    value=f.word.hex,
                    unit=f.word.name,
                    level=E.HYPOTHESIS,
                    method=(
                        "Blind discovery: the constant prefix of the frame (column constancy), "
                        "verified by its recurrence on held-out frames"
                        if acc.blind_frames
                        else "Known-sync catalogue correlation, ≤ 3 bit errors"
                    ),
                    evidence=_sync_evidence(acc, f),
                    warnings=_sync_warnings(acc),
                ),
                proof,
            ),
            promote(
                Parameter(
                    id="frame_length",
                    name="Frame length",
                    value=f.period,
                    unit="bits",
                    level=E.HYPOTHESIS,
                    method="Spacing of the recurring sync word",
                ),
                proof,
            ),
            promote(
                Parameter(
                    id="crc",
                    name="Frame check",
                    value=f.crc.name if f.crc else "?",
                    unit=f"{f.passes} / {f.complete} pass",
                    level=E.HYPOTHESIS,
                    method=(
                        "Blind CRC recovery: GCD of frame-pair XORs (Ewing), fitted on half "
                        "the frames and tested on the rest"
                        if acc.blind_frames
                        else "CRC catalogue over the bits between sync word and CRC field"
                    ),
                    evidence=_crc_evidence(acc),
                ),
                proof,
            ),
            *_header_parameters(acc),
            *_descrambler_parameters(acc, proof),
        )
        stages.append(
            _stage(
                "frame",
                "Frame",
                f"{f.word.name}, {f.passes}/{f.complete} CRC pass",
                E.VERIFIED,
                frame_params,
            )
        )
        frames = tuple(
            Frame(
                index=fr.index,
                start_bit=fr.start_bit,
                sync_word=f.word.hex,
                length_bits=fr.length_bits,
                crc=fr.crc,
                header_hex=fr.header_hex,
                payload_hex=fr.payload_hex,
            )  # type: ignore[arg-type]
            for fr in f.frames[:500]
        )
    else:
        reason = (
            f"None of the {search.tried} hypotheses ({grid} x uncoded, conv K=7 r½ or a blindly "
            f"identified rate-1/n code x {len(SYNC_WORDS)} sync word x {len(CRCS)} CRCs) gave "
            f"CRC passes significant at {search.threshold:.1e}."
            + (
                f" The blind convolutional search covers non-recursive, unpunctured rate-1/n "
                f"codes (n <= {DEFAULT_MAX_N}, K <= {DEFAULT_MAX_CONSTRAINT}) in the first "
                f"{MAX_INPUT_BITS:,} bits; it ran on {search.blind.searched} branches and named "
                f"a code on {search.blind.identified}."
                if search.blind.searched
                else ""
            )
        )
        stages.append(
            _stage(
                "fec",
                "FEC",
                "No catalogued code confirmed",
                E.UNKNOWN,
                (
                    Parameter(
                        id="code",
                        name="Code",
                        value=None,
                        level=E.UNKNOWN,
                        method="Catalogue and blind search: uncoded, conv K=7 r½, rate-1/n; "
                        "decided by sync word + CRC",
                        evidence=(reason,),
                        resolve_hint="Naming the transmitting standard, or adding its code and "
                        "framing to the catalogue, would settle it.",
                    ),
                ),
            )
        )
    return stages, frames


_PREFIX_WARNING = (
    "Column constancy finds the constant prefix of the frame: the sync word plus any constant "
    "header bytes after it, less a trailing run of one value.",
)


_POLARITY_WARNING = (
    "The frame check does not fix the stream's polarity (a complemented stream fits equally well, "
    "with a different constant), so the payload may be complemented relative to what was sent; "
    "a match with a catalogued CRC would settle it.",
)


def _sync_warnings(acc: _Chain) -> tuple[str, ...]:
    if not acc.blind_frames:
        return ()
    return _PREFIX_WARNING + (_POLARITY_WARNING if _unnamed_blind_crc(acc) else ())


def _sync_evidence(acc: _Chain, f: FrameResult) -> tuple[str, ...]:
    if acc.blind_frames:
        d = acc.blind_frames.sync
        return (
            f"{d.hits} of {d.heldout} held-out frames repeat it at a period of {d.period:,} bits "
            f"(p = {d.p_value:.1e} against a structureless stream, {d.candidates} candidate "
            f"period(s) tried)",
            "Stream variant: " + ("NRZ-I, differenced" if d.variant == "nrzi" else "as decoded"),
        )
    return (
        f"{f.hits} hits; recurs every {f.period:,} bits ({f.recurrences} consecutive pairs)"
        + (", inverted polarity" if f.inverted else ""),
    )


def _crc_evidence(acc: _Chain) -> tuple[str, ...]:
    if not (acc.blind_frames and acc.blind_frames.crc):
        return ()
    fit = acc.blind_frames.crc
    conventions = (
        f"input {'reflected' if fit.refin else 'as sent'}, "
        f"output {'reflected' if fit.refout else 'as is'}"
    )
    return (
        f"CRC-{fit.width}, generator 0x{fit.poly:X} ({conventions}); affine constant "
        f"0x{fit.constant:X} (initial value and final XOR combined at this frame length)",
        f"Fitted on {fit.fitted} frames; {fit.passes} of {fit.heldout} held-out frames pass "
        f"(p = {fit.p_value:.1e}, threshold {fit.threshold:.1e} over {fit.tried} fits)",
        f"Matches the catalogued {fit.name}"
        if fit.name
        else "No catalogued CRC has this exact initial value and final XOR",
    )


def _descrambler_parameters(acc: _Chain, proof: Proof) -> tuple[Parameter, ...]:
    """The descrambler the chain went through, promoted by the same CRC proof: with the wrong
    one the frame check would not pass."""
    d = acc.descrambler
    if d is None:
        return ()
    scheme = (
        "restarts at every frame, after the sync word"
        if d.kind == "additive"
        else "self-synchronising, applied to the whole stream"
    )
    return (
        promote(
            Parameter(
                id="descrambler",
                name="Descrambler",
                value=d.name,
                level=E.HYPOTHESIS,
                method="Descrambler catalogue (CCSDS additive, G3RUH self-synchronising), "
                "decided by the frame check",
                evidence=("1 + " + " + ".join(f"x^{t}" for t in d.taps) + f", {scheme}",),
            ),
            proof,
        ),
    )


def _header_parameters(acc: _Chain) -> tuple[Parameter, ...]:
    """The header fields the blind analysis read, as one HYPOTHESIS: each was tested on its own
    (the p-values are in the evidence), none is proven by the CRC."""
    if not acc.blind_frames:
        return ()
    parts: list[str] = []
    evidence: list[str] = []
    for fld in acc.blind_frames.fields:
        span = f"bits {fld.start}-{fld.start + fld.width - 1}"
        if fld.kind == "sync":
            parts.append(f"prefix {fld.width}")
        elif fld.kind == "constant":
            parts.append(f"constant {fld.width}")
            evidence.append(f"{span}: constant 0x{fld.value or 0:X} (p = {fld.p_value or 1:.1e})")
        elif fld.kind == "counter":
            parts.append(f"counter {fld.width} (+{fld.step})")
            evidence.append(f"{span}: counter, step {fld.step} (p = {fld.p_value or 1:.1e})")
        else:
            parts.append("payload")
    return (
        Parameter(
            id="header",
            name="Header fields",
            value=" · ".join(parts),
            level=E.HYPOTHESIS,
            method="Byte-aligned constant and counter tests after the constant prefix",
            evidence=tuple(evidence) or ("No constant or counter field after the prefix",),
        ),
    )


_BLIND_WARNING = (
    "These generators are one equivalent description of a code that decodes this stream: the "
    "branch order, a common delay and any factor shared by every branch cannot be told apart "
    "from the samples.",
)


def _code_label(chain: _Chain) -> str:
    """The code's name for headlines and summaries, saying when it was found blind."""
    if chain.code is None:
        return "uncoded"
    return f"{chain.code.name} (found blind)" if chain.blind else chain.code.name


def _blind_evidence(found: ConvIdentification) -> tuple[str, ...]:
    return (
        f"Rate 1/{found.n}, constraint length {found.code.constraint}, generators "
        f"{', '.join(f'{g:o}' for g in found.code.generators)} (octal), named with no catalogue "
        f"entry to start from, within the searched space: non-recursive, unpunctured rate-1/n, "
        f"n <= {DEFAULT_MAX_N}, K <= {DEFAULT_MAX_CONSTRAINT}, the first {MAX_INPUT_BITS:,} bits",
        f"The worst of the {found.n - 1} branch-pair parity checks holds on all but "
        f"{found.syndrome_weight} of {found.windows} windows (p = {found.p_value:.1e}, "
        f"threshold {found.threshold:.1e} = {found.alpha:g} / {found.tried} hypotheses)",
    )


def _blind_parameters(found: ConvIdentification, proof: Proof) -> list[Parameter]:
    """Where the blind search put the first code block, and which polarity it read, promoted by
    the same CRC proof as the code (a wrong alignment or polarity would not have decoded)."""
    alignment = Parameter(
        id="code_alignment",
        name="Code alignment",
        value=found.offset,
        unit="bits",
        level=E.HYPOTHESIS,
        method="Blind convolutional-code search: the block boundary its parity checks hold at",
        evidence=(f"Blocks of {found.n} bits start at bit {found.offset} of the soft stream",),
    )
    polarity = Parameter(
        id="stream_polarity",
        name="Stream polarity",
        value="inverted" if found.inverted else "upright",
        level=E.HYPOTHESIS,
        method="Blind convolutional-code search: the parity of its odd-weight checks",
        evidence=(
            ("Read from the parity of an odd-weight check on every window",)
            if found.polarity_determined
            else (
                "Every check has even weight, so a complemented stream fits equally well: "
                "upright is the default here, and only the CRC vouches for the decode",
            )
        ),
    )
    return [promote(alignment, proof), promote(polarity, proof)]


def _proof(chain: _Chain) -> Proof:
    f = chain.frames
    assert f is not None and f.crc is not None
    if chain.blind_frames and chain.blind_frames.crc:
        fit = chain.blind_frames.crc
        return Proof(
            kind="crc",
            detail=f"{f.crc.name}, fitted blind on {fit.fitted} frames, passes on {fit.passes} of "
            f"{fit.heldout} held-out frames ({chain.candidate})",
        )
    return Proof(
        kind="crc",
        detail=f"{f.crc.name} passes on {f.passes} of {f.complete} complete frames "
        f"({chain.candidate})",
    )


def _ledger(search: _Search, matched: MatchResult | None = None) -> HypothesisSearch:
    def row(c: _Chain) -> Hypothesis:
        f = c.frames
        ok = c is search.accepted
        if any(c is b for b in search.blocked):
            statistic = "Passes the corrected threshold"
            reason = "Blocked: the same chain also passes on shuffled bits, so it is a false alarm"
        elif c.interleaver and c.syndrome is not None and c.syndrome >= SYNDROME_SCREEN:
            statistic = f"Code syndrome {c.syndrome:.2f} at the best alignment (0.5 if absent)"
            reason = f"Syndrome not below {SYNDROME_SCREEN} at any alignment; not decoded"
        elif f is None:
            statistic, reason = "Sync word does not recur", "No frame boundaries"
        else:
            crc = f.crc.name if f.crc else "no catalogued CRC"
            statistic = f"{f.word.name} x{f.hits}, period {f.period}; {crc} {f.passes}/{f.complete}"
            reason = (
                "CRC passes significant after correction"
                if ok
                else ("CRC passes not significant" if f.passes else "No frame passes any CRC")
            )
            if c.blind_frames and c.blind_frames.crc:
                fit = c.blind_frames.crc
                statistic = (
                    f"Constant prefix {len(c.blind_frames.sync.word)} bits, period {f.period}; "
                    f"blind {crc} {fit.passes}/{fit.heldout} held-out"
                )
                reason = (
                    "Held-out CRC passes significant after correction"
                    if ok
                    else "Held-out CRC passes not significant after correction"
                )
        return Hypothesis(
            layer="Interleaver" if c.interleaver else ("FEC" if c.code else "Framing"),
            candidate=c.candidate,
            statistic=statistic,
            p_value=c.p_value,
            threshold=c.threshold if c.threshold is not None else search.threshold,
            outcome="accepted" if ok else "rejected",
            reason=reason,
        )

    ordered = sorted(
        search.chains,
        key=lambda c: (c is not search.accepted, c.p_value if c.p_value is not None else 2.0),
    )
    return HypothesisSearch(
        tried=search.tried,
        alpha=ALPHA,
        correction="Bonferroni",
        smallest_threshold=search.threshold,
        shuffled_runs=SHUFFLED_RUNS * search.shuffled_checked,
        shuffled_blocked=len(search.blocked),
        shuffled_accepts=search.shuffled_accepts,
        blind_searched=search.blind.searched,
        blind_identified=search.blind.identified,
        match_tried=matched.tried if matched else 0,
        rows=(
            *(row(c) for c in ordered[:MAX_LEDGER_ROWS]),
            *(matched.rows[:MAX_LEDGER_ROWS] if matched else ()),
        ),
    )


def _run_match(candidates: list[Candidate], search: _Search, findings: Findings) -> MatchResult:
    """The known-system catalogue against this signal: the blind findings and demodulated bits
    in, a `system` parameter and the ledger rows of every check out."""
    acc = search.accepted
    accepted = None
    if acc is not None and acc.frames is not None and acc.frames.crc is not None:
        accepted = Accepted(
            acc.frames,
            replace(
                findings,
                code=acc.code.name if acc.code else "Uncoded",
                interleaver=acc.interleaver,
                descrambler=acc.descrambler.name if acc.descrambler else None,
                outer=RS_NAME if acc.outer else None,
            ),
            acc.p_value if acc.p_value is not None else 1.0,
        )
    return match(candidates, accepted, MATCH_ALPHA)


def _hard_bits(llr: Any) -> Any:
    return (np.asarray(llr) < 0).astype(np.uint8)


def _fsk_candidate(
    index: int, rate: SymbolRate, symbols: fsk.FskSymbols, units: _Units
) -> Candidate:
    """One symbol-rate candidate's demodulation, for the Match stage."""
    value, unit, scale = units.rate(rate.normalised_rate)
    shift, shift_unit, _ = units.frequency(symbols.shift / units.channel.decimation)
    known = unit == "Bd"
    return Candidate(
        f"rate candidate {index + 1}",
        Findings(
            modulation=f"{symbols.order}FSK",
            symbol_rate=value if known else None,
            rate_uncertainty=rate.uncertainty * scale if known else None,
            tone_spacing=abs(shift) if shift_unit == "Hz" else None,
        ),
        _hard_bits(symbols.llr),
        key=index,
    )


def _with_system(headline: str, matched: MatchResult, chain_decoded: bool) -> str:
    """The headline with the verified known system named: beside a chain that decoded, or in
    place of "not decoded" when only the system's own check passed."""
    system = matched.verified
    if system is None:
        return headline
    if chain_decoded:
        return f"{headline} · {system.name}"
    good = sum(1 for f in matched.frames if f.crc == "pass")
    return (
        headline.replace("? ", " ", 1).replace(", not decoded", "")
        + f" → {system.name}: {good}/{len(matched.frames)} frames pass its check"
    )
