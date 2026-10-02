from dsp.results import Results
from dsp.summary import render_summary


def test_what_was_proved_comes_first_with_its_proof(sample_results: Results) -> None:
    out = render_summary(sample_results)
    assert "Signal 1 (signal_0), VERIFIED: QPSK, CCSDS frames" in out
    assert "Frames: CCSDS (proved on this recording); crc" in out
    assert out.index("Proved:") < out.index("Not proved:")


def test_estimates_state_their_uncertainty_and_are_not_called_proved(
    sample_results: Results,
) -> None:
    out = render_summary(sample_results)
    assert "Snr: 12.5 dB ± 0.8 (estimated)" in out
    proved = out[out.index("Proved:") : out.index("Not proved:")]
    assert "Snr" not in proved


def test_unknown_assumptions_say_what_would_settle_them(sample_results: Results) -> None:
    out = render_summary(sample_results)
    assert "Sample_Rate: UNKNOWN; enter the rate" in out
    assert "Center_Frequency: UNKNOWN; enter the rate" in out


def test_a_convention_is_listed_for_review(sample_results: Results) -> None:
    out = render_summary(sample_results)
    assert "1 value(s) rest on a convention" in out
    assert "Iq_Order = IQ: IQ is the default" in out


def test_frames_are_counted_by_crc_outcome(sample_results: Results) -> None:
    assert "Frames in the table: 1, 1 pass their CRC." in render_summary(sample_results)


def test_a_signal_without_a_search_states_nothing_about_one(sample_results: Results) -> None:
    assert "blind search counted" not in render_summary(sample_results)


def test_output_is_deterministic(sample_results: Results) -> None:
    assert render_summary(sample_results) == render_summary(sample_results)
