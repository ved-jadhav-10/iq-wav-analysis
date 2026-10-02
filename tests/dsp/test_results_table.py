import csv
import io

from dsp.results import Results
from dsp.results_table import COLUMNS, render_csv


def rows(results: Results) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(render_csv(results))))


def test_header_is_the_documented_columns(sample_results: Results) -> None:
    assert render_csv(sample_results).splitlines()[0] == ",".join(COLUMNS)


def test_assumptions_come_first_then_each_signals_headline_and_values(
    sample_results: Results,
) -> None:
    table = rows(sample_results)
    assert [(r["signal"], r["stage"], r["id"]) for r in table] == [
        ("", "assumptions", "datatype"),
        ("", "assumptions", "data_offset"),
        ("", "assumptions", "sample_rate"),
        ("", "assumptions", "center_frequency"),
        ("", "assumptions", "iq_order"),
        ("signal_0", "headline", "headline"),
        ("signal_0", "estimate", "snr"),
        ("signal_0", "framing", "frames"),
    ]


def test_an_estimate_keeps_its_unit_uncertainty_and_level(sample_results: Results) -> None:
    snr = next(r for r in rows(sample_results) if r["id"] == "snr")
    assert (snr["value"], snr["unit"], snr["uncertainty"], snr["level"]) == (
        "12.5",
        "dB",
        "0.8",
        "ESTIMATED",
    )


def test_verified_carries_its_proof_and_never_without_it(sample_results: Results) -> None:
    table = rows(sample_results)
    frames = next(r for r in table if r["id"] == "frames")
    assert frames["level"] == "VERIFIED"
    assert frames["proof"] == "crc: CRC-16 passed on 12 of 12 frames"
    assert frames["evidence"] == "ASM 1ACFFC1D | 12 frames"
    assert frames["warnings"] == "short run"
    assert all(r["proof"] == "" for r in table if r["level"] != "VERIFIED")


def test_unknown_has_no_value_and_gives_its_reason(sample_results: Results) -> None:
    rate = next(r for r in rows(sample_results) if r["id"] == "sample_rate")
    assert (rate["level"], rate["value"], rate["evidence"]) == (
        "UNKNOWN",
        "",
        "no peak above the noise",
    )


def test_a_convention_is_in_its_own_column(sample_results: Results) -> None:
    order = next(r for r in rows(sample_results) if r["id"] == "iq_order")
    assert (order["level"], order["convention"]) == ("HYPOTHESIS", "IQ is the default")


def test_signal_headline_row_carries_label_headline_and_level(sample_results: Results) -> None:
    headline = next(r for r in rows(sample_results) if r["stage"] == "headline")
    assert (headline["name"], headline["value"], headline["level"]) == (
        "QPSK",
        "QPSK, CCSDS frames",
        "VERIFIED",
    )
    assert headline["proof"] == "crc: 1 of 1 frames in the table pass"


def test_output_is_deterministic(sample_results: Results) -> None:
    assert render_csv(sample_results) == render_csv(sample_results)
