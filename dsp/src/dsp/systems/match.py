"""The Match stage (PLAN M6): compare a signal with the known-system catalogue and run each
fitting entry's own check on this recording.

Blind results always stand. Match reads them (modulation, symbol rate, code, and the frames the
chain found) and the demodulated bits, and adds a `system` parameter beside them:

- **VERIFIED** only when the entry's own check passes on this recording, significant after Holm
  correction over every check run (`crc` proof for CCSDS: marker recurrence plus the frame error
  control field; `reencode` proof for POCSAG: the synchronisation codeword recurring every batch
  plus BCH(31,21) and parity re-encoded on the codewords between);
- **HYPOTHESIS** "consistent with ..." when an entry fits by parameters but its check could not
  run (no bits to check);
- **UNKNOWN** otherwise, naming the closest entries and why each failed.

An entry whose parameters conflict with the blind findings is not checked (a check on bits
demodulated for something else proves nothing) and is listed with the conflict. Every check run
is one hypothesis in the ledger, layer "Match".
"""

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from dsp.evidence import Alternative, EvidenceLevel, Parameter, Proof
from dsp.framing import MAX_SYNC_ERRORS, FrameResult, binomial_tail
from dsp.report import Frame, Hypothesis, StageReport
from dsp.systems import ais, ccir476, dsc, pocsag
from dsp.systems.catalogue import CATALOGUE, RATE_TOLERANCE, TONE_TOLERANCE, SystemEntry
from dsp.systems.ccsds import HEADER_BYTES, TM_VERSION, parse_header

E = EvidenceLevel
Bits = NDArray[np.uint8]
Outcome = Literal["verified", "failed", "conflict", "not-run"]

MAX_FRAMES = 500
# The family-wise error rate of the Match stage, well below the blind search's 0.01 because a
# check that has a structure to find (a sync word, a repeat) has no prior reason to be tried on a
# given stream: PLAN M6's gate is a false-alarm rate of 1e-6 per stream. A real match has p far
# below this (1e-100 and smaller on a few dozen codewords).
MATCH_ALPHA = 1e-6
MAX_PAGES_SHOWN = 20
MAX_FRAME_TEXT = 500
CCSDS_CRC = "CRC-16/CCITT-FALSE"
CCSDS_ASM = "CCSDS ASM"
FRAME_CHECK_CHANCE = 2.0**-16  # a random frame passes a 16-bit CRC


@dataclass(frozen=True)
class Findings:
    """What the blind analysis found about a signal, to compare with catalogue entries; None for
    anything it did not or could not determine."""

    modulation: str | None
    symbol_rate: float | None = None  # baud; None when there is no sample rate to state it in
    rate_uncertainty: float | None = None
    tone_spacing: float | None = None  # hertz
    code: str | None = None  # "Uncoded", or the inner code's name
    interleaver: str | None = None
    descrambler: str | None = None
    outer: str | None = None  # the outer code's name, when frames came through one


@dataclass(frozen=True)
class Candidate:
    """One demodulation hypothesis (a symbol-rate candidate, a carrier rotation) and its
    uncoded hard-decision bits, which a system's check can read."""

    label: str
    findings: Findings
    bits: Bits | None
    key: int = 0  # the caller's index of this hypothesis


@dataclass(frozen=True)
class Accepted:
    """The blind chain that passed its CRC, when one did."""

    frames: FrameResult
    findings: Findings
    p_value: float


def relayout(frames: tuple[Frame, ...], entry: SystemEntry) -> tuple[Frame, ...]:
    """The chain's frames with the header column set to the verified system's own header length
    (a catalogue-framed stream otherwise shows a fixed four-byte column), the payload unchanged.
    Frames shorter than the header are left alone."""
    size = entry.header_bytes
    if size is None:
        return frames
    out: list[Frame] = []
    for f in frames:
        whole = f.payload_hex
        if len(whole) >= 2 * size:
            head = " ".join(whole[i : i + 2] for i in range(0, 2 * size, 2))
            out.append(Frame.model_validate({**f.model_dump(by_alias=False), "header_hex": head}))
        else:
            out.append(f)
    return tuple(out)


@dataclass(frozen=True)
class MatchResult:
    stage: StageReport
    rows: tuple[Hypothesis, ...]
    tried: int  # checks run, each a hypothesis in the Holm count
    frames: tuple[Frame, ...] = field(default=())  # a verified system's own frames
    verified: SystemEntry | None = None
    proof: Proof | None = None  # of the verified system's check, which also settles the
    key: int = 0  # demodulation hypothesis (this `Candidate.key`) it was run on,
    inverted: bool = False  # and the bit polarity that fitted


