from pathlib import Path

import numpy as np
import pytest

from dsp.evidence import EvidenceLevel
from dsp.ingest.formats import SampleFormat
from dsp.ingest.rate import (
    ALPHA,
    MAX_ALTERNATIVES,
    MIN_NORMALISED_RATE,
    RateCandidate,
    filename_hints,
    rate_candidates,
    sample_rate_parameter,
    structural_parameter,
    structural_test,
)
from dsp.ingest.raw import read_raw
from dsp.synth.waveforms import awgn


@pytest.mark.parametrize(
    ("name", "rate", "center"),
    [
        ("gqrx_20240101_120000_144800000_1800000_fc.raw", 1_800_000.0, 144_800_000.0),
        ("capture_fs=2.4M_fc=433.92M.cu8", 2_400_000.0, 433_920_000.0),
        ("SDRSharp_20170125_095238Z_96500000Hz_IQ.wav", None, 96_500_000.0),
        ("HDSDR_20170125_095238Z_7100kHz_RF.wav", None, 7_100_000.0),
        ("noaa_2048ksps.cf32", 2_048_000.0, None),
        ("sr250k.cu8", 250_000.0, None),
        ("pass_samp_rate_6M.cs16", 6_000_000.0, None),
        ("usrp_rate5.bin", None, None),  # 5 S/s is out of range: not a hint
        ("capture.bin", None, None),
        ("sweep_freq2.bin", None, None),
    ],
)
def test_filename_hints(name: str, rate: float | None, center: float | None) -> None:
    hints = filename_hints(name)
    assert [h.value for h in hints if h.kind == "sample_rate"] == ([rate] if rate else [])
    assert [h.value for h in hints if h.kind == "center_frequency"] == ([center] if center else [])


def test_candidates_rank_file_name_hints_then_the_matching_recorder() -> None:
    candidates = rate_candidates("x_fs=2.4M.cu8", "cu8")
    assert candidates[0] == RateCandidate(
        2.4e6, "sample-rate tag in the file name: 'fs=2.4m'", True
    )
    assert "RTL-SDR" in candidates[1].reason and "writes cu8" in candidates[1].reason
    assert len({c.value for c in candidates}) == len(candidates)  # no duplicates
    hackrf = rate_candidates("x.cs8", "ci8")
    assert "HackRF" in hackrf[0].reason


def test_unknown_rate_lists_candidates_and_never_picks_one() -> None:
    candidates = rate_candidates("x_fs=2.4M.cu8", "cu8")
    param = sample_rate_parameter(candidates, "cu8", "test", "No metadata.")
    assert (param.value, param.level) == (None, EvidenceLevel.UNKNOWN)
    assert param.alternatives[0].value == 2.4e6
    assert len(param.alternatives) == MAX_ALTERNATIVES
    assert any("'fs=2.4m'" in e for e in param.evidence)
    assert param.resolve_hint and "candidate" in param.resolve_hint


def test_raw_files_state_rate_and_frequency_candidates(tmp_path: Path) -> None:
    path = tmp_path / "gqrx_20240101_120000_144800000_1800000_fc.raw"
    x = awgn(np.random.default_rng(0), 1 << 14)
    path.write_bytes(SampleFormat.parse("cf32_le").encode(x))
    a = read_raw(path).assumptions
    assert a.sample_rate.level is EvidenceLevel.UNKNOWN
    assert a.sample_rate.alternatives[0].value == 1_800_000.0
    assert a.center_frequency.level is EvidenceLevel.UNKNOWN
    assert [alt.value for alt in a.center_frequency.alternatives] == [144_800_000.0]


# -- structural matches ------------------------------------------------------------------------


def test_a_file_name_rate_confirmed_by_a_symbol_rate_becomes_a_hypothesis() -> None:
    candidates = rate_candidates("ais_fs=2.4M.cu8", "cu8")
    unknown = sample_rate_parameter(candidates, "cu8", "test", "No metadata.")
    test = structural_test(9600 / 2.4e6 * (1 + 30e-6), 1e-6, candidates)  # 30 ppm clock error
    assert test.decided is not None and test.decided.label == "file-name candidates"
    param = structural_parameter(test, unknown)
    assert (param.value, param.level) == (2.4e6, EvidenceLevel.HYPOTHESIS)
    assert any("AIS" in e for e in param.evidence)
    assert 2.4e6 not in {a.value for a in param.alternatives}


def test_a_ladder_of_rates_is_ambiguous_and_stays_unknown() -> None:
    # 9600 Bd at 2.4 MS/s and 4800 Bd at 1.2 MS/s give the same normalised rate.
    candidates = rate_candidates("capture.cu8", "cu8")
    unknown = sample_rate_parameter(candidates, "cu8", "test", "No metadata.")
    test = structural_test(9600 / 2.4e6, 1e-6, candidates)
    assert {m.sample_rate for t in test.tiers for m in t.matches} == {1.2e6, 2.4e6}
    assert test.decided is None
    param = structural_parameter(test, unknown)
    assert param.level is EvidenceLevel.UNKNOWN
    assert "different sample rates" in param.evidence[-1]


def test_an_imprecise_symbol_rate_matches_nothing() -> None:
    candidates = rate_candidates("x_fs=2.4M.cu8", "cu8")
    test = structural_test(9600 / 2.4e6, 1e-3, candidates)
    assert test.decided is None and not any(t.matches for t in test.tiers)
    param = structural_parameter(test, sample_rate_parameter(candidates, "cu8", "t", "r"))
    assert "too uncertain" in param.evidence[-1]


def test_an_unrecognised_symbol_rate_matches_nothing() -> None:
    candidates = rate_candidates("x_fs=2.4M.cu8", "cu8")
    test = structural_test(0.0123457, 1e-6, candidates)
    assert test.decided is None
    param = structural_parameter(test, sample_rate_parameter(candidates, "cu8", "t", "r"))
    assert param.evidence[-1] == "No structural match."


@pytest.mark.parametrize("name", ["capture.cu8", "x_fs=2.4M.cu8", "x_fs=48k_fs=96k.wav"])
def test_random_rates_are_promoted_no_more_often_than_alpha(name: str) -> None:
    candidates = rate_candidates(name, "cu8")
    rng = np.random.default_rng(11)
    rates = np.exp(rng.uniform(np.log(MIN_NORMALISED_RATE), 0.0, 5_000))
    promoted = sum(structural_test(float(r), 0.0, candidates).decided is not None for r in rates)
    assert promoted / len(rates) <= ALPHA


def test_every_pair_tried_is_counted() -> None:
    candidates = rate_candidates("x_fs=2.4M.cu8", "cu8")
    test = structural_test(0.004, 0.0, candidates)
    assert [t.hypotheses for t in test.tiers] == [16, 16 * len(candidates) - 9]
    assert sum(t.alpha for t in test.tiers) == pytest.approx(ALPHA)


@pytest.mark.parametrize("bad", [0.0, 1.5, -0.1])
def test_normalised_rate_out_of_range_is_refused(bad: float) -> None:
    with pytest.raises(ValueError):
        structural_test(bad, 0.0, rate_candidates("x.cu8", "cu8"))
