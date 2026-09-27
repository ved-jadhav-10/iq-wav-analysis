"""The results document an analysis writes, and the JSON schema it is published under (PLAN §3, §7).

Every results JSON carries `schemaVersion` and an `Assumptions` block that states what the analysis
took as given about the recording. A breaking change to the schema is a major version bump.
"""

import json
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from dsp.evidence import CamelModel, Parameter
from dsp.ingest.formats import SampleFormat

SchemaVersion = Literal["0.2.0"]
SCHEMA_VERSION: SchemaVersion = "0.2.0"
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


class Results(CamelModel):
    """The results of analysing one recording."""

    schema_version: SchemaVersion = SCHEMA_VERSION
    sanket_version: str = Field(min_length=1)
    assumptions: Assumptions
    stages: tuple[StageResult, ...]

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