@dataclass
class _Run:
    entry: SystemEntry
    label: str
    outcome: Outcome
    p_value: float | None
    statistic: str
    reason: str
    proof: Proof | None = None
    evidence: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    frames: tuple[Frame, ...] = ()
    pages: tuple[pocsag.Page, ...] = ()
    threshold: float = 0.0
    header: pocsag.PocsagScan | None = None
    tm: tuple[str, ...] = ()
    key: int = 0
    extra: tuple[Parameter, ...] = ()  # the system's own parameters, e.g. decoded text


def holm(p_values: list[float], alpha: float) -> list[float]:
    """Holm's step-down thresholds, in the order given: the k-th smallest p is tested against
    alpha / (m - k); the first failure stops the walk, so every larger p is tested against a
    threshold it cannot pass (returned as 0)."""
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    thresholds = [0.0] * m
    alive = True
    for rank, i in enumerate(order):
        limit = alpha / (m - rank)
        thresholds[i] = limit if alive else 0.0
        alive = alive and p_values[i] < limit
    return thresholds


def fit(entry: SystemEntry, f: Findings) -> tuple[list[str], list[str]]:
    """(conflicts, notes) of a signal's blind findings against an entry: a conflict is a finding
    the entry rules out; a note is something that could not be compared or only differs."""
    conflicts: list[str] = []
    notes: list[str] = []
    if f.modulation is not None and entry.modulations and f.modulation not in entry.modulations:
        conflicts.append(f"modulation {f.modulation} is not among {', '.join(entry.modulations)}")
    if entry.symbol_rates:
        if f.symbol_rate is None:
            notes.append(
                "symbol rate not compared: no sample rate to state it in baud "
                f"(entry: {', '.join(f'{r:g}' for r in entry.symbol_rates)} Bd)"
            )
        else:
            rate = f.symbol_rate
            nearest = min(entry.symbol_rates, key=lambda r: abs(r - rate))
            tolerance = max(3 * (f.rate_uncertainty or 0.0), RATE_TOLERANCE * nearest)
            if abs(rate - nearest) > tolerance:
                conflicts.append(
                    f"symbol rate {rate:.4g} Bd is not within {tolerance:.3g} Bd of "
                    f"{', '.join(f'{r:g}' for r in entry.symbol_rates)} Bd"
                )
    if (
        f.code is not None
        and entry.codes
        and not any(f.code.lower().startswith(c.lower()) for c in entry.codes)
    ):
        conflicts.append(f"code {f.code} is not among {', '.join(entry.codes)}")
    if f.interleaver is not None and f.interleaver not in entry.interleavers:
        conflicts.append(f"interleaver {f.interleaver} is not part of the entry")
    if f.outer is not None and f.outer not in entry.outer_codes:
        conflicts.append(f"outer code {f.outer} is not part of the entry")
    if f.descrambler is not None and f.descrambler not in entry.descramblers:
        conflicts.append(f"descrambler {f.descrambler} is not part of the entry")
    if (
        entry.tone_spacing_hz
        and f.tone_spacing
        and abs(f.tone_spacing - entry.tone_spacing_hz) > TONE_TOLERANCE * entry.tone_spacing_hz
    ):
        notes.append(
            f"tone spacing {f.tone_spacing:.4g} Hz differs from the entry's "
            f"{entry.tone_spacing_hz:g} Hz (shown, not a condition: deviation varies by service)"
        )
    return conflicts, notes


