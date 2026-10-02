import json
from pathlib import Path
from typing import Any, get_args

import numpy as np
import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from bench.sniffer import COMPLEX_SIGNALS
from dsp.evidence import EvidenceLevel, Parameter, Proof, promote
from dsp.findings import Frame, Hypothesis, HypothesisSearch
from dsp.ingest.formats import SampleFormat
from dsp.ingest.raw import read_raw
from dsp.ingest.sigmf import read_sigmf
from dsp.results import (
    NO_FILES,
    SCHEMA_PATH,
    SCHEMA_VERSION,
    Assumptions,
    Results,
    SchemaVersion,
    Signal,
    StageResult,
    schema_json,
)

SCHEMA: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)
PARAMETER_VALIDATOR = Draft202012Validator({"$defs": SCHEMA["$defs"], "$ref": "#/$defs/Parameter"})


def sigmf(tmp_path: Path, global_: dict[str, Any]) -> Assumptions:
    meta = tmp_path / "rec.sigmf-meta"
    meta.write_text(json.dumps({"global": global_}), encoding="utf-8")
    (tmp_path / "rec.sigmf-data").write_bytes(bytes(64))
    return read_sigmf(meta).assumptions


@pytest.fixture
def results(tmp_path: Path) -> Results:
    assumptions = sigmf(tmp_path, {"core:datatype": "ci16_le", "core:sample_rate": 250_000})
    ingest = StageResult(
        id="ingest",
        name="Ingest",
        status="done",
        summary="SigMF ci16_le at 250 kS/s",
        parameters=(assumptions.datatype, assumptions.sample_rate),
    )
    detect = StageResult(
        id="detect", name="Detect", status="failed", summary="Detection failed", error="boom"
    )
    return Results(
        sanket_version="0.1.0",
        recording=NO_FILES,
        catalogues=(),
        assumptions=assumptions,
        stages=(ingest, detect),
    )


def a_signal(stages: tuple[StageResult, ...] = (), **changes: Any) -> Signal:
    """A signal with no search and no frames, each stating why, unless `changes` say otherwise."""
    fields: dict[str, Any] = {
        "id": "signal_0",
        "label": "QPSK",
        "kind": "psk",
        "level": EvidenceLevel.ESTIMATED,
        "headline": "QPSK, no frames",
        "stages": stages,
        "search": None,
        "no_search_reason": "No search ran.",
        "frames": (),
        "no_frames_reason": "No frames found.",
    }
    return Signal.model_validate(fields | changes)


def test_committed_schema_is_current() -> None:
    assert SCHEMA_PATH.read_text(encoding="utf-8") == schema_json(), (
        "results.schema.json is stale: run `uv run python tools/results_schema.py`"
    )
    Draft202012Validator.check_schema(SCHEMA)


def test_schema_version_constant_matches_its_type() -> None:
    assert get_args(SchemaVersion) == (SCHEMA_VERSION,)
    assert SCHEMA["properties"]["schemaVersion"]["const"] == SCHEMA_VERSION


def test_results_json_matches_the_schema_and_round_trips(results: Results) -> None:
    text = results.to_json()
    data = json.loads(text)
    VALIDATOR.validate(data)
    assert data["schemaVersion"] == SCHEMA_VERSION
    assert data["assumptions"]["sampleRate"]["value"] == 250_000.0
    assert Results.model_validate_json(text) == results
    assert Results.model_validate_json(text).to_json() == text


def test_schema_rejects_a_document_without_assumptions(results: Results) -> None:
    data = json.loads(results.to_json())
    del data["assumptions"]
    assert not VALIDATOR.is_valid(data)
    with pytest.raises(ValidationError):
        Results.model_validate(data)


def test_wrong_schema_version_is_rejected(results: Results) -> None:
    data = json.loads(results.to_json()) | {"schemaVersion": "9.9.9"}
    assert not VALIDATOR.is_valid(data)
    with pytest.raises(ValidationError):
        Results.model_validate(data)


