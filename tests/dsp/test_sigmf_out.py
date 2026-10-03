"""SigMF out (PLAN M7): what the results may put in standard fields, and what they refuse."""

from typing import Any

import pytest

from dsp.evidence import EvidenceLevel
from dsp.findings import Frame
from dsp.results import Results, Signal, StageResult
from dsp.sigmf_out import SigmfRefused, annotations, meta_for, render_meta

from .conftest import assumptions, build_results, param


def with_assumptions(results: Results, **fields: Any) -> Results:
    base = {n: getattr(results.assumptions, n) for n in type(results.assumptions).model_fields}
    return results.model_copy(
        update={"assumptions": type(results.assumptions).model_validate({**base, **fields})}
    )


def detected(results: Results, **values: float) -> Results:
    """The sample signal with a detect stage holding a span and a band."""
    defaults = {
        "start_sample": 1000,
        "stop_sample": 5000,
        "center_frequency": 0.2,
        "bandwidth": 0.1,
    }
    stage = StageResult(
        id="detect",
        name="Detect",
        status="done",
        summary="d",
        parameters=tuple(
            param(k, EvidenceLevel.ESTIMATED, v, uncertainty=1.0)
            for k, v in {**defaults, **values}.items()
        ),
    )
    signal = results.signals[0]
    frame = Frame(
        index=1,
        start_bit=0,
        sync_word="1ACFFC1D",
        length_bits=64,
        crc="pass",
        header_hex="12",
        payload_hex="0A",
    )
    rebuilt = Signal(
        id=signal.id,
        label="QPSK",
        kind="psk",
        level=EvidenceLevel.VERIFIED,
        headline="QPSK, CCSDS frames",
        stages=(stage, *signal.stages),
        search=None,
        no_search_reason="none",
        frames=(frame,),
        no_frames_reason=None,
    )
    return results.model_copy(update={"signals": (rebuilt,)})


def firm_rate(results: Results) -> Results:
    return with_assumptions(
        results,
        sample_rate=param("sample_rate", EvidenceLevel.MEASURED, 1e6, unit="S/s"),
        center_frequency=param("center_frequency", EvidenceLevel.MEASURED, 1e8, unit="Hz"),
    )


def test_a_signal_becomes_an_annotation_with_its_span_and_band_in_hz() -> None:
    results = firm_rate(detected(build_results()))
    (note,) = annotations(results)
    assert (note["core:sample_start"], note["core:sample_count"]) == (1000, 4000)
    # centre 0.2 of 1 MS/s above the 100 MHz capture centre, 0.1 of the rate wide
    assert note["core:freq_lower_edge"] == pytest.approx(1e8 + 0.2e6 - 0.05e6)
    assert note["core:freq_upper_edge"] == pytest.approx(1e8 + 0.2e6 + 0.05e6)
    assert note["core:label"] == "QPSK" and note["core:comment"] == "QPSK, CCSDS frames"
    assert (note["sanket:signal"], note["sanket:level"]) == ("signal_0", "VERIFIED")
    assert "sanket:frequency_reference" not in note


def test_without_a_stated_centre_the_band_is_from_the_capture_centre_and_says_so() -> None:
    results = with_assumptions(
        detected(build_results()),
        sample_rate=param("sample_rate", EvidenceLevel.MEASURED, 1e6, unit="S/s"),
    )
    (note,) = annotations(results)
    assert note["core:freq_lower_edge"] == pytest.approx(0.15e6)
    assert "baseband" in note["sanket:frequency_reference"]


def test_a_rate_that_is_only_a_hypothesis_gives_no_band_in_hz() -> None:
    guess = param(
        "sample_rate", EvidenceLevel.HYPOTHESIS, 1e6, unit="S/s", convention="a structural match"
    )
    (note,) = annotations(with_assumptions(detected(build_results()), sample_rate=guess))
    assert "core:freq_lower_edge" not in note and "core:freq_upper_edge" not in note
    assert note["core:sample_count"] == 4000  # the span in samples needs no rate


def test_a_signal_without_a_span_is_not_annotated() -> None:
    assert annotations(build_results()) == []