def match(
    candidates: list[Candidate],
    accepted: Accepted | None,
    alpha: float,
    *,
    has_bits: bool = True,
) -> MatchResult:
    """Run the catalogue against one signal. `candidates` are its demodulation hypotheses (for
    checks that read bits); `accepted` is the blind chain that decoded, if any."""
    runs: list[_Run] = []
    for entry in CATALOGUE.entries:
        if entry.check == "pocsag":
            runs += _pocsag_runs(entry, candidates)
        elif entry.check == "navtex":
            runs += _navtex_runs(entry, candidates)
        elif entry.check == "dsc":
            runs += _dsc_runs(entry, candidates)
        elif entry.check == "ais":
            runs += _ais_runs(entry, candidates)
        elif entry.check == "ccsds-tm":
            runs.append(_ccsds_run(entry, accepted, candidates))
    # A run with no p-value never ran a check (the entry needs a chain the blind search did not
    # accept), so it is listed but is not a hypothesis in the correction.
    checked = [r for r in runs if r.outcome in ("verified", "failed") and r.p_value is not None]
    thresholds = holm([1.0 if r.p_value is None else r.p_value for r in checked], alpha)
    for r, limit in zip(checked, thresholds, strict=True):
        r.threshold = limit
        significant = r.p_value is not None and r.p_value < limit
        if r.outcome == "verified" and not significant:
            r.outcome = "failed"
            r.proof = None
            r.reason = "The check passed on too few codewords to rule out chance after correction"
    verified = sorted((r for r in runs if r.outcome == "verified"), key=lambda r: r.p_value or 1.0)
    # An accepted row first, so the ledger's row limit can never cut it off.
    ordered = sorted(runs, key=lambda r: r.outcome != "verified")
    rows = tuple(_row(r, alpha, len(checked)) for r in ordered)
    best = verified[0] if verified else None
    return MatchResult(
        stage=_stage(runs, verified, has_bits),
        rows=rows,
        tried=len(checked),
        frames=best.frames if best else (),
        verified=best.entry if best else None,
        proof=best.proof if best else None,
        key=best.key if best else 0,
        inverted=bool(best and best.header and best.header.inverted),
    )


def _row(run: _Run, alpha: float, m: int) -> Hypothesis:
    return Hypothesis(
        layer="Match",
        candidate=f"{run.entry.name} · {run.label}",
        statistic=run.statistic,
        p_value=run.p_value,
        threshold=run.threshold or alpha / max(m, 1),
        outcome="accepted" if run.outcome == "verified" else "rejected",
        reason=run.reason,
    )


def _stage(runs: list[_Run], verified: list[_Run], has_bits: bool) -> StageReport:
    if verified:
        best = verified[0]
        assert best.proof is not None
        parameters = [
            Parameter(
                id="system",
                name="Known system",
                value=best.entry.name,
                level=E.VERIFIED,
                method=(
                    f"Known-system catalogue {CATALOGUE.version}: parameters compared with the "
                    f"blind findings, then the entry's own check run on this recording "
                    f"({best.entry.specification})"
                ),
                evidence=(*best.evidence, *best.notes),
                alternatives=tuple(
                    Alternative(value=name)
                    for name in dict.fromkeys(r.entry.name for r in verified[1:])
                    if name != best.entry.name
                ),
                proof=best.proof,
                warnings=(
                    "A blind result that differs from the entry's parameters stands as found.",
                ),
            )
        ]
        if best.pages:
            parameters.append(_pages_parameter(best))
        parameters += best.extra
        if best.tm:
            parameters.append(
                Parameter(
                    id="tm_header",
                    name="Transfer frame header",
                    value=best.tm[0],
                    level=E.VERIFIED,
                    method="CCSDS 132.0-B-3 primary header of the first frame passing its check",
                    evidence=best.tm[1:],
                    proof=best.proof,
                )
            )
        return StageReport(
            id="match",
            name="Match",
            status="done",
            summary=f"{best.entry.name}: {best.reason}",
            level=E.VERIFIED,
            parameters=tuple(parameters),
        )
    unrun = [r for r in runs if r.outcome == "not-run"]
    if unrun:
        names = sorted({r.entry.name for r in unrun})
        return StageReport(
            id="match",
            name="Match",
            status="done",
            summary=f"Consistent with {', '.join(names)}; check could not run",
            level=E.HYPOTHESIS,
            parameters=(
                Parameter(
                    id="system",
                    name="Known system",
                    value=f"consistent with {', '.join(names)}",
                    level=E.HYPOTHESIS,
                    method="Parameters within the catalogue entry's tolerances; its own check "
                    "could not run on this recording",
                    evidence=(
                        *(f"{r.entry.name}: {r.reason}" for r in unrun),
                        *(note for r in unrun for note in r.notes),
                        *(
                            f"{r.entry.name} ({r.label}): {r.reason}"
                            for r in runs
                            if r.outcome in ("failed", "conflict")
                        ),
                    ),
                ),
            ),
        )
    why = tuple(f"{r.entry.name} ({r.label}): {r.reason}" for r in runs) or (
        "No catalogue entry applies to this signal.",
    )
    return StageReport(
        id="match",
        name="Match",
        status="done",
        summary="No catalogued system confirmed",
        level=E.UNKNOWN,
        parameters=(
            Parameter(
                id="system",
                name="Known system",
                value=None,
                level=E.UNKNOWN,
                method=f"Known-system catalogue {CATALOGUE.version}: parameters, then each "
                "fitting entry's own check",
                evidence=why if has_bits else (*why, "No demodulated bits were available."),
                resolve_hint="A recording that carries a catalogued system, or the system added "
                "to the catalogue with its specification, would settle it.",
            ),
        ),
    )


