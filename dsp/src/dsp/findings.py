"""What a detected signal's analysis concluded, apart from its stages: the headline, the
hypothesis ledger and the frame table (PLAN M6, M7).

These models are shared by the decode chain's per-detection report (`dsp.report`, which also
carries the constellation and the eye for the live views) and by the results document
(`dsp.results`, which is what a file or an export holds), so the two can never disagree about
what a ledger row or a frame is. They live here because `dsp.report` builds on `dsp.results`.
"""

from typing import Literal, Self

from pydantic import Field, model_validator

from dsp.evidence import CamelModel, EvidenceLevel, FiniteFloat


class Hypothesis(CamelModel):
    """One row of the ledger: a candidate the search tried, and what decided it."""

    layer: Literal["Demod", "Interleaver", "FEC", "Framing", "Match"]
    candidate: str = Field(min_length=1)
    statistic: str = Field(min_length=1)
    p_value: FiniteFloat | None = Field(
        description="Chance of the statistic under the no-structure null; null when not computed."
    )
    threshold: FiniteFloat = Field(description="The corrected acceptance threshold on p_value.")
    outcome: Literal["accepted", "rejected"]
    reason: str = Field(min_length=1)


class HypothesisSearch(CamelModel):
    """The blind search's ledger. `tried` counts every hypothesis, including ones not listed in
    `rows`; thresholds are corrected for that count."""

    tried: int = Field(ge=0)
    alpha: FiniteFloat
    correction: str = Field(min_length=1)
    smallest_threshold: FiniteFloat
    shuffled_runs: int = Field(
        ge=0,
        description="Runs on shuffled bits of the chains that passed the threshold, best first "
        "(up to three of them, each run several times).",
    )
    shuffled_accepts: int = Field(ge=0, description="How many of those runs passed; should be 0.")
    shuffled_blocked: int = Field(
        default=0,
        ge=0,
        description="Chains that passed the threshold but also passed on shuffled bits, and so "
        "were not accepted.",
    )
    blind_searched: int = Field(
        default=0, ge=0, description="Branches the blind rate-1/n convolutional search ran on."
    )
    blind_identified: int = Field(
        default=0,
        ge=0,
        description="Of those, branches where it named a code (which then still had to frame).",
    )
    match_tried: int = Field(
        default=0,
        ge=0,
        description="Known-system checks the Match stage ran, each one hypothesis in its own "
        "Holm correction (rows with layer Match), separate from `tried`.",
    )
    rows: tuple[Hypothesis, ...]


class Frame(CamelModel):
    index: int = Field(ge=1)
    start_bit: int = Field(ge=0, description="Offset of the sync word in the decoded bit stream.")
    sync_word: str = Field(min_length=1)
    length_bits: int = Field(ge=0)
    crc: Literal["pass", "fail", "truncated"]
    header_hex: str = Field(description="The first bytes after the sync word, space-separated.")
    payload_hex: str = Field(description="The frame's payload bytes (CRC excluded), no spaces.")


MAX_FRAMES = 500

SignalKind = Literal["psk", "fsk", "cw", "analog", "unknown"]


class SignalFindings(CamelModel):
    """A signal's label, headline level, ledger and frames, with the rules tying them together."""

    label: str = Field(min_length=1, description="Short label for the signal, e.g. 'QPSK'.")
    kind: SignalKind = Field(description="Picks the symbol view: constellation, frequency, none.")
    level: EvidenceLevel = Field(description="The level of the signal's headline finding.")
    headline: str = Field(min_length=1)
    search: HypothesisSearch | None = Field(
        description="The hypothesis ledger; null when no search ran, and `noSearchReason` says why."
    )
    no_search_reason: str | None = None
    frames: tuple[Frame, ...] = Field(
        default=(),
        max_length=MAX_FRAMES,
        description=f"The frame table, limited to the first {MAX_FRAMES} frames.",
    )
    no_frames_reason: str | None = None

    @model_validator(mode="after")
    def _check_findings(self) -> Self:
        if (self.search is None) != bool(self.no_search_reason):
            raise ValueError("a missing search states why, and only a missing search does")
        if (not self.frames) != bool(self.no_frames_reason):
            raise ValueError("no frames states why, and only no frames does")
        if self.level is EvidenceLevel.VERIFIED and not any(f.crc == "pass" for f in self.frames):
            raise ValueError("a VERIFIED signal needs at least one frame that passes its CRC")
        return self
