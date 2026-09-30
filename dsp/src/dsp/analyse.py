"""Per-detection analysis (PLAN M3-M6): channelise, estimate, sync, demodulate, decode
and frame one detected signal, returning a `DetectionReport`.

The digital chain is a blind search over a small, fixed grid of hypotheses: modulation (ranked
by the fourth-order cumulant) x carrier rotation x inner code (none, or conv K=7 r1/2 at both
bit alignments) x sync word x CRC. Every cell of the grid counts toward `tried`, and a cell is
accepted only when its CRC passes are significant at ALPHA / tried (Bonferroni). An accepted
cell promotes the modulation, rotation, code and framing to VERIFIED with a `crc` proof; the
accepted chain is also re-run on shuffled soft bits, which should never pass.

The chain stops at the first stage that finds nothing, and says why; an analog (AM/FM) signal
skips the digital chain.
"""

import math
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from dsp import _scipy, fsk
from dsp.analog import analog_detect
from dsp.channel import Channel, channelise
from dsp.deinterleave import CATALOGUE, Block, deinterleave
from dsp.demod import BITS_PER_SYMBOL, ORDERS, demap, rotate, rotations
from dsp.detect import Detection, detection_parameters
from dsp.estimate.params import (
    SymbolRate,
    cumulants,
    fsk_symbol_rates,
    rolloff_fit,
    snr_psd,
    symbol_rate,
)
from dsp.evidence import Alternative, EvidenceLevel, Parameter, Proof, promote
from dsp.fec import rs
from dsp.fec.viterbi import K7_R12, ConvCode, decode, syndrome_rates
from dsp.framing import CRCS, SYNC_WORDS, FrameResult, binomial_tail, find_frames
from dsp.report import (
    MAX_CONSTELLATION_POINTS,
    DetectionReport,
    Frame,
    Hypothesis,
    HypothesisSearch,
    StageReport,
)
from dsp.spectrum import welch, welch_freqs
from dsp.sync import Carrier, Timing, correct_carrier, recover_timing

ALPHA = 0.01
MAX_LEDGER_ROWS = 12
SHUFFLED_RUNS = 3
MIN_SYMBOLS = 512
CODES: tuple[ConvCode | None, ...] = (K7_R12, None)
# Block interleavers (dsp.deinterleave.CATALOGUE) are tried after the convolutional code;
# alignment by the code's parity syndrome, which sits near 0.5 when misaligned.
SYNDROME_SCREEN = 0.25
SCREEN_BITS = 2048  # at least this many coded bits per alignment tried
SCREEN_CHUNK = 256  # alignments screened per batch

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
    analog = _analog(x, channel, detection)
    if analog is not None and (analog[0] == "fm" or rate is None):
        kind, param = analog
        return DetectionReport(
            label=kind.upper(),
            kind="analog",
            level=E.ESTIMATED,
            headline=f"Analog {kind.upper()}: not sent to the digital chain",
            stages=(
                detect_stage,
                _stage("classify", "Classify", f"Analog {kind.upper()}", E.ESTIMATED, (param,)),
            ),
            search=None,
            no_search_reason="An analog signal carries no bits, so no code or framing search ran.",
            no_frames_reason="An analog signal carries no bits.",
        )

    if rate is None or _frequency_kurtosis(x, channel, detection) < FSK_KURTOSIS:
        # Constant envelope and not analog, or discrete tones (a bimodal instantaneous
        # frequency; PSK's is spiky, well above 0) even where the channel filter has trimmed
        # the tones' skirts into envelope ripple: try 2-FSK, whose rate is in the transitions.
        candidates = [r for r in fsk_symbol_rates(x) if r.normalised_rate * len(x) >= MIN_SYMBOLS]
        report = _fsk_report(detect_stage, detection, units, x, candidates)
        if report is not None:
            return report

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
    )


# --- analog ---------------------------------------------------------------------------------


