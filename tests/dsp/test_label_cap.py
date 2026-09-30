"""The HYPOTHESIS cap on digital labels from recordings that can't carry them (PLAN M2 gate)."""

import pytest

from dsp.evidence import EvidenceLevel, Parameter, Proof
from dsp.report import DetectionReport, Frame, StageReport, cap_digital_labels, note_rate_basis

E = EvidenceLevel
REASON = "Lossy audio distorts the phase that digital demodulation relies on"


def param(id: str, level: EvidenceLevel, **fields: object) -> Parameter:
    extra: dict[str, object] = {}
    if level is E.VERIFIED:
        extra["proof"] = Proof(kind="crc", detail="CRC-16 passes on 9 of 9 frames")
    if level is E.ESTIMATED:
        extra["uncertainty"] = 1.0
    return Parameter.model_validate(
        {"id": id, "name": id, "value": 4.0, "level": level, "method": "test", **extra, **fields}
    )


def stage(id: str, level: EvidenceLevel, *params: Parameter) -> StageReport:
    return StageReport(id=id, name=id, status="done", summary=id, level=level, parameters=params)


def report(kind: str, *, verified: bool = False) -> DetectionReport:
    top = E.VERIFIED if verified else E.ESTIMATED
    frame = Frame(
        index=1, start_bit=0, sync_word="ASM", length_bits=64, crc="pass", header_hex="00",
        payload_hex="ab",
    )  # fmt: skip
    return DetectionReport(
        label="QPSK",
        kind=kind,  # type: ignore[arg-type]
        level=top,
        headline="QPSK",
        stages=(
            stage("detect", E.ESTIMATED, param("centre", E.ESTIMATED)),
            stage(
                "classify",
                top,
                param("modulation", top),
                param("rate", E.MEASURED),
                param("rotation", E.HYPOTHESIS),
            ),
        ),
        search=None,
        no_search_reason="not run",
        frames=(frame,) if verified else (),
        no_frames_reason=None if verified else "none",
    )


def levels(r: DetectionReport, stage: str) -> dict[str, EvidenceLevel]:
    s = next(s for s in r.stages if s.id == stage)
    return {p.id: p.level for p in s.parameters}


def test_estimated_and_measured_digital_labels_drop_to_hypothesis_with_the_reason() -> None:
    capped = cap_digital_labels(report("psk"), REASON)
    assert levels(capped, "classify") == {
        "modulation": E.HYPOTHESIS, "rate": E.HYPOTHESIS, "rotation": E.HYPOTHESIS,
    }  # fmt: skip
    assert capped.level is E.HYPOTHESIS
    classify = next(s for s in capped.stages if s.id == "classify")
    assert classify.level is E.HYPOTHESIS
    assert all(REASON in p.warnings for p in classify.parameters if p.id != "rotation")
    assert "capped at HYPOTHESIS" in capped.headline


def test_the_detect_stage_is_the_band_not_a_label_and_stays() -> None:
    capped = cap_digital_labels(report("psk"), REASON)
    assert levels(capped, "detect") == {"centre": E.ESTIMATED}


def test_a_crc_verified_chain_stays_verified() -> None:
    capped = cap_digital_labels(report("psk", verified=True), REASON)
    assert capped.level is E.VERIFIED
    assert levels(capped, "classify")["modulation"] is E.VERIFIED
    assert levels(capped, "classify")["rate"] is E.HYPOTHESIS


@pytest.mark.parametrize("kind", ["analog", "cw", "unknown"])
def test_signals_that_are_not_digital_are_left_alone(kind: str) -> None:
    original = report(kind)
    assert cap_digital_labels(original, REASON) == original


def with_units() -> DetectionReport:
    rate = param("symbol_rate", E.ESTIMATED, unit="Bd")
    carrier = param("carrier", E.ESTIMATED, unit="Hz")
    snr = param("snr", E.ESTIMATED, unit="dB")
    return DetectionReport(
        label="QPSK",
        kind="psk",
        level=E.ESTIMATED,
        headline="QPSK",
        stages=(stage("estimate", E.ESTIMATED, rate, carrier, snr),),
        search=None,
        no_search_reason="not run",
        no_frames_reason="none",
    )


def test_values_in_hertz_and_baud_carry_the_inferred_rate_as_their_basis() -> None:
    noted = note_rate_basis(with_units(), "Rests on an inferred rate")
    by_id = {p.id: p for p in noted.stages[0].parameters}
    assert by_id["carrier"].warnings == ("Rests on an inferred rate",)
    assert by_id["snr"].warnings == ()  # dB does not depend on the sample rate
    assert by_id["symbol_rate"].warnings[0] == "Rests on an inferred rate"
    assert "does not confirm that rate independently" in by_id["symbol_rate"].warnings[1]
    assert all(p.level is E.ESTIMATED for p in by_id.values())  # noted, not lowered
