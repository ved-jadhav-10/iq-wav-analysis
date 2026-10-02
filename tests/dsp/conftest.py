"""Shared fixtures for the dsp tests."""

import pytest

from dsp.evidence import EvidenceLevel, Parameter, Proof
from dsp.findings import Frame
from dsp.results import Assumptions, Results, Signal, StageResult


def param(id: str, level: EvidenceLevel, value: float | str | None, **fields: object) -> Parameter:
    extra: dict[str, object] = {"method": "test"}
    if level is EvidenceLevel.UNKNOWN:
        extra |= {"evidence": ("no peak above the noise",), "resolve_hint": "enter the rate"}
    return Parameter(id=id, name=id.title(), value=value, level=level, **extra | fields)  # type: ignore[arg-type]


def assumptions() -> Assumptions:
    return Assumptions(
        datatype=param("datatype", EvidenceLevel.MEASURED, "ci16_le"),
        data_offset=param("data_offset", EvidenceLevel.MEASURED, 0, unit="bytes"),
        sample_rate=param("sample_rate", EvidenceLevel.UNKNOWN, None),
        center_frequency=param("center_frequency", EvidenceLevel.UNKNOWN, None),
        iq_order=param("iq_order", EvidenceLevel.HYPOTHESIS, "IQ", convention="IQ is the default"),
    )


def build_results() -> Results:
    snr = param("snr", EvidenceLevel.ESTIMATED, 12.5, unit="dB", uncertainty=0.8)
    crc = param(
        "frames",
        EvidenceLevel.VERIFIED,
        "CCSDS",
        proof=Proof(kind="crc", detail="CRC-16 passed on 12 of 12 frames"),
        evidence=("ASM 1ACFFC1D", "12 frames"),
        warnings=("short run",),
    )
    signal = Signal(
        id="signal_0",
        label="QPSK",
        kind="psk",
        level=EvidenceLevel.VERIFIED,
        headline="QPSK, CCSDS frames",
        stages=(
            StageResult(
                id="estimate", name="Estimate", status="done", summary="s", parameters=(snr,)
            ),
            StageResult(
                id="framing", name="Framing", status="done", summary="f", parameters=(crc,)
            ),
        ),
        search=None,
        no_search_reason="none run",
        frames=(
            Frame(
                index=1,
                start_bit=0,
                sync_word="1ACFFC1D",
                length_bits=64,
                crc="pass",
                header_hex="12 34",
                payload_hex="0A1B",
            ),
        ),
        no_frames_reason=None,
    )
    return Results(
        sanket_version="0.1.0",
        assumptions=assumptions(),
        stages=(StageResult(id="ingest", name="Ingest", status="done", summary="i"),),
        signals=(signal,),
    )


@pytest.fixture
def sample_results() -> Results:
    """One recording with an UNKNOWN sample rate, a convention-based IQ order, and a signal with
    an estimate, a VERIFIED value (CRC) and one passing frame."""
    return build_results()