def _pages_parameter(run: _Run) -> Parameter:
    shown = run.pages[:MAX_PAGES_SHOWN]
    lines = [
        f"RIC {p.address:07d} function {p.function}: "
        + (f'"{p.text}"' if p.text is not None else "not shown (numeric, or a codeword failed)")
        for p in shown
    ]
    if len(run.pages) > len(shown):
        lines.append(f"... and {len(run.pages) - len(shown)} more")
    return Parameter(
        id="pages",
        name="Pages",
        value=f"{len(run.pages)} page{'s' if len(run.pages) != 1 else ''}",
        level=E.HYPOTHESIS,
        method="Address and message codewords that pass BCH and parity, grouped per page",
        evidence=tuple(lines),
        convention=(
            "Function bits 3 read as alphanumeric 7-bit ASCII (the standard leaves the function "
            "bits' meaning to the operator); shown only from codewords that pass their check, "
            "and never used as evidence"
        ),
    )


def _bits_needed() -> int:
    return 2 * pocsag.BATCH_BITS


def _pocsag_runs(entry: SystemEntry, candidates: list[Candidate]) -> list[_Run]:
    runs: list[_Run] = []
    for cand in candidates:
        conflicts, notes = fit(entry, cand.findings)
        if conflicts:
            runs.append(
                _Run(
                    entry, cand.label, "conflict", None, "Parameters conflict", "; ".join(conflicts)
                )
            )
            continue
        if cand.bits is None or len(cand.bits) < _bits_needed():
            n = 0 if cand.bits is None else len(cand.bits)
            runs.append(
                _Run(
                    entry,
                    cand.label,
                    "not-run",
                    None,
                    "Too few bits to check",
                    f"{n} bits; the check needs two batches ({_bits_needed()})",
                    notes=tuple(notes),
                )
            )
            continue
        found = pocsag.scan(cand.bits)
        if found is None:
            runs.append(
                _Run(
                    entry,
                    cand.label,
                    "failed",
                    1.0,
                    "Synchronisation codeword does not recur every 544 bits",
                    "No POCSAG synchronisation codeword recurs one batch apart, in either polarity",
                    notes=tuple(notes),
                )
            )
            continue
        good = sum(1 for b in found.batches if b.passes)
        reason = (
            f"{found.valid} of {found.codewords} codewords between the synchronisation words pass "
            f"BCH(31,21) and parity; "
            f"synchronisation codeword recurs every 544 bits ({found.recurrences} pairs)"
        )
        runs.append(
            _Run(
                entry,
                cand.label,
                "verified",
                found.p_value,
                f"{found.valid}/{found.codewords} codewords valid, sync x{found.hits}",
                reason,
                proof=Proof(
                    kind="reencode",
                    detail=f"BCH(31,21) + parity re-encode matches on {found.valid} of "
                    f"{found.codewords} codewords, synchronisation codeword 0x7CD215D8 recurring "
                    f"every 544 bits ({found.recurrences} consecutive pairs, each hit allowing "
                    f"up to {MAX_SYNC_ERRORS} bit errors); a random word passes with "
                    f"probability 2^-11",
                ),
                evidence=(
                    reason,
                    f"{good} of {len(found.batches)} batches have all 17 codewords valid; "
                    f"stream {'inverted' if found.inverted else 'upright'} (bit polarity was "
                    "chosen by the sync search)",
                    f"Chance of this many valid codewords in a random stream: {found.p_value:.1e}",
                ),
                notes=tuple(notes),
                frames=_batch_frames(found),
                pages=found.pages,
                header=found,
                key=cand.key,
            )
        )
    return runs


def _batch_frames(found: pocsag.PocsagScan) -> tuple[Frame, ...]:
    out: list[Frame] = []
    for i, b in enumerate(found.batches[:MAX_FRAMES]):
        out.append(
            Frame(
                index=i + 1,
                start_bit=b.start_bit,
                sync_word=pocsag.SYNC.hex,
                length_bits=b.length_bits,
                crc="pass" if b.passes else ("truncated" if not b.complete else "fail"),
                header_hex=b.body_hex[0] if b.body_hex else "",
                payload_hex="".join(b.body_hex[1:]),
            )
        )
    return tuple(out)