VALID_PARAMETER: dict[str, Any] = {
    "id": "rs",
    "name": "Symbol rate",
    "value": 25_000.0,
    "unit": "Bd",
    "uncertainty": 12.5,
    "level": "ESTIMATED",
    "confidence": 0.9,
    "method": "|x|² spectral line",
    "evidence": [],
    "alternatives": [],
    "warnings": [],
    "resolveHint": None,
    "proof": None,
    "convention": None,
}
CRC = {"kind": "crc", "detail": "CRC-16 passed on 48 of 48 frames"}
UNKNOWN = {"value": None, "uncertainty": None, "level": "UNKNOWN"}


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param(UNKNOWN | {"evidence": ["No header"]}, id="unknown-without-hint"),
        pytest.param(UNKNOWN | {"resolveHint": "Enter it"}, id="unknown-without-evidence"),
        pytest.param(
            UNKNOWN | {"value": 1.0, "evidence": ["x"], "resolveHint": "y"}, id="unknown-with-value"
        ),
        pytest.param({"value": None}, id="known-level-without-value"),
        pytest.param({"uncertainty": None}, id="estimated-number-without-uncertainty"),
        pytest.param({"level": "VERIFIED"}, id="verified-without-proof"),
        pytest.param({"proof": CRC}, id="proof-without-verified"),
        pytest.param({"confidence": 1.5}, id="confidence-out-of-range"),
        pytest.param({"extra": 1}, id="unknown-field"),
        pytest.param({"convention": "Most tools do this"}, id="convention-not-hypothesis"),
    ],
)
def test_schema_and_model_both_enforce_the_honesty_rules(overrides: dict[str, Any]) -> None:
    data = VALID_PARAMETER | overrides
    assert not PARAMETER_VALIDATOR.is_valid(data)
    with pytest.raises(ValidationError):
        Parameter.model_validate(data)


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({}, id="estimated-number"),
        pytest.param({"value": "QPSK", "uncertainty": None}, id="estimated-label"),
        pytest.param({"level": "VERIFIED", "proof": CRC}, id="verified-with-proof"),
        pytest.param(
            UNKNOWN | {"evidence": ["No header"], "resolveHint": "Enter it"}, id="unknown"
        ),
        pytest.param(
            {"value": "IQ", "uncertainty": None, "level": "HYPOTHESIS", "convention": "I first"},
            id="hypothesis-on-a-convention",
        ),
    ],
)
def test_schema_and_model_both_accept_honest_parameters(overrides: dict[str, Any]) -> None:
    data = VALID_PARAMETER | overrides
    PARAMETER_VALIDATOR.validate(data)
    assert Parameter.model_validate(data).model_dump(mode="json") == data


def test_sigmf_complex_iq_order_is_a_stated_hypothesis(tmp_path: Path) -> None:
    iq = sigmf(tmp_path, {"core:datatype": "cf32_le"}).iq_order
    assert iq is not None
    assert (iq.value, iq.level) == ("IQ", EvidenceLevel.HYPOTHESIS)


def test_sigmf_real_samples_have_no_iq_order(tmp_path: Path) -> None:
    assert sigmf(tmp_path, {"core:datatype": "rf32_le"}).iq_order is None


def test_sigmf_unknown_datatype_leaves_everything_unknown(tmp_path: Path) -> None:
    assumptions = sigmf(tmp_path, {})
    for param in (
        assumptions.datatype,
        assumptions.sample_rate,
        assumptions.center_frequency,
        assumptions.iq_order,
    ):
        assert param is not None
        assert param.level is EvidenceLevel.UNKNOWN
        assert param.evidence and param.resolve_hint


def test_iq_order_must_be_stated_for_complex_data(tmp_path: Path) -> None:
    fields = sigmf(tmp_path, {"core:datatype": "cf32_le"}).model_dump(by_alias=False)
    with pytest.raises(ValidationError, match="IQ order must be stated"):
        Assumptions.model_validate(fields | {"iq_order": None})


def test_assumption_ids_match_their_slot(tmp_path: Path) -> None:
    fields = sigmf(tmp_path, {"core:datatype": "cu8"}).model_dump(by_alias=False)
    swapped = fields | {"sample_rate": fields["center_frequency"]}
    with pytest.raises(ValidationError, match="has id 'center_frequency'"):
        Assumptions.model_validate(swapped)


@pytest.mark.parametrize(
    ("status", "error", "parameters"),
    [("failed", None, ()), ("done", "boom", ()), ("not-applicable", None, None)],
)
def test_stage_status_rules(
    tmp_path: Path, status: str, error: str | None, parameters: tuple[Parameter, ...] | None
) -> None:
    if parameters is None:
        parameters = (sigmf(tmp_path, {"core:datatype": "cu8"}).datatype,)
    with pytest.raises(ValidationError):
        StageResult.model_validate(
            {"id": "x", "name": "X", "status": status, "summary": "s", "error": error}
            | {"parameters": parameters}
        )


