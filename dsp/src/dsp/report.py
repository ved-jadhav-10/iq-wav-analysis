"""The per-detection analysis report (PLAN M3-M6): what `dsp.analyse.analyse` returns for
one detected signal, and what the backend sends as `RecordingInfo.detections[i].analysis`.

It mirrors the frontend's `Detection` shape (`frontend/src/lib/analysis.ts`), so the existing
panels (pipeline rail, evidence, ledger, frames, constellation) draw a real detection unchanged.
"""

from typing import Any, Self

from pydantic import Field, model_validator

from dsp.evidence import CamelModel, EvidenceLevel, FiniteFloat, Parameter, revise
from dsp.findings import Frame as Frame
from dsp.findings import Hypothesis as Hypothesis
from dsp.findings import HypothesisSearch as HypothesisSearch
from dsp.findings import SignalFindings
from dsp.findings import SignalKind as SignalKind
from dsp.results import StageResult

MAX_CONSTELLATION_POINTS = 2048


class StageReport(StageResult):
    """A stage result with the level the pipeline rail shows for it: the level of the stage's
    headline finding, or null for a not-applicable stage."""

    level: EvidenceLevel | None = None

    @model_validator(mode="after")
    def _check_level(self) -> Self:
        if self.status == "not-applicable" and self.level is not None:
            raise ValueError("a not-applicable stage has no level")
        return self


class Eye(CamelModel):
    """Eye diagram of a linear signal: the matched-filter output around each of a spread of
    symbols, over one symbol either side, after the accepted carrier correction, scaled so the
    samples at the symbol instants have unit RMS. Each trace has `2 * samples_per_symbol + 1`
    points from -1 to +1 symbols."""

    samples_per_symbol: int = Field(ge=1)
    i: tuple[tuple[FiniteFloat, ...], ...]
    q: tuple[tuple[FiniteFloat, ...], ...]

    @model_validator(mode="after")
    def _check(self) -> Self:
        width = 2 * self.samples_per_symbol + 1
        if len(self.i) != len(self.q) or any(len(t) != width for t in (*self.i, *self.q)):
            raise ValueError(f"every eye trace has {width} points, in I and Q alike")
        return self


class DetectionReport(SignalFindings):
    stages: tuple[StageReport, ...]
    constellation: tuple[tuple[FiniteFloat, FiniteFloat], ...] = Field(
        default=(),
        description="Symbol-spaced (I, Q) points after sync and phase correction, unit RMS, at "
        f"most {MAX_CONSTELLATION_POINTS}. Empty when no symbols were recovered, or for a "
        "signal that isn't PSK.",
    )
    eye: Eye | None = Field(
        default=None, description="Null for a signal that has no matched-filter symbols."
    )

    @model_validator(mode="after")
    def _check(self) -> Self:
        if len(self.constellation) > MAX_CONSTELLATION_POINTS:
            raise ValueError(f"at most {MAX_CONSTELLATION_POINTS} constellation points")
        ids = [s.id for s in self.stages]
        if len(ids) != len(set(ids)):
            raise ValueError(f"stage ids must be unique: {ids}")
        return self


_CAPPED_LEVELS = frozenset({EvidenceLevel.MEASURED, EvidenceLevel.ESTIMATED})


def cap_digital_labels(report: DetectionReport, reason: str) -> DetectionReport:
    """A digital signal's labels capped at HYPOTHESIS, for a recording whose samples can't carry
    them reliably (a real-valued channel has no quadrature; lossy audio distorts the phase).

    Only MEASURED and ESTIMATED values are lowered, each with `reason` as a warning. The detect
    stage stays (it is where the band is, not what it carries), and so does a VERIFIED value: a
    CRC pass is proof on the decoded bits whatever the audio did to the samples on the way.
    Analog and unclassified signals are left as they are.
    """
    if report.kind not in ("psk", "fsk"):
        return report
    stages = tuple(s if s.id == "detect" else _capped_stage(s, reason) for s in report.stages)
    if stages == report.stages:
        return report
    return _revised(
        report,
        stages=stages,
        level=EvidenceLevel.HYPOTHESIS if report.level in _CAPPED_LEVELS else report.level,
        headline=f"{report.headline} (labels capped at HYPOTHESIS)",
    )


def _capped_stage(stage: StageReport, reason: str) -> StageReport:
    parameters = tuple(
        revise(p, level=EvidenceLevel.HYPOTHESIS, warnings=(*p.warnings, reason))
        if p.level in _CAPPED_LEVELS
        else p
        for p in stage.parameters
    )
    level = EvidenceLevel.HYPOTHESIS if stage.level in _CAPPED_LEVELS else stage.level
    return _revised(stage, parameters=parameters, level=level)


def _revised[M: CamelModel](model: M, **changes: Any) -> M:
    """A validated copy (`model_copy(update=...)` would skip the validators)."""
    return type(model).model_validate({**model.model_dump(by_alias=False), **changes})


_RATE_UNITS = frozenset({"Hz", "Bd", "s"})


def note_rate_basis(report: DetectionReport, note: str) -> DetectionReport:
    """Every value in hertz, baud or seconds carries `note`, for a report computed from a sample
    rate that is itself only a HYPOTHESIS (a structural match): those units are the normalised
    values times that rate, so they are no firmer than it. The symbol rate also says it cannot
    confirm the rate, which was chosen because it matches a recognised one."""
    circular = (
        "The sample rate was chosen because this symbol rate matches a recognised one, so this "
        "value does not confirm that rate independently."
    )

    def noted(p: Parameter) -> Parameter:
        if p.unit not in _RATE_UNITS:
            return p
        extra = (note, circular) if p.id == "symbol_rate" else (note,)
        return revise(p, warnings=(*p.warnings, *extra))

    stages = tuple(
        _revised(s, parameters=tuple(noted(p) for p in s.parameters)) for s in report.stages
    )
    return report if stages == report.stages else _revised(report, stages=stages)
