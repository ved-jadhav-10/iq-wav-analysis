from typing import Any

import pytest
from pydantic import ValidationError

from dsp.evidence import EvidenceLevel, Parameter, Proof, promote

CRC = Proof(kind="crc", detail="CRC-16/CCITT passed on 48 of 48 frames")


def make(**overrides: Any) -> Parameter:
    fields: dict[str, Any] = {
        "id": "rs",
        "name": "Symbol rate",
        "value": 25_000.0,
        "unit": "Bd",
        "uncertainty": 12.5,
        "level": EvidenceLevel.ESTIMATED,
        "confidence": 0.9,
        "method": "|x|² spectral line, refined by cyclic autocorrelation",
    }
    return Parameter.model_validate(fields | overrides)


def test_json_uses_the_frontend_field_names() -> None:
    data = make(resolve_hint=None).model_dump(mode="json")
    frontend_fields = {
        "id", "name", "value", "unit", "level", "confidence", "method",
        "evidence", "alternatives", "warnings", "resolveHint",
    }  # fmt: skip
    assert frontend_fields <= data.keys()
    assert Parameter.model_validate(data) == make()


def test_unknown_must_explain_itself() -> None:
    unknown = {"value": None, "uncertainty": None, "level": EvidenceLevel.UNKNOWN}
    with pytest.raises(ValidationError, match="state why"):
        make(**unknown)
    ok = make(**unknown, evidence=["No header"], resolve_hint="Enter the sample rate")
    assert ok.value is None


def test_unknown_cannot_carry_a_value() -> None:
    with pytest.raises(ValidationError, match="no value"):
        make(level=EvidenceLevel.UNKNOWN, evidence=["x"], resolve_hint="y")


def test_a_known_level_requires_a_value() -> None:
    with pytest.raises(ValidationError, match="report UNKNOWN instead"):
        make(value=None)


def test_estimated_numbers_need_an_uncertainty_but_labels_do_not() -> None:
    with pytest.raises(ValidationError, match="uncertainty"):
        make(uncertainty=None)
    assert make(value="QPSK", unit=None, uncertainty=None).value == "QPSK"


def test_verified_requires_proof_and_only_verified_has_one() -> None:
    with pytest.raises(ValidationError, match="requires a proof"):
        make(level=EvidenceLevel.VERIFIED)
    with pytest.raises(ValidationError, match="requires a proof"):
        make(proof=CRC)


@pytest.mark.parametrize(
    "overrides",
    [{"confidence": 1.2}, {"value": float("nan")}, {"uncertainty": -1.0}, {"method": ""}],
)
def test_out_of_range_or_empty_fields_are_rejected(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        make(**overrides)


def test_promotion_records_the_proof_as_evidence() -> None:
    hypothesis = make(value="QPSK", uncertainty=None, level=EvidenceLevel.HYPOTHESIS)
    verified = promote(hypothesis, CRC)
    assert verified.level is EvidenceLevel.VERIFIED
    assert verified.proof == CRC
    assert verified.evidence[-1] == f"Promoted from HYPOTHESIS by crc: {CRC.detail}"


def test_unknown_cannot_be_promoted() -> None:
    unknown = make(
        value=None,
        uncertainty=None,
        level=EvidenceLevel.UNKNOWN,
        evidence=["x"],
        resolve_hint="y",
    )
    with pytest.raises(ValueError, match="no value to verify"):
        promote(unknown, CRC)


def test_parameters_are_immutable() -> None:
    with pytest.raises(ValidationError):
        make().value = 1.0  # type: ignore[misc]