def test_stage_ids_are_unique(results: Results) -> None:
    with pytest.raises(ValidationError, match="unique"):
        Results.model_validate(results.model_dump() | {"stages": results.stages * 2})


def raw_results(tmp_path: Path, datatype: str = "ci16_le") -> Results:
    x = COMPLEX_SIGNALS["noise"](np.random.default_rng(0), 16384) * 0.05
    path = tmp_path / "capture.bin"
    path.write_bytes(SampleFormat.parse(datatype).encode(x))
    return Results(
        sanket_version="0.1.0",
        recording=NO_FILES,
        catalogues=(),
        assumptions=read_raw(path).assumptions,
        stages=(),
    )


def test_needs_review_lists_every_value_taken_on_a_convention(tmp_path: Path) -> None:
    results = raw_results(tmp_path)
    items = {(item.stage, item.parameter) for item in results.needs_review}
    # Noise can't tell complex from real, and a raw file states neither its header nor IQ order.
    assert items == {(None, "datatype"), (None, "data_offset"), (None, "iq_order")}
    data = json.loads(results.to_json())
    VALIDATOR.validate(data)
    assert [item["parameter"] for item in data["needsReview"]] == [
        "datatype",
        "data_offset",
        "iq_order",
    ]
    assert Results.model_validate(data) == results


def test_needs_review_is_empty_when_everything_rests_on_evidence(results: Results) -> None:
    assert results.needs_review == ()
    assert json.loads(results.to_json())["needsReview"] == []


def test_needs_review_includes_stage_parameters(results: Results) -> None:
    guess = Parameter(
        id="rotation",
        name="Phase rotation",
        value=0,
        unit="deg",
        level=EvidenceLevel.HYPOTHESIS,
        method="Carried forward",
        convention="The first rotation is kept until sync resolves it.",
    )
    stage = StageResult(id="demod", name="Demod", status="done", summary="s", parameters=(guess,))
    edited = results.model_dump(exclude={"needs_review"}) | {"stages": (*results.stages, stage)}
    updated = Results.model_validate(edited)
    assert [(i.stage, i.parameter, i.value) for i in updated.needs_review] == [
        ("demod", "rotation", 0)
    ]


def test_a_needs_review_list_that_disagrees_with_the_parameters_is_rejected(
    tmp_path: Path,
) -> None:
    data = json.loads(raw_results(tmp_path).to_json())
    data["needsReview"] = data["needsReview"][:1]  # hides two conventions
    with pytest.raises(ValidationError, match="doesn't match"):
        Results.model_validate(data)


def test_signal_stage_ids_must_be_unique() -> None:
    detect = StageResult(id="detect", name="Detect", status="done", summary="Found", parameters=())
    with pytest.raises(ValidationError, match="unique"):
        a_signal((detect, detect))


def test_results_signal_ids_must_be_unique(results: Results) -> None:
    signal = a_signal()
    with pytest.raises(ValidationError, match="signal ids must be unique"):
        Results.model_validate(results.model_dump() | {"signals": (signal, signal)})


def test_needs_review_includes_signal_parameters(results: Results) -> None:
    guess = Parameter(
        id="center_frequency",
        name="Centre frequency",
        value=0.1,
        unit="cycles/sample",
        level=EvidenceLevel.HYPOTHESIS,
        method="Carried forward",
        convention="Taken from the stronger of two tied candidates.",
    )
    detect = StageResult(
        id="detect", name="Detect", status="done", summary="s", parameters=(guess,)
    )
    signal = a_signal((detect,))
    edited = results.model_dump(exclude={"needs_review"}) | {"signals": (signal,)}
    updated = Results.model_validate(edited)
    assert [(i.signal, i.stage, i.parameter, i.value) for i in updated.needs_review] == [
        ("signal_0", "detect", "center_frequency", 0.1)
    ]
    data = json.loads(updated.to_json())
    VALIDATOR.validate(data)
    assert Results.model_validate(data) == updated


def test_promotion_clears_the_convention_and_records_it() -> None:
    guess = Parameter.model_validate(
        VALID_PARAMETER
        | {"value": "IQ", "uncertainty": None, "level": "HYPOTHESIS", "convention": "I first"}
    )
    verified = promote(guess, Proof(kind="crc", detail="CRC-16 passed on 12 of 12 frames"))
    assert verified.convention is None
    assert "taken on a convention: I first" in verified.evidence[-1]