def test_a_new_description_names_the_dataset_and_leaves_the_samples_alone() -> None:
    results = firm_rate(detected(build_results()))
    meta = meta_for(results, dataset="capture.cs16")
    g = meta["global"]
    assert g["core:dataset"] == "capture.cs16" and g["core:datatype"] == "ci16_le"
    assert g["core:sample_rate"] == 1e6 and meta["captures"][0]["core:frequency"] == 1e8
    assert "core:header_bytes" not in meta["captures"][0]  # offset 0
    assert g["sanket:provenance"]["assumptions"]["datatype"]["level"] == "MEASURED"
    assert g["core:extensions"][0]["name"] == "sanket"
    assert render_meta(meta) == render_meta(meta_for(results, dataset="capture.cs16"))


def test_a_hypothesis_rate_stays_out_of_the_standard_fields_but_is_recorded() -> None:
    guess = param(
        "sample_rate",
        EvidenceLevel.HYPOTHESIS,
        250000.0,
        unit="S/s",
        convention="a structural match",
    )
    meta = meta_for(with_assumptions(build_results(), sample_rate=guess), dataset="x.cu8")
    assert "core:sample_rate" not in meta["global"]
    recorded = meta["global"]["sanket:provenance"]["assumptions"]["sample_rate"]
    assert (recorded["value"], recorded["level"]) == (250000.0, "HYPOTHESIS")


def test_a_header_offset_is_carried_as_header_bytes() -> None:
    offset = param("data_offset", EvidenceLevel.MEASURED, 44, unit="B")
    meta = meta_for(with_assumptions(build_results(), data_offset=offset), dataset="x.raw")
    assert meta["captures"][0]["core:header_bytes"] == 44


def test_an_unknown_format_or_q_first_is_refused() -> None:
    unknown = param("datatype", EvidenceLevel.UNKNOWN, None)
    with pytest.raises(SigmfRefused, match="UNKNOWN"):
        meta_for(with_assumptions(build_results(), datatype=unknown), dataset="x")
    q_first = param("iq_order", EvidenceLevel.MEASURED, "QI")
    with pytest.raises(SigmfRefused, match="Q comes first"):
        meta_for(with_assumptions(build_results(), iq_order=q_first), dataset="x")


def test_an_existing_recordings_metadata_is_kept_and_annotated() -> None:
    original = {
        "global": {
            "core:datatype": "cf32_le",
            "core:sample_rate": 2e6,
            "core:version": "1.2.0",
            "core:extensions": [{"name": "other", "version": "1", "optional": True}],
        },
        "captures": [{"core:sample_start": 0, "core:frequency": 5e7}],
        "annotations": [{"core:sample_start": 0, "core:sample_count": 10, "core:label": "mine"}],
    }
    results = firm_rate(detected(build_results()))
    meta = meta_for(results, original=original)
    assert meta["global"]["core:sample_rate"] == 2e6  # theirs, not the results' assumption
    assert meta["captures"] == original["captures"]
    assert [a["core:label"] for a in meta["annotations"]] == ["mine", "QPSK"]
    assert [e["name"] for e in meta["global"]["core:extensions"]] == ["other", "sanket"]
    assert original["annotations"][0]["core:label"] == "mine" and len(original["annotations"]) == 1


def two_signals_out_of_order(results: Results) -> Results:
    """`detected`'s signal (starting at sample 1000) followed by one starting at sample 200."""
    first = detected(results).signals[0]
    early = detected(results, start_sample=200, stop_sample=900).signals[0]
    return results.model_copy(
        update={"signals": (first, early.model_copy(update={"id": "signal_1", "label": "BPSK"}))}
    )


def test_annotations_come_in_sample_order_as_the_sigmf_validator_requires() -> None:
    results = two_signals_out_of_order(build_results())
    assert [a["core:sample_start"] for a in annotations(results)] == [200, 1000]
    original = {
        "global": {"core:datatype": "cf32_le", "core:sample_rate": 2e6, "core:version": "1.2.0"},
        "captures": [{"core:sample_start": 0}],
        "annotations": [
            {"core:sample_start": 500, "core:sample_count": 10, "core:label": "theirs"},
            {"core:sample_start": 5000, "core:sample_count": 10, "core:label": "later"},
        ],
    }
    merged = meta_for(results, original=original)["annotations"]
    assert [a["core:label"] for a in merged] == ["BPSK", "theirs", "QPSK", "later"]
    assert [a["core:sample_start"] for a in merged] == sorted(
        a["core:sample_start"] for a in merged
    )


def test_the_assumptions_helper_matches_the_fixture() -> None:
    assert assumptions().datatype.value == "ci16_le"