def _ccsds_run(entry: SystemEntry, accepted: Accepted | None, candidates: list[Candidate]) -> _Run:
    if accepted is None:
        conflicts = [fit(entry, c.findings)[0] for c in candidates]
        if candidates and all(conflicts):
            return _Run(
                entry, "any candidate", "conflict", None, "Parameters conflict", conflicts[0][0]
            )
        return _Run(
            entry,
            "blind chain",
            "failed",
            None,
            "No accepted frame chain",
            "The blind search accepted no frame chain, so no marker-plus-CRC check is on offer",
        )
    f = accepted.frames
    conflicts, notes = fit(entry, accepted.findings)
    if f.word.name != CCSDS_ASM or f.crc is None or f.crc.name != CCSDS_CRC:
        found = f"{f.word.name}, {f.crc.name if f.crc else 'no catalogued CRC'}"
        return _Run(
            entry,
            "blind chain",
            "conflict",
            None,
            "Framing conflicts",
            f"the frames found use {found}; {entry.name} uses the {CCSDS_ASM} and "
            f"{entry.frame_check}",
        )
    if conflicts:
        return _Run(
            entry, "blind chain", "conflict", None, "Parameters conflict", "; ".join(conflicts)
        )
    passing = [fr for fr in f.frames if fr.crc == "pass"]
    versions = {h.version for fr in passing if (h := parse_header(fr.payload)) is not None}
    if versions - {TM_VERSION}:
        return _Run(
            entry,
            "blind chain",
            "failed",
            accepted.p_value,
            "Primary header version",
            f"passing frames carry version {sorted(versions)[0]} in the primary header; "
            f"TM transfer frames carry {TM_VERSION}",
            notes=tuple(notes),
        )
    p = binomial_tail(f.passes, f.complete, FRAME_CHECK_CHANCE)
    header = parse_header(passing[0].payload) if passing else None
    tm: tuple[str, ...] = ()
    if header is not None:
        tm = (
            f"version {header.version}, spacecraft {header.spacecraft_id:#x}, virtual channel "
            f"{header.virtual_channel}, master channel count {header.master_channel_count}",
            f"OCF flag {int(header.ocf_flag)}; virtual channel count "
            f"{header.virtual_channel_count}; data field status {header.data_field_status:#06x}",
            f"Read from the first of {f.passes} frames whose {CCSDS_CRC} passes",
        )
    reason = (
        f"attached sync marker recurs every {f.period:,} bits and the frame error control field "
        f"({CCSDS_CRC}) passes on {f.passes} of {f.complete} frames"
    )
    return _Run(
        entry,
        "blind chain",
        "verified",
        p,
        f"{CCSDS_ASM} x{f.hits}, {f.passes}/{f.complete} {CCSDS_CRC}",
        reason,
        proof=Proof(
            kind="crc",
            detail=f"{CCSDS_CRC} (the frame error control field) passes on {f.passes} of "
            f"{f.complete} frames delimited by the recurring {CCSDS_ASM}",
        ),
        evidence=(reason, f"Header of {HEADER_BYTES} bytes parsed per CCSDS 132.0-B-3"),
        notes=tuple(notes),
        tm=tm,
    )


def _navtex_runs(entry: SystemEntry, candidates: list[Candidate]) -> list[_Run]:
    runs: list[_Run] = []
    for cand in candidates:
        conflicts, notes = fit(entry, cand.findings)
        if conflicts:
            runs.append(
                _Run(
                    entry, cand.label, "conflict", None, "Parameters conflict", "; ".join(conflicts)
                )
            )
            continue
        needed = ccir476.MIN_PAIRS * 2 * ccir476.WIDTH + ccir476.REPEAT_SLOTS * ccir476.WIDTH
        if cand.bits is None or len(cand.bits) < needed:
            n = 0 if cand.bits is None else len(cand.bits)
            runs.append(
                _Run(
                    entry,
                    cand.label,
                    "not-run",
                    None,
                    "Too few bits to check",
                    f"{n} bits; the check needs {ccir476.MIN_PAIRS} repeated characters ({needed})",
                    notes=tuple(notes),
                )
            )
            continue
        found = ccir476.scan(cand.bits)
        if found is None:
            runs.append(
                _Run(
                    entry,
                    cand.label,
                    "failed",
                    1.0,
                    "No repeated four-of-seven characters",
                    "No polarity, group boundary and repeat phase shows valid seven-bit characters "
                    f"repeated {ccir476.REPEAT_SLOTS} slots later on enough distinct characters",
                    notes=tuple(notes),
                )
            )
            continue
        reason = (
            f"{found.agree} of {found.pairs} repetition slots hold a valid four-of-seven character "
            f"equal to the one {ccir476.REPEAT_SLOTS} slots earlier ({found.distinct} distinct "
            f"characters); polarity {'inverted' if found.inverted else 'upright'}, group boundary "
            f"at bit {found.offset}"
        )
        runs.append(
            _Run(
                entry,
                cand.label,
                "verified",
                found.p_value,
                f"{found.agree}/{found.pairs} repeats agree, {found.distinct} distinct",
                reason,
                proof=Proof(
                    kind="reencode",
                    detail=f"{found.agree} of {found.pairs} time-diversity copies agree on valid "
                    f"four-of-seven characters; a random pair is a valid equal pair with "
                    f"probability at most {ccir476.RANDOM_PAIR:.1e}, corrected for "
                    f"{found.tried} polarity/boundary/phase hypotheses",
                ),
                evidence=(
                    reason,
                    f"Chance of this many agreeing copies in a random stream: {found.p_value:.1e} "
                    f"(corrected over {found.tried} hypotheses)",
                    f"{found.characters} characters recovered from either copy, "
                    f"{found.erased} with neither copy valid",
                ),
                notes=tuple(notes),
                frames=_diversity_frames(found),
                key=cand.key,
                extra=_messages_parameter(found),
            )
        )
    return runs