def frame(index: int, crc: str) -> Frame:
    return Frame.model_validate(
        {
            "index": index,
            "start_bit": 64 * index,
            "sync_word": "1ACFFC1D",
            "length_bits": 64,
            "crc": crc,
            "header_hex": "00 01",
            "payload_hex": "CAFE",
        }
    )


def ledger() -> HypothesisSearch:
    def row(layer: str, candidate: str, outcome: str) -> Hypothesis:
        return Hypothesis.model_validate(
            {
                "layer": layer,
                "candidate": candidate,
                "statistic": "CRC passes 12 of 12",
                "p_value": 1e-30 if outcome == "accepted" else None,
                "threshold": 1e-6,
                "outcome": outcome,
                "reason": "Check passed" if outcome == "accepted" else "Not tried",
            }
        )

    return HypothesisSearch(
        tried=3,
        alpha=0.01,
        correction="Holm",
        smallest_threshold=0.0033,
        shuffled_runs=3,
        shuffled_accepts=0,
        match_tried=1,
        rows=(row("Framing", "ASM", "accepted"), row("Match", "POCSAG", "rejected")),
    )


def test_a_signal_carries_its_headline_ledger_and_frames_through_the_schema(
    results: Results,
) -> None:
    one = a_signal(
        level=EvidenceLevel.VERIFIED,
        headline="QPSK, 2 frames, 1 CRC pass",
        search=ledger(),
        no_search_reason=None,
        frames=(frame(1, "pass"), frame(2, "fail")),
        no_frames_reason=None,
    )
    full = Results.model_validate(
        results.model_dump(exclude={"needs_review"}) | {"signals": (one,)}
    )
    text = full.to_json()
    data = json.loads(text)
    VALIDATOR.validate(data)
    (written,) = data["signals"]
    assert (written["label"], written["kind"], written["level"]) == ("QPSK", "psk", "VERIFIED")
    assert written["headline"] == "QPSK, 2 frames, 1 CRC pass"
    assert [f["crc"] for f in written["frames"]] == ["pass", "fail"]
    assert written["search"]["matchTried"] == 1
    assert [(r["layer"], r["outcome"]) for r in written["search"]["rows"]] == [
        ("Framing", "accepted"),
        ("Match", "rejected"),
    ]
    assert written["noSearchReason"] is None and written["noFramesReason"] is None
    assert Results.model_validate_json(text) == full
    assert Results.model_validate_json(text).to_json() == text


def test_a_signal_without_findings_is_rejected_by_the_model_and_the_schema(
    results: Results,
) -> None:
    data = json.loads(
        Results.model_validate(
            results.model_dump(exclude={"needs_review"}) | {"signals": (a_signal(),)}
        ).to_json()
    )
    VALIDATOR.validate(data)
    for field in ("label", "kind", "level", "headline", "search", "frames"):
        broken = json.loads(json.dumps(data))
        del broken["signals"][0][field]
        assert not VALIDATOR.is_valid(broken), field
        if field != "frames":  # the model defaults an absent frame table to none
            with pytest.raises(ValidationError):
                Results.model_validate(broken)


def test_a_signals_findings_keep_their_honesty_rules() -> None:
    many = tuple(frame(i + 1, "pass") for i in range(501))
    with pytest.raises(ValidationError, match="a VERIFIED signal needs"):
        a_signal(level=EvidenceLevel.VERIFIED)
    with pytest.raises(ValidationError, match="a VERIFIED signal needs"):
        a_signal(level=EvidenceLevel.VERIFIED, frames=(frame(1, "fail"),), no_frames_reason=None)
    with pytest.raises(ValidationError, match="no frames states why"):
        a_signal(no_frames_reason=None)
    with pytest.raises(ValidationError, match="no frames states why"):
        a_signal(frames=(frame(1, "pass"),))
    with pytest.raises(ValidationError, match="a missing search states why"):
        a_signal(no_search_reason=None)
    with pytest.raises(ValidationError, match="a missing search states why"):
        a_signal(search=ledger())
    with pytest.raises(ValidationError, match="at most 500"):
        a_signal(frames=many, no_frames_reason=None)


def test_the_schema_bounds_the_frame_table(results: Results) -> None:
    one = a_signal(frames=(frame(1, "pass"),), no_frames_reason=None)
    data = json.loads(
        Results.model_validate(
            results.model_dump(exclude={"needs_review"}) | {"signals": (one,)}
        ).to_json()
    )
    VALIDATOR.validate(data)
    data["signals"][0]["frames"] = data["signals"][0]["frames"] * 501
    assert not VALIDATOR.is_valid(data)
