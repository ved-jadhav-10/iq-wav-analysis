import io

import pytest
from pypdf import PdfReader

from dsp.evidence import EvidenceLevel, Parameter, Proof
from dsp.findings import Frame, Hypothesis, HypothesisSearch
from dsp.report_pdf import MAX_FRAME_ROWS, printable, render_pdf
from dsp.results import (
    NO_FILES,
    CatalogueVersion,
    FileIdentity,
    RecordingIdentity,
    Results,
    Signal,
    StageResult,
    results_sha256,
)
from dsp.summary import render_summary
from tests.dsp.conftest import assumptions, build_results, param

SHA = "ab" * 32
SYNC = "1ACFFC1D"


def text_of(pdf: bytes) -> str:
    """The PDF's text with every run of whitespace (line wraps included) as one space."""
    reader = PdfReader(io.BytesIO(pdf))
    return " ".join(" ".join(page.extract_text() or "" for page in reader.pages).split())


def pages_of(pdf: bytes) -> int:
    return len(PdfReader(io.BytesIO(pdf)).pages)


def frames(count: int, payload: str = "0A1B2C") -> tuple[Frame, ...]:
    return tuple(
        Frame(
            index=i + 1,
            start_bit=64 * i,
            sync_word=SYNC,
            length_bits=64,
            crc="pass" if i % 2 == 0 else "fail",
            header_hex="12 34",
            payload_hex=payload,
        )
        for i in range(count)
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
        tried=1234,
        alpha=0.01,
        correction="Holm",
        smallest_threshold=0.0033,
        shuffled_runs=3,
        shuffled_accepts=0,
        match_tried=1,
        rows=(row("Framing", "ASM-LEDGER", "accepted"), row("Match", "POCSAG-LEDGER", "rejected")),
    )


def rich_results(
    frame_count: int = 3, payload: str = "0A1B2C", **signal_changes: object
) -> Results:
    """Two signals: one VERIFIED with a ledger and frames, one all-UNKNOWN with no frames."""
    base = build_results()
    first = base.signals[0]
    proved = Signal.model_validate(
        first.model_dump(by_alias=False)
        | {
            "headline": "QPSK, CCSDS frames, ledger-headline",
            "search": ledger(),
            "no_search_reason": None,
            "frames": frames(frame_count, payload),
            "no_frames_reason": None,
        }
        | signal_changes
    )
    unknown = Signal(
        id="signal_1",
        label="unclassified",
        kind="unknown",
        level=EvidenceLevel.UNKNOWN,
        headline="unclassified, second-signal-headline",
        stages=(
            StageResult(
                id="estimate",
                name="Estimate",
                status="done",
                summary="s",
                parameters=(param("symbol_rate", EvidenceLevel.UNKNOWN, None),),
                warnings=("stage-warning-text",),
            ),
        ),
        search=None,
        no_search_reason="the signal is too short to search",
        frames=(),
        no_frames_reason="no sync word recurred",
    )
    recording = RecordingIdentity(
        container="SigMF",
        samples=1_000_000,
        files=(
            FileIdentity(name="capture.sigmf-data", size_bytes=4_000_000, sha256=SHA),
            FileIdentity(name="capture.sigmf-meta", size_bytes=512, sha256="cd" * 32),
        ),
    )
    return base.model_copy(
        update={
            "recording": recording,
            "catalogues": (CatalogueVersion(name="systems", version="2026.3"),),
            "signals": (proved, unknown),
        }
    )


@pytest.fixture
def rich() -> Results:
    return rich_results()


def test_it_is_a_pdf_that_reads_back(sample_results: Results) -> None:
    pdf = render_pdf(sample_results)
    assert pdf.startswith(b"%PDF")
    assert pages_of(pdf) >= 1


def test_the_title_names_the_files_and_their_hashes(rich: Results) -> None:
    text = text_of(render_pdf(rich))
    assert "Sanket results report capture.sigmf-data, capture.sigmf-meta" in text
    assert SHA in text
    assert "cd" * 32 in text
    assert "Catalogue versions: systems 2026.3." in text
    assert "Sanket version 0.1.0." in text
    assert results_sha256(rich) in text


def test_a_recording_held_in_memory_says_there_are_no_hashes(sample_results: Results) -> None:
    text = text_of(render_pdf(sample_results))
    assert "no recording files (analysed in memory)" in text
    assert "No file hashes" in text
    assert "Catalogue versions: none recorded." in text