def _ais_runs(entry: SystemEntry, candidates: list[Candidate]) -> list[_Run]:
    runs: list[_Run] = []
    needed = ais.MIN_PASSES * (ais.MIN_FRAME_BITS + 2 * len(ais.FLAG))
    for cand in candidates:
        conflicts, notes = fit(entry, cand.findings)
        if conflicts:
            runs.append(
                _Run(
                    entry, cand.label, "conflict", None, "Parameters conflict", "; ".join(conflicts)
                )
            )
            continue
        if cand.bits is None or len(cand.bits) < needed:
            n = 0 if cand.bits is None else len(cand.bits)
            runs.append(
                _Run(
                    entry,
                    cand.label,
                    "not-run",
                    None,
                    "Too few bits to check",
                    f"{n} bits; the check needs {ais.MIN_PASSES} whole packets ({needed})",
                    notes=tuple(notes),
                )
            )
            continue
        found = ais.scan(cand.bits)
        if found is None:
            runs.append(
                _Run(
                    entry,
                    cand.label,
                    "failed",
                    1.0,
                    f"Fewer than {ais.MIN_PASSES} HDLC frames pass CRC-16/X.25",
                    "No frame between flags in the NRZI-decoded stream passes the CRC-16/X.25 "
                    f"check on at least {ais.MIN_PASSES} packets",
                    notes=tuple(notes),
                )
            )
            continue
        reason = (
            f"{found.passes} of {found.candidates} HDLC frames between flags pass CRC-16/X.25 "
            "after NRZI decoding and removing bit stuffing"
        )
        runs.append(
            _Run(
                entry,
                cand.label,
                "verified",
                found.p_value,
                f"{found.passes}/{found.candidates} frames pass CRC-16/X.25",
                reason,
                proof=Proof(
                    kind="crc",
                    detail=f"CRC-16/X.25 passes on {found.passes} of {found.candidates} HDLC "
                    f"frames; a random frame passes with probability 2^-16",
                ),
                evidence=(
                    reason,
                    f"Chance of this many CRC passes in a random stream: {found.p_value:.1e}",
                    "NRZI decoding looks only at level changes, so the bit polarity and a "
                    "mirrored spectrum do not matter",
                ),
                notes=tuple(notes),
                frames=_ais_frames(found),
                key=cand.key,
                extra=_ais_messages_parameter(found),
            )
        )
    return runs


def _ais_frames(found: ais.AisScan) -> tuple[Frame, ...]:
    """One frame per candidate packet: the flag as its sync word, the first five bytes (message
    type, repeat indicator and MMSI) as its header and the rest of the message as its payload."""
    out: list[Frame] = []
    for i, p in enumerate(found.packets[:MAX_FRAMES]):
        out.append(
            Frame(
                index=i + 1,
                start_bit=p.start_bit,
                sync_word="7E",
                length_bits=p.length_bits,
                crc="pass" if p.passes else "fail",
                header_hex=" ".join(f"{b:02X}" for b in p.data[:5]),
                payload_hex=p.data[5:].hex().upper(),
            )
        )
    return tuple(out)