def _analog(x: Any, channel: Channel, detection: Detection) -> tuple[str, Parameter] | None:
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
    return result.kind, Parameter(
        id="modulation",
        name="Modulation",
        value=f"Analog {result.kind.upper()}",
        level=E.ESTIMATED,
        method="Envelope and instantaneous-frequency spread vs their AWGN floors (dsp.analog)",
        evidence=evidence,
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
CUMULANTS = {"BPSK": (2.0, 2.0), "QPSK": (1.0, 1.0), "8PSK": (0.0, 1.0), "16QAM": (0.68, 0.68)}


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

    @property
    def candidate(self) -> str:
        code = f"{self.code.name}, alignment {self.alignment}" if self.code else "uncoded"
        deinterleave = f" · {self.interleaver}" if self.interleaver else ""
        outer = f" · {RS_NAME}" if self.outer else ""
        # For FSK the branch index is which candidate symbol rate, not a carrier rotation.
        where = (
            f"rate candidate {self.rotation + 1}"
            if self.modulation.endswith("FSK")
            else f"at {self.rotation}°"
        )
        return f"{self.modulation} {where}{deinterleave} · {code}{outer}"


@dataclass(frozen=True)
class _Search:
    chains: tuple[_Chain, ...]
    tried: int
    threshold: float
    accepted: _Chain | None
    carriers: dict[str, Carrier]
    shuffled_accepts: int


Branch = tuple[str, int, Any]  # modulation, carrier rotation in degrees, soft bits


def _psk_branches(
    symbols: Any, ranked: tuple[tuple[str, float], ...], carriers: dict[str, Carrier]
) -> Iterator[list[Branch]]:
    """Per ranked modulation, best first: each of its carrier rotations as soft bits. Lazy, so
    modulations after an accepted one are never demodulated; `carriers` records each lock."""
    for modulation, _ in ranked:
        carrier = correct_carrier(symbols, ORDERS[modulation])
        carriers[modulation] = carrier
        yield [
            (modulation, rotation, demap(rotate(carrier.symbols, rotation), modulation).llr)
            for rotation in rotations(modulation)
        ]


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
        frames = find_frames(bits, word)
        chains.append(
            _Chain(modulation, rotation, code, alignment, frames, llr, _p_value(frames), **extra)
        )
    return chains


def _interleaver_cells(branch: Branch) -> list[_Chain]:
    """Each catalogued block interleaver, at the alignment where the code's parity syndrome is
    lowest; only an alignment that passes the syndrome screen goes on to Viterbi and framing."""
    modulation, rotation, soft = branch
    chains: list[_Chain] = []
    if modulation in ("BPSK", "QPSK") and rotation >= 180:
        # Only inverts every bit of the 0°/90° branch, which the code (odd-weight generators)
        # and the inverted-sync check already cover: counted as tried, not run again.
        return chains
    for entry in CATALOGUE:
        offset, rate = _interleaver_offset(soft, entry)
        label = f"block {entry.rows}x{entry.cols} from bit {offset}"
        if rate >= SYNDROME_SCREEN:
            chains.append(_Chain(modulation, rotation, K7_R12, 0, None, soft, None, label, rate))
            continue
        llr = deinterleave(soft, entry, offset)
        chains += _decode_cell(
            modulation, rotation, K7_R12, 0, llr, interleaver=label, syndrome=rate
        )
    return chains


def _search(
    groups: Iterable[list[Branch]], branch_count: int, carriers: dict[str, Carrier]
) -> _Search:
    """Every branch x (inner code x alignment, or block interleaver x alignment with the
    convolutional code) x sync word x CRC, Bonferroni-corrected over the whole grid
    (`branch_count` branches). The grid is walked cheapest first and stops at the first group
    with an accepted chain; the threshold covers the cells never reached, so it stays honest.
    Interleaver cells rejected by the syndrome screen count as tried."""
    per_branch = sum(2 if c else 1 for c in CODES) + sum(e.size for e in CATALOGUE)
    # Each cell also with the outer RS code at every bit alignment and codeword phase.
    tried = branch_count * per_branch * len(SYNC_WORDS) * len(CRCS) * (1 + rs.GRID_HYPOTHESES)
    threshold = ALPHA / tried

    def accepted() -> bool:
        return any(c.p_value is not None and c.p_value < threshold for c in chains)

    chains: list[_Chain] = []
    seen: list[list[Branch]] = []
    for group in groups:
        seen.append(group)
        for modulation, rotation, soft in group:
            for code in CODES:
                for alignment in range(2 if code else 1):
                    chains += _decode_cell(modulation, rotation, code, alignment, soft[alignment:])
        if accepted():
            break
    else:
        for group in seen:
            for branch in group:
                chains += _interleaver_cells(branch)
            if accepted():
                break
    chains += _outer_cells(chains, threshold)
    best = min(
        (c for c in chains if c.p_value is not None and c.p_value < threshold),
        key=lambda c: (c.p_value or 1.0, c.outer is None),
        default=None,
    )
    shuffled = _shuffled_accepts(best, threshold) if best else 0
    return _Search(tuple(chains), tried, threshold, best, carriers, shuffled)


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
        if chain.outer:
            outer = rs.decode_stream(bits)
            if outer is None:
                continue
            bits = outer.bits
        frames = find_frames(bits, chain.frames.word if chain.frames else SYNC_WORDS[0])
        p = _p_value(frames)
        accepts += int(p is not None and p < threshold)
    return accepts


def _interleaver_offset(soft: Any, entry: Block) -> tuple[int, float]:
    """The block alignment with the lowest parity-syndrome rate, and that rate: every offset's
    first blocks (at least SCREEN_BITS bits) deinterleaved and screened in one batch."""
    n = entry.size
    hard = (np.asarray(soft) < 0).astype(np.uint8)
    blocks = min(max(2, -(-SCREEN_BITS // n)), len(hard) // n - 1)
    if blocks < 1:
        return 0, 0.5
    inverse = np.argsort(entry.permutation())  # deinterleaved[i] = interleaved[inverse[i]]
    within = (np.arange(blocks)[:, None] * n + inverse[None, :]).ravel()
    rates = np.empty(n)
    for start in range(0, n, SCREEN_CHUNK):
        offsets = np.arange(start, min(n, start + SCREEN_CHUNK))
        rates[offsets] = syndrome_rates(hard[offsets[:, None] + within[None, :]])
    best = int(np.argmin(rates))
    return best, float(rates[best])


# --- outer Reed-Solomon ---------------------------------------------------------------------

RS_NAME = "RS(255,223) CCSDS"


def _outer_cells(chains: list[_Chain], threshold: float) -> list[_Chain]:
    """The outer RS code on the most promising inner chain: the accepted one when some of its
    frames fail their CRC, else the one whose sync word recurs most."""
    framed = [c for c in chains if c.frames is not None]
    if not framed:
        return []
    ok = [c for c in framed if c.p_value is not None and c.p_value < threshold]
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
) -> DetectionReport:
    acc = search.accepted
    rate_value, rate_unit, rate_scale = units.rate(timing.rate)
    modulation = acc.modulation if acc else ranked[0][0]
    carrier = search.carriers[modulation]
    symbols = rotate(carrier.symbols, acc.rotation if acc else 0)
    soft = demap(symbols, modulation)
    esn0 = -20 * math.log10(max(soft.evm, 1e-3))
    cfo_cycles = carrier.cfo * timing.rate / units.channel.decimation  # per input sample
    carrier_value, carrier_unit, carrier_scale = units.frequency(units.channel.centre + cfo_cycles)

    estimate_params = (
        Parameter(
            id="symbol_rate",
            name="Symbol rate",
            value=rate_value,
            unit=rate_unit,
            uncertainty=max(rate_uncertainty, abs(timing.rate - rate)) * rate_scale,
            level=E.ESTIMATED,
            method="|x|² spectral line, refined by the timing loop's drift",
            evidence=(
                f"Timing drift followed: {timing.drift:+.3f} symbols over "
                f"{len(timing.symbols):,} symbols",
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
            method=f"Detection centre plus the M-th power (M={carrier.order}) residual offset",
            evidence=("Relative to the capture centre.",),
        ),
        Parameter(
            id="esn0",
            name="Es/N0",
            value=round(esn0, 1),
            unit="dB",
            uncertainty=1.0,
            level=E.ESTIMATED,
            method="From the EVM of the recovered constellation (reads low below about 8 dB)",
        ),
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
        if acc
        else f"one of {', '.join(f'{r}°' for r in rotations(modulation))}",
        level=E.HYPOTHESIS,
        method=f"All {ORDERS[modulation]} rotations of the M-th power phase tried; the CRC decides",
    )
    timing_param = Parameter(
        id="timing",
        name="Timing recovery",
        value=round(timing.jitter, 4),
        unit="symbols RMS jitter",
        uncertainty=round(timing.jitter / 2, 4),
        level=E.ESTIMATED,
        method="RRC matched filter, Oerder-Meyr square-law timing per 256 symbols, unwrapped",
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
        value=modulation,
        level=E.HYPOTHESIS,
        confidence=round(dict(ranked)[modulation], 2),
        method="Nearest theoretical fourth-order cumulants (|C40|, -C42) on the carrier-locked "
        "symbols: BPSK (2, 2), QPSK (1, 1), 8PSK (0, 1), 16QAM (0.68, 0.68); tried in rank "
        "order, the CRC decides",
        evidence=("|C40| = {:.2f}, -C42 = {:.2f}".format(*_features(timing.symbols)),),
        alternatives=tuple(
            Alternative(value=m, confidence=round(c, 2)) for m, c in ranked if m != modulation
        ),
    )
    classify = _stage(
        "classify",
        "Classify",
        f"{modulation}, confirmed by decode" if acc else f"{modulation} (unconfirmed)",
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
        method=f"Error vector against the nearest ideal {modulation} point",
    )
    n_bits = len(symbols) * BITS_PER_SYMBOL[modulation]
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

    ledger = _ledger(search)
    label = modulation if acc else f"{modulation}?"
    if acc and acc.frames:
        code_name = acc.code.name if acc.code else "uncoded"
        f = acc.frames
        headline = (
            f"{modulation} {_fmt_rate(rate_value, rate_unit)} → {code_name} → {f.word.name} "
            f"frames, {f.passes}/{f.complete} CRC pass"
        )
    else:
        headline = f"{modulation}? {_fmt_rate(rate_value, rate_unit)}, not decoded"
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
    )


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

    def groups() -> Iterator[list[Branch]]:
        for i, r in enumerate(rates):
            try:
                demodulated[i] = (r, fsk.demodulate(x, r.normalised_rate))
            except ValueError:
                continue
            yield [("2FSK", i, demodulated[i][1].llr)]

    search = _search(groups(), len(rates), {})
    if not demodulated:
        return None
    acc = search.accepted
    rate, symbols = demodulated[acc.rotation if acc else min(demodulated)]
    proof = _proof(acc) if acc else None
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
            Parameter(
                id="symbol_rate",
                name="Symbol rate",
                value=rate_value,
                unit=rate_unit,
                uncertainty=rate.uncertainty * rate_scale,
                level=E.ESTIMATED,
                method="Tone-transition comb: lowest significant line in the discriminator's "
                "edge energy",
            ),
            Parameter(
                id="tone_spacing",
                name="Tone spacing",
                value=shift_value,
                unit=shift_unit,
                uncertainty=0.05 * abs(shift_value),
                level=E.ESTIMATED,
                method="Medians of the discriminator's two frequency clusters",
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
        value="2FSK",
        level=E.HYPOTHESIS,
        method="Constant envelope with a tone-transition comb; discrete tones, so not analog FM",
    )
    classify = _stage(
        "classify",
        "Classify",
        "2FSK, confirmed by decode" if acc else "2FSK (unconfirmed)",
        E.VERIFIED if acc else E.HYPOTHESIS,
        (promote(mod_param, proof) if proof else mod_param,),
    )
    inverted = bool(acc and acc.frames and acc.frames.inverted)
    mapping = Parameter(
        id="bit_mapping",
        name="Bit mapping",
        value="upper tone = 0" if inverted else "lower tone = 0",
        level=E.HYPOTHESIS,
        method="Per-symbol tone energies over the symbol interior; the sync word's polarity "
        "decides which tone is 0",
    )
    demod = _stage(
        "demod",
        "Demodulate",
        f"{len(symbols.llr):,} soft bits, non-coherent",
        E.ESTIMATED,
        (promote(mapping, proof) if proof else mapping,),
    )
    stages = [detect_stage, estimate, sync, classify, demod]
    decode_stages, frames = _decode_stages(search, proof, "2FSK x both polarities")
    stages += decode_stages
    if acc and acc.frames:
        code_name = acc.code.name if acc.code else "uncoded"
        headline = (
            f"2FSK {_fmt_rate(rate_value, rate_unit)} → {code_name} → {acc.frames.word.name} "
            f"frames, {acc.frames.passes}/{acc.frames.complete} CRC pass"
        )
    else:
        headline = f"2FSK? {_fmt_rate(rate_value, rate_unit)}, not decoded"
    return DetectionReport(
        label="2FSK" if acc else "2FSK?",
        kind="fsk",
        level=E.VERIFIED if any(fr.crc == "pass" for fr in frames) else E.ESTIMATED,
        headline=headline,
        stages=tuple(stages),
        search=_ledger(search),
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
        if acc.interleaver:
            param = Parameter(
                id="interleaver",
                name="Interleaver",
                value=acc.interleaver,
                level=E.HYPOTHESIS,
                method="Block-interleaver catalogue; alignment by the inner code's parity "
                "syndrome, decided by the CRC",
                evidence=(f"Syndrome rate {acc.syndrome or 0:.3f} here (0.5 if wrong)",),
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
                    method="Catalogue search (soft Viterbi), decided by the CRC",
                ),
                proof,
            )
        ]
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
            code_value = f"{code_value} + {RS_NAME}"
        stages.append(_stage("fec", "FEC", code_value, E.VERIFIED, tuple(code_params)))
        frame_params = (
            promote(
                Parameter(
                    id="sync_word",
                    name="Sync word",
                    value=f.word.hex,
                    unit=f.word.name,
                    level=E.HYPOTHESIS,
                    method="Known-sync catalogue correlation, ≤ 3 bit errors",
                    evidence=(
                        f"{f.hits} hits; recurs every {f.period:,} bits "
                        f"({f.recurrences} consecutive pairs)"
                        + (", inverted polarity" if f.inverted else ""),
                    ),
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
                    method="CRC catalogue over the bits between sync word and CRC field",
                ),
                proof,
            ),
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
            f"None of the {search.tried} hypotheses ({grid} x uncoded or conv K=7 r½ "
            f"x {len(SYNC_WORDS)} sync word x {len(CRCS)} CRCs) gave CRC passes significant "
            f"at {search.threshold:.1e}."
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
                        method="Catalogue search: uncoded, conv K=7 r½; decided by sync word + CRC",
                        evidence=(reason,),
                        resolve_hint="Naming the transmitting standard, or adding its code and "
                        "framing to the catalogue, would settle it.",
                    ),
                ),
            )
        )
    return stages, frames


def _proof(chain: _Chain) -> Proof:
    f = chain.frames
    assert f is not None and f.crc is not None
    return Proof(
        kind="crc",
        detail=f"{f.crc.name} passes on {f.passes} of {f.complete} complete frames "
        f"({chain.candidate})",
    )


def _ledger(search: _Search) -> HypothesisSearch:
    def row(c: _Chain) -> Hypothesis:
        f = c.frames
        ok = c is search.accepted
        if c.interleaver and c.syndrome is not None and c.syndrome >= SYNDROME_SCREEN:
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
        return Hypothesis(
            layer="Interleaver" if c.interleaver else ("FEC" if c.code else "Framing"),
            candidate=c.candidate,
            statistic=statistic,
            p_value=c.p_value,
            threshold=search.threshold,
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
        shuffled_runs=SHUFFLED_RUNS if search.accepted else 0,
        shuffled_accepts=search.shuffled_accepts,
        rows=tuple(row(c) for c in ordered[:MAX_LEDGER_ROWS]),
    )
