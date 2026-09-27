"""The results document an analysis writes, and the JSON schema it is published under (PLAN §3, §7).

Every results JSON carries `schemaVersion` and an `Assumptions` block that states what the analysis
took as given about the recording. A breaking change to the schema is a major version bump.
"""

import json
from pathlib import Path
from typing import Any, Literal, Self, cast

from pydantic import Field, ModelWrapValidatorHandler, computed_field, model_validator

from dsp.evidence import CamelModel, Parameter, Value
from dsp.ingest.formats import SampleFormat

SchemaVersion = Literal["0.3.0"]
SCHEMA_VERSION: SchemaVersion = "0.3.0"
SCHEMA_PATH = Path(__file__).with_name("results.schema.json")


class Assumptions(CamelModel):
    """What the analysis took as given about the recording; every result and export carries it.

    Each entry is stated even when it is UNKNOWN, so nothing about the input is silently defaulted.
    """

    datatype: Parameter = Field(description="Sample format as a SigMF core:datatype.")
    data_offset: Parameter = Field(description="Byte offset of the first sample in the data file.")
    sample_rate: Parameter
    center_frequency: Parameter
    iq_order: Parameter | None = Field(
        description="'IQ' or 'QI'. Null only when the datatype is a known real-valued format."
    )

    @model_validator(mode="after")
    def _check(self) -> Self:
        for field in ("datatype", "data_offset", "sample_rate", "center_frequency", "iq_order"):
            param: Parameter | None = getattr(self, field)
            if param is not None and param.id != field:
                raise ValueError(f"the {field} assumption has id {param.id!r}")
        datatype = self.datatype.value
        is_real = isinstance(datatype, str) and not SampleFormat.parse(datatype).is_complex
        if is_real != (self.iq_order is None):
            raise ValueError("IQ order must be stated unless the datatype is real-valued")
        return self

    def parameters(self) -> tuple[Parameter, ...]:
        entries = (
            self.datatype,
            self.data_offset,
            self.sample_rate,
            self.center_frequency,
            self.iq_order,
        )
        return tuple(p for p in entries if p is not None)


class StageResult(CamelModel):
    """One stage's output. A stage that throws is FAILED with its error; the job carries on."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    status: Literal["done", "not-applicable", "failed"]
    summary: str = Field(min_length=1)
    parameters: tuple[Parameter, ...] = ()
    warnings: tuple[str, ...] = ()
    error: str | None = Field(default=None, description="Present exactly when status is failed.")

    @model_validator(mode="after")
    def _check(self) -> Self:
        if (self.status == "failed") != bool(self.error):
            raise ValueError("a failed stage states its error, and only a failed stage has one")
        if self.status == "not-applicable" and self.parameters:
            raise ValueError("a not-applicable stage reports no parameters")
        return self


class ReviewItem(CamelModel):
    """A value taken on a convention rather than evidence, for the analyst to confirm."""

    stage: str | None = Field(description="The stage that reported it; null for an assumption.")
    parameter: str = Field(description="The parameter's id.")
    name: str
    value: Value
    convention: str


class Results(CamelModel):
    """The results of analysing one recording.

    `needsReview` is derived from the parameters, never set by hand: it lists every value taken
    on a convention, so one field tells a reader or a script whether anything rests on a guess.
    """

    schema_version: SchemaVersion = SCHEMA_VERSION
    sanket_version: str = Field(min_length=1)
    assumptions: Assumptions
    stages: tuple[StageResult, ...]

    @computed_field(
        description="Every value taken on a convention rather than evidence, derived from the "
        "parameters. Empty when nothing rests on a convention."
    )
    @property
    def needs_review(self) -> tuple[ReviewItem, ...]:
        located = [(None, p) for p in self.assumptions.parameters()] + [
            (stage.id, p) for stage in self.stages for p in stage.parameters
        ]
        return tuple(
            ReviewItem(
                stage=stage, parameter=p.id, name=p.name, value=p.value, convention=p.convention
            )
            for stage, p in located
            if p.convention is not None and p.value is not None
        )

    @model_validator(mode="wrap")
    @classmethod
    def _derived_review(cls, data: Any, handler: ModelWrapValidatorHandler[Self]) -> Self:
        """needsReview is accepted on input only when it matches what the parameters say."""
        claimed: Any = None
        if isinstance(data, dict):
            fields = cast(dict[str, Any], data)
            claimed = fields.get("needsReview", fields.get("needs_review"))
            data = {k: v for k, v in fields.items() if k not in ("needsReview", "needs_review")}
        results = handler(data)
        if claimed is not None:
            items = cast(list[Any], claimed)
            if [ReviewItem.model_validate(item) for item in items] != list(results.needs_review):
                raise ValueError("needsReview doesn't match the conventions in the parameters")
        return results

    @model_validator(mode="after")
    def _check(self) -> Self:
        ids = [stage.id for stage in self.stages]
        if len(ids) != len(set(ids)):
            raise ValueError(f"stage ids must be unique: {ids}")
        return self

    def to_json(self) -> str:
        """Deterministic JSON: the same results always give the same bytes."""
        return self.model_dump_json(indent=2) + "\n"


def results_schema() -> dict[str, Any]:
    schema = Results.model_json_schema(mode="serialization")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Sanket results",
        **{key: value for key, value in schema.items() if key != "title"},
    }


def schema_json() -> str:
    return json.dumps(results_schema(), indent=2, ensure_ascii=False) + "\n"