def _ais_messages_parameter(found: ais.AisScan) -> tuple[Parameter, ...]:
    shown = found.passing[:MAX_PAGES_SHOWN]
    return (
        Parameter(
            id="ais_messages",
            name="AIS messages",
            value=f"{found.passes} packet{'s' if found.passes != 1 else ''}, "
            f"{len({p.mmsi for p in found.passing})} MMSI(s)",
            level=E.HYPOTHESIS,
            method="Message type, repeat indicator and MMSI read from the first 38 bits of each "
            "packet that passed its CRC",
            evidence=tuple(f"type {p.message_type}, MMSI {p.mmsi:09d}" for p in shown),
            convention=(
                "The first 38 message bits read as message type (6), repeat indicator (2) and "
                "MMSI (30), most significant bit first, as ITU-R M.1371-6 lays them out; the "
                "CRC does not depend on this reading and the rest of the message is not decoded"
            ),
        ),
    )


def _diversity_frames(found: ccir476.Ccir476Scan) -> tuple[Frame, ...]:
    """One frame per message (ZCZC to NNNN), passing when every one of its characters was
    recovered from a valid copy. Without a complete header and trailer there is no message, so
    one frame covers the stretch where copies agree: for this system the agreement of the
    time-diversity copies is the frame check, and it has passed (that is why the system is
    verified), so the frame passes, with no text to show."""
    if found.messages:
        return tuple(
            Frame(
                index=i + 1,
                start_bit=m.start_bit,
                sync_word="ZCZC",
                length_bits=m.length_bits,
                crc="pass" if m.complete else "fail",
                header_hex=f"{m.station}{m.subject}{m.serial}".encode().hex().upper(),
                payload_hex=m.body[:MAX_FRAME_TEXT].encode("utf-8").hex().upper(),
            )
            for i, m in enumerate(found.messages[:MAX_FRAMES])
        )
    first, last = found.span
    return (
        Frame(
            index=1,
            start_bit=first,
            sync_word="SITOR-B",
            length_bits=last - first,
            crc="pass",
            header_hex="",
            payload_hex=found.text[:MAX_FRAME_TEXT].encode("utf-8").hex().upper(),
        ),
    )


def _messages_parameter(found: ccir476.Ccir476Scan) -> tuple[Parameter, ...]:
    if not found.messages:
        return ()
    identity = [(m.station, m.subject, m.serial, m.body) for m in found.messages]
    distinct_ids = list(dict.fromkeys(identity))
    distinct = [
        next(m for m in found.messages if (m.station, m.subject, m.serial, m.body) == d)
        for d in distinct_ids[:MAX_PAGES_SHOWN]
    ]
    lines = tuple(f"{m.station}{m.subject}{m.serial}: {m.body[:200]}" for m in distinct)
    return (
        Parameter(
            id="messages",
            name="NAVTEX messages",
            value=f"{len(found.messages)} message{'s' if len(found.messages) != 1 else ''} "
            f"({len(distinct_ids)} distinct)",
            level=E.HYPOTHESIS,
            method="Characters from the first or repeated copy, decoded through the CCIR 476 "
            "letters and figures sets between ZCZC and NNNN headers",
            evidence=lines,
            convention=(
                f"Bits read {found.bit_order} against the CCIR 476 table (most significant bit "
                "first, mark = 1), the order that puts ZCZC headers in the text; the figures set "
                "is the international one. The check cannot tell bit orders apart, so the text "
                "rests on this convention and is never used as evidence"
            ),
        ),
    )


