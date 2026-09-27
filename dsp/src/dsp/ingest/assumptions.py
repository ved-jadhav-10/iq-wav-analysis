"""Assumption entries shared by every ingest path, and the hints that settle UNKNOWN ones."""

from dsp.evidence import EvidenceLevel, Parameter
from dsp.ingest.formats import SampleFormat

FORMAT_HINT = "Choose the sample format from the ranked format candidates."
OFFSET_HINT = "Enter the byte offset of the first sample (the header length)."
RATE_HINT = (
    "Enter the sample rate. Until then, frequencies and rates are reported as fractions of it."
)
FREQUENCY_HINT = (
    "Enter the centre frequency. Until then, frequencies are relative to the recording's centre."
)


def iq_order(fmt: SampleFormat | None, method: str) -> Parameter | None:
    """IQ order as a stated HYPOTHESIS for complex data, UNKNOWN if the format is, None if real."""
    if fmt is None:
        return Parameter(
            id="iq_order",
            name="IQ order",
            value=None,
            level=EvidenceLevel.UNKNOWN,
            method=method,
            evidence=(
                "The sample format is unknown, so it isn't known whether samples are complex.",
            ),
            resolve_hint=FORMAT_HINT,
        )
    if not fmt.is_complex:
        return None
    return Parameter(
        id="iq_order",
        name="IQ order",
        value="IQ",
        level=EvidenceLevel.HYPOTHESIS,
        method=method,
        evidence=(
            "The samples can't confirm it: swapping I and Q only mirrors the spectrum. Toggle it "
            "if a known carrier sits on the wrong side.",
        ),
    )