def test_the_summary_comes_second_and_is_verbatim(rich: Results) -> None:
    text = text_of(render_pdf(rich))
    summary = render_summary(rich).splitlines()
    assert summary[0] in text
    assert text.index("Summary") < text.index(summary[0]) < text.index("Assumptions")
    assert text.index("Sanket results report") < text.index("Summary")
    for line in summary:
        if line.strip():
            assert " ".join(line.split()) in text


def test_sections_come_in_the_stated_order(rich: Results) -> None:
    text = text_of(render_pdf(rich))
    marks = [
        "Sanket results report",
        "Summary",
        "Assumptions What the analysis took as given",
        "Capture quality",
        "Needs review",
        "Signals Signal 1",
    ]
    positions = [text.index(m) for m in marks]
    assert positions == sorted(positions)


def test_every_assumption_is_listed_with_its_level_word(sample_results: Results) -> None:
    text = text_of(render_pdf(sample_results))
    for p in sample_results.assumptions.parameters():
        assert p.name in text
    for word in ("MEASURED", "UNKNOWN", "HYPOTHESIS"):
        assert word in text


def test_every_level_is_a_glyph_and_its_word() -> None:
    values = {
        EvidenceLevel.VERIFIED: ("CCSDS", {"proof": Proof(kind="crc", detail="CRC-16 passed")}),
        EvidenceLevel.MEASURED: ("a", {}),
        EvidenceLevel.ESTIMATED: ("b", {"uncertainty": 0.5}),
        EvidenceLevel.HYPOTHESIS: ("c", {}),
        EvidenceLevel.UNKNOWN: (None, {}),
    }
    params = tuple(
        param(f"p_{level.value.lower()}", level, value, **extra)
        for level, (value, extra) in values.items()
    )
    base = build_results()
    stage = StageResult(id="demod", name="Demod", status="done", summary="d", parameters=params)
    signal = base.signals[0].model_copy(update={"stages": (stage,)})
    pdf = render_pdf(base.model_copy(update={"signals": (signal,)}))
    # The signal's own table: the five words appear after the signal heading, each as text.
    after = text_of(pdf)
    after = after[after.index("Signals Signal 1") :]
    for level in EvidenceLevel:
        assert level.value in after


def test_each_signal_has_its_headline_and_label(rich: Results) -> None:
    text = text_of(render_pdf(rich))
    assert "Signal 1: signal_0, QPSK" in text
    assert "QPSK, CCSDS frames, ledger-headline" in text
    assert "Signal 2: signal_1, unclassified" in text
    assert "unclassified, second-signal-headline" in text


def test_proofs_warnings_and_unknowns_with_their_hints(rich: Results) -> None:
    text = text_of(render_pdf(rich))
    assert "Frames: crc, CRC-16 passed on 12 of 12 frames" in text
    assert "Frames: short run" in text
    assert "Estimate: stage-warning-text" in text
    assert "Symbol_Rate: no peak above the noise. To resolve: enter the rate" in text
    assert "Proofs: none (no value is VERIFIED)." in text


def test_a_value_shows_its_uncertainty_and_unit(rich: Results) -> None:
    assert "12.5 ± 0.8 dB" in text_of(render_pdf(rich))


def test_needs_review_lists_the_conventions_or_says_there_are_none(
    rich: Results,
) -> None:
    assert "IQ is the default" in text_of(render_pdf(rich))
    none = Results(
        sanket_version="0.1.0",
        recording=NO_FILES,
        catalogues=(),
        assumptions=assumptions().model_copy(
            update={
                "iq_order": Parameter(
                    id="iq_order",
                    name="Iq_Order",
                    value="IQ",
                    level=EvidenceLevel.MEASURED,
                    method="header",
                )
            }
        ),
        stages=(),
    )
    text = text_of(render_pdf(none))
    assert "Nothing rests on a convention." in text
    assert "This document has no capture-quality stage." in text
    assert "No signals are reported in this document." in text


def test_capture_quality_shows_its_parameters_and_warnings() -> None:
    capture = StageResult(
        id="capture",
        name="Capture quality",
        status="done",
        summary="clipping found",
        parameters=(param("clipping", EvidenceLevel.MEASURED, 0.03, unit="fraction"),),
        warnings=("clipping-warning-text",),
    )
    base = build_results()
    results = base.model_copy(update={"stages": (*base.stages, capture)})
    text = text_of(render_pdf(results))
    section = text[text.index("Capture quality (capture), done: clipping found") :]
    assert "Clipping 0.03 fraction" in section
    assert "clipping-warning-text" in section


