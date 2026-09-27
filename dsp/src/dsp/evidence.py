"""The evidence model: every value Sanket reports is a Parameter (PLAN §3).

The honesty rules are enforced when a Parameter is built, so a result that breaks them can't
exist: UNKNOWN states why and what would settle it, an ESTIMATED number carries its
uncertainty, and VERIFIED requires a CRC, sync-recurrence or re-encode proof.
"""

from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class EvidenceLevel(StrEnum):
    VERIFIED = "VERIFIED"
    MEASURED = "MEASURED"
    ESTIMATED = "ESTIMATED"
    HYPOTHESIS = "HYPOTHESIS"
    UNKNOWN = "UNKNOWN"


class CamelModel(BaseModel):
    """Immutable, strict about unknown fields, and camelCase in JSON to match the frontend."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        # Every field is always written, so the published schema marks every field required.
        json_schema_serialization_defaults_required=True,
    )


Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
Value = int | FiniteFloat | str


class Alternative(CamelModel):
    value: Value
    confidence: Confidence | None = Field(
        default=None,
        description="Null when candidates are ranked without a calibrated probability.",
    )


class Proof(CamelModel):
    kind: Literal["crc", "sync_recurrence", "reencode"]
    detail: str = Field(min_length=1)


# The honesty rules restated in JSON Schema, so a consumer that doesn't use this model still
# enforces them. They must agree with Parameter._check_honesty; tests check both on the same cases.
_HONESTY_SCHEMA: dict[str, Any] = {
    "allOf": [
        {
            "if": {"properties": {"level": {"const": "UNKNOWN"}}},
            "then": {
                "properties": {
                    "value": {"type": "null"},
                    "evidence": {"minItems": 1},
                    "resolveHint": {"type": "string", "minLength": 1},
                }
            },
            "else": {"properties": {"value": {"not": {"type": "null"}}}},
        },
        {
            "if": {"properties": {"level": {"const": "ESTIMATED"}, "value": {"type": "number"}}},
            "then": {"properties": {"uncertainty": {"type": "number"}}},
        },
        {
            "if": {"properties": {"level": {"const": "VERIFIED"}}},
            "then": {"properties": {"proof": {"type": "object"}}},
            "else": {"properties": {"proof": {"type": "null"}}},
        },
        {
            "if": {"properties": {"convention": {"type": "string"}}},
            "then": {"properties": {"level": {"const": "HYPOTHESIS"}}},
        },
    ]
}


class Parameter(CamelModel):
    """A reported value with its evidence level, method and evidence.

    UNKNOWN has no value and states why and what would settle it; an ESTIMATED number carries
    its uncertainty; VERIFIED, and only VERIFIED, carries a CRC, sync-recurrence or re-encode proof.
    A value the evidence can't decide, taken on a stated convention instead, is a HYPOTHESIS that
    names the convention; results list every such value under needsReview.
    """

    model_config = ConfigDict(json_schema_extra=_HONESTY_SCHEMA)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    value: Value | None
    unit: str | None = None
    uncertainty: FiniteFloat | None = Field(
        default=None, ge=0.0, description="Standard uncertainty (1 sigma), in the value's unit."
    )
    level: EvidenceLevel
    confidence: Confidence | None = None
    method: str = Field(min_length=1)
    evidence: tuple[str, ...] = ()
    alternatives: tuple[Alternative, ...] = ()
    warnings: tuple[str, ...] = ()
    resolve_hint: str | None = Field(
        default=None, description="For UNKNOWN: what additional input would settle it."
    )
    proof: Proof | None = None
    convention: str | None = Field(
        default=None,
        min_length=1,
        description="Set when the evidence can't decide and the value follows a stated convention "
        "instead: the convention and why an analyst should review it. Only on HYPOTHESIS.",
    )

    @model_validator(mode="after")
    def _check_honesty(self) -> Self:
        if self.level is EvidenceLevel.UNKNOWN:
            if self.value is not None:
                raise ValueError("an UNKNOWN parameter has no value")
            if not self.evidence or not self.resolve_hint:
                raise ValueError("UNKNOWN must state why (evidence) and what would settle it")
        elif self.value is None:
            raise ValueError(f"{self.level} requires a value; report UNKNOWN instead")
        is_number = isinstance(self.value, int | float)
        if self.level is EvidenceLevel.ESTIMATED and is_number and self.uncertainty is None:
            raise ValueError("an ESTIMATED number must state its uncertainty")
        if (self.level is EvidenceLevel.VERIFIED) != (self.proof is not None):
            raise ValueError("VERIFIED requires a proof, and only VERIFIED carries one")
        if self.convention is not None and self.level is not EvidenceLevel.HYPOTHESIS:
            raise ValueError("a value taken on a convention is a HYPOTHESIS")
        return self


def promote(parameter: Parameter, proof: Proof) -> Parameter:
    """Raise a value to VERIFIED on downstream proof, recording the promotion as evidence.

    Proof settles a value taken on a convention, so the convention is recorded and cleared.
    """
    if parameter.level is EvidenceLevel.UNKNOWN:
        raise ValueError("an UNKNOWN parameter has no value to verify")
    note = f"Promoted from {parameter.level} by {proof.kind}: {proof.detail}"
    if parameter.convention:
        note += f" (it had been taken on a convention: {parameter.convention})"
    return Parameter.model_validate(
        {
            **parameter.model_dump(),
            "level": EvidenceLevel.VERIFIED,
            "proof": proof,
            "evidence": (*parameter.evidence, note),
            "convention": None,
        }
    )