def _dsc_runs(entry: SystemEntry, candidates: list[Candidate]) -> list[_Run]:
    runs: list[_Run] = []
    for cand in candidates:
        conflicts, notes = fit(entry, cand.findings)
        if conflicts:
            runs.append(
                _Run(
                    entry, cand.label, "conflict", None, "Parameters conflict", "; ".join(conflicts)
                )
            )
            continue
        needed = dsc.MIN_PAIRS * 2 * dsc.WIDTH + dsc.REPEAT_SLOTS * dsc.WIDTH
        if cand.bits is None or len(cand.bits) < needed:
            n = 0 if cand.bits is None else len(cand.bits)
            runs.append(
                _Run(
                    entry,
                    cand.label,
                    "not-run",
                    None,
                    "Too few bits to check",
                    f"{n} bits; the check needs {dsc.MIN_PAIRS} repeated characters ({needed})",
                    notes=tuple(notes),
                )
            )
            continue
        found = dsc.scan(cand.bits)
        if found is None:
            runs.append(
                _Run(
                    entry,
                    cand.label,
                    "failed",
                    1.0,
                    "No repeated ten-bit characters",
                    "No polarity, group boundary and repeat phase shows valid ten-bit characters "
                    f"repeated {dsc.REPEAT_SLOTS} slots later on enough distinct characters",
                    notes=tuple(notes),
                )
            )
            continue
        reason = (
            f"{found.agree} of {found.pairs} repetition slots hold a character whose check bits "
            f"agree and that equals the one {dsc.REPEAT_SLOTS} slots earlier ({found.distinct} "
            f"distinct characters); polarity {'inverted' if found.inverted else 'upright'}, "
            f"group boundary at bit {found.offset}"
        )
        checked = [c for c in found.calls if c.ecc_ok is not None]
        ecc_line = (
            f"Error-check character matches on {sum(c.ecc_ok is True for c in checked)} of "
            f"{len(checked)} complete calls"
            if checked
            else "No complete call to check the error-check character on"
        )
        runs.append(
            _Run(
                entry,
                cand.label,
                "verified",
                found.p_value,
                f"{found.agree}/{found.pairs} repeats agree, {found.distinct} distinct",
                reason,
                proof=Proof(
                    kind="reencode",
                    detail=f"{found.agree} of {found.pairs} time-diversity copies agree on "
                    "characters whose three check bits re-derive from the seven information bits; "
                    f"a random pair is a valid equal pair with probability at most "
                    f"{dsc.RANDOM_PAIR:.1e}, corrected for {found.tried} polarity/boundary/phase "
                    "hypotheses",
                ),
                evidence=(
                    reason,
                    f"Chance of this many agreeing copies in a random stream: {found.p_value:.1e} "
                    f"(corrected over {found.tried} hypotheses)",
                    ecc_line,
                    *(
                        ()
                        if found.polarity_read
                        else (
                            "No call was read, and a complemented stream is also valid (each "
                            "symbol s reads as 127 - s), so the bit polarity is not settled: "
                            "upright is assumed",
                        )
                    ),
                    f"{found.characters} characters recovered from either copy, "
                    f"{found.erased} with neither copy valid",
                ),
                notes=tuple(notes),
                frames=_dsc_frames(found),
                key=cand.key,
                extra=_calls_parameter(found),
            )
        )
    return runs


def _dsc_frames(found: dsc.DscScan) -> tuple[Frame, ...]:
    """One frame per call, passing when every character was recovered and the error-check
    character matches; with no readable call, one frame over the stretch where copies agree,
    which passes because that agreement is this system's frame check and has passed (the frame
    holds no call to show)."""
    if found.calls:
        return tuple(
            Frame(
                index=i + 1,
                start_bit=c.start_bit,
                sync_word=f"format {c.format}",
                length_bits=c.length_bits,
                crc="pass" if c.ecc_ok else "fail",
                header_hex=f"{c.format:02X}",
                payload_hex="".join(f"{s or 0:02X}" for s in c.content),
            )
            for i, c in enumerate(found.calls[:MAX_FRAMES])
        )
    first, last = found.span
    return (
        Frame(
            index=1,
            start_bit=first,
            sync_word="DSC",
            length_bits=last - first,
            crc="pass",
            header_hex="",
            payload_hex="",
        ),
    )


def _calls_parameter(found: dsc.DscScan) -> tuple[Parameter, ...]:
    if not found.calls:
        return ()
    identity = [(c.format, c.content, c.eos) for c in found.calls]
    distinct = list(dict.fromkeys(identity))[:MAX_PAGES_SHOWN]
    lines: list[str] = []
    for fmt, content, eos in distinct:
        call = next(c for c in found.calls if (c.format, c.content, c.eos) == (fmt, content, eos))
        field = call.first_field
        ecc = {True: "ECC matches", False: "ECC does NOT match", None: "ECC not checked"}[
            call.ecc_ok
        ]
        lines.append(
            f"{call.format_name} (format {call.format}); "
            + (f"first field {field}; " if field else "")
            + f"content symbols {' '.join('?' if s is None else str(s) for s in content)}; "
            + f"EOS {eos} ({dsc.EOS[eos]}); {ecc}"
        )
    return (
        Parameter(
            id="calls",
            name="DSC calls",
            value=f"{len(found.calls)} call{'s' if len(found.calls) != 1 else ''} "
            f"({len(list(dict.fromkeys(identity)))} distinct)",
            level=E.HYPOTHESIS,
            method="Doubled format specifier, content, three EOS and the error-check character, "
            "read from the first transmissions (a damaged one replaced by its repetition)",
            evidence=tuple(lines),
            convention=(
                "The first five content symbols are shown as ten decimal digits (two per "
                "symbol), which is how an address or self-identity is coded but is not known to "
                "be one here; the meaning of the other fields is not decoded, and the calls are "
                "never used as evidence"
            ),
        ),
    )