def test_the_ledger_states_its_counts_and_rows(rich: Results) -> None:
    text = text_of(render_pdf(rich))
    assert "Hypotheses tried: 1,234" in text
    assert "Correction: Holm" in text
    assert "ASM-LEDGER" in text
    assert "POCSAG-LEDGER" in text
    assert "2 row(s) listed." in text
    assert "No search ran: the signal is too short to search" in text


def test_frames_show_their_fields_and_a_signal_without_any_says_why(rich: Results) -> None:
    text = text_of(render_pdf(rich))
    assert "Frames in the table: 3, 2 pass their CRC." in text
    assert text.count(SYNC) == 3
    assert "No frames: no sync word recurred" in text


def test_only_forty_frame_rows_appear_and_the_rest_are_counted() -> None:
    pdf = render_pdf(rich_results(500))
    text = text_of(pdf)
    assert text.count(SYNC) == MAX_FRAME_ROWS
    assert f"Showing the first {MAX_FRAME_ROWS} of 500 frames; 460 more are not shown" in text


def test_a_very_long_payload_is_cut_with_an_ellipsis() -> None:
    payload = "DEADBEEF" * 1000
    pdf = render_pdf(rich_results(2, payload))
    text = text_of(pdf)
    assert payload[:64] in text.replace(" ", "")
    assert payload[:65] not in text.replace(" ", "")
    assert "…" in text
    assert pages_of(pdf) < 20


def test_the_footer_is_on_every_page(rich: Results) -> None:
    pdf = render_pdf(rich_results(300))
    reader = PdfReader(io.BytesIO(pdf))
    total = len(reader.pages)
    assert total > 2
    prefix = f"Sanket 0.1.0 · results SHA-256 {results_sha256(rich_results(300))[:16]}"
    for n, page in enumerate(reader.pages, start=1):
        text = " ".join((page.extract_text() or "").split())
        assert f"{prefix} · page {n} of {total}" in text


def test_the_same_results_give_the_same_bytes(rich: Results) -> None:
    assert render_pdf(rich) == render_pdf(rich)
    assert render_pdf(rich_results(60)) == render_pdf(rich_results(60))


def test_different_results_give_different_bytes(rich: Results, sample_results: Results) -> None:
    assert render_pdf(rich) != render_pdf(sample_results)


def test_the_metadata_has_no_clock_or_random_id(rich: Results) -> None:
    pdf = render_pdf(rich)
    info = PdfReader(io.BytesIO(pdf)).metadata
    assert info is not None
    assert info.title is not None
    assert "capture.sigmf-data" in info.title
    assert info.author == "Sanket 0.1.0"
    assert info.creation_date is not None
    assert info.creation_date.year == 2000  # ReportLab's fixed invariant date


def test_greek_and_latin_symbols_render() -> None:
    label = "β=0.35 · 12° · x² · ½ · ±3 · Łódź"
    results = build_results()
    snr = param("beta", EvidenceLevel.ESTIMATED, 0.35, unit="°", uncertainty=0.02)
    named = Parameter.model_validate({**snr.model_dump(by_alias=False), "name": label})
    stage = StageResult(
        id="estimate", name="Estimate", status="done", summary="s", parameters=(named,)
    )
    signal = results.signals[0].model_copy(update={"stages": (stage,)})
    text = text_of(render_pdf(results.model_copy(update={"signals": (signal,)})))
    assert "β=0.35 · 12° · x² · ½ · ±3 · Łódź" in text
    assert "?" not in text.split("Signals", 1)[1].split("Signal 1")[1].split("Frames")[0]


def test_symbols_the_fonts_lack_are_spelled_in_ascii() -> None:
    assert printable("a ≥ b → c ≤ d") == "a >= b -> c <= d"
    headline = "QPSK 1/2 → CCSDS, ≤ 3 bit errors"
    results = build_results()
    signal = results.signals[0].model_copy(update={"headline": headline})
    text = text_of(render_pdf(results.model_copy(update={"signals": (signal,)})))
    assert "QPSK 1/2 -> CCSDS, <= 3 bit errors" in text


def test_a_glyph_no_font_has_is_a_visible_question_mark_and_never_an_error() -> None:
    assert printable("a漢bc\x00d") == "a?b?c d"
    results = build_results()
    signal = results.signals[0].model_copy(update={"headline": "headline 漢字 here"})
    pdf = render_pdf(results.model_copy(update={"signals": (signal,)}))
    assert "headline ?? here" in text_of(pdf)
