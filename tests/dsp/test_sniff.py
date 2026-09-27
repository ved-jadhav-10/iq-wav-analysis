from pathlib import Path

import numpy as np
import pytest

from bench.sniffer import COMPLEX_SIGNALS, REAL_SIGNALS, Case, levels_dbfs, outcome
from dsp.evidence import EvidenceLevel
from dsp.ingest.formats import ALL_DATATYPES, SampleFormat
from dsp.ingest.raw import read_raw
from dsp.ingest.sniff import (
    BLOCK_BYTES,
    BLOCKS,
    MIN_BYTES,
    detect_container,
    prediction_error,
    sniff,
    sniff_blocks,
)
from dsp.results import Assumptions

ACCEPTED = {"correct", "correct, layout by convention", "real proposed as complex by convention"}


def encode(datatype: str, signal: str, seed: int = 0, n: int = 16384) -> bytes:
    fmt = SampleFormat.parse(datatype)
    make = (COMPLEX_SIGNALS if fmt.is_complex else REAL_SIGNALS)[signal]
    x = make(np.random.default_rng(seed), n)
    level = levels_dbfs(fmt)[0]
    return fmt.encode(x / np.sqrt(np.mean(np.abs(x) ** 2)) * 10 ** (level / 20))


def sniff_bytes(data: bytes):
    return sniff_blocks([data[i : i + BLOCK_BYTES] for i in range(0, len(data), BLOCK_BYTES)])


@pytest.mark.parametrize("datatype", ALL_DATATYPES)
def test_every_datatype_is_identified_on_a_structured_signal(datatype: str) -> None:
    signal = "qpsk, 2 sps, offset 0.2" if datatype[0] == "c" else "real if qpsk at 0.2"
    param = sniff_bytes(encode(datatype, signal)).datatype
    assert (param.level, param.value, param.convention) == (
        EvidenceLevel.HYPOTHESIS,
        datatype,
        None,
    )


@pytest.mark.parametrize("datatype", ALL_DATATYPES)
def test_noise_never_yields_a_wrong_format(datatype: str) -> None:
    level = levels_dbfs(SampleFormat.parse(datatype))[0]
    assert outcome(Case(datatype, "noise", level, 0, encode(datatype, "noise"))) in ACCEPTED


def test_indistinguishable_layouts_propose_complex_and_say_why() -> None:
    param = sniff_bytes(encode("ri16_le", "noise")).datatype
    assert (param.level, param.value) == (EvidenceLevel.HYPOTHESIS, "ci16_le")
    assert param.convention and "ri16_le" in param.convention
    assert "can't tell them apart" in param.convention
    assert "ri16_le" in {a.value for a in param.alternatives}


def test_random_bytes_are_unknown() -> None:
    data = np.random.default_rng(0).integers(0, 256, 200_000, dtype=np.uint8).tobytes()
    param = sniff_bytes(data).datatype
    assert param.level is EvidenceLevel.UNKNOWN
    assert "look random" in param.evidence[0]
    assert param.resolve_hint


def test_too_short_is_unknown() -> None:
    param = sniff_bytes(bytes(MIN_BYTES - 1)).datatype
    assert param.level is EvidenceLevel.UNKNOWN
    assert "too short" in param.evidence[0]


def test_wav_header_is_detected_and_refused_as_raw(tmp_path: Path) -> None:
    header = b"RIFF" + (1000).to_bytes(4, "little") + b"WAVEfmt "
    assert detect_container(header) == "wav"
    assert detect_container(b"\x00" * 12) is None
    path = tmp_path / "x.dat"
    path.write_bytes(header + bytes(2000))
    assert sniff(path).datatype.level is EvidenceLevel.UNKNOWN
    with pytest.raises(ValueError, match="WAV"):
        read_raw(path)


def test_large_files_are_sampled_not_loaded(tmp_path: Path) -> None:
    path = tmp_path / "big.cu8"
    block = encode("cu8", "tone in noise", n=1 << 16)
    path.write_bytes(block * 32)  # 4 MiB
    result = sniff(path)
    assert result.bytes_scored == BLOCKS * BLOCK_BYTES
    assert result.datatype.value == "cu8"


@pytest.mark.parametrize("is_complex", [False, True])
def test_levinson_matches_the_known_ar1_innovation(is_complex: bool) -> None:
    rng = np.random.default_rng(2)
    n, pole = 200_000, (0.9 * np.exp(0.4j) if is_complex else 0.9)
    e = rng.standard_normal(n) + (1j * rng.standard_normal(n) if is_complex else 0)
    x = np.zeros(n, dtype=complex if is_complex else float)
    for i in range(1, n):
        x[i] = pole * x[i - 1] + e[i]
    assert prediction_error(x) == pytest.approx(np.mean(np.abs(e) ** 2), rel=0.01)


def test_raw_assumptions_state_every_layout_fact(tmp_path: Path) -> None:
    path = tmp_path / "capture.bin"
    path.write_bytes(encode("ci16_le", "tone in noise"))
    a = read_raw(path).assumptions
    Assumptions.model_validate(a.model_dump())
    assert (a.datatype.value, a.datatype.level) == ("ci16_le", EvidenceLevel.HYPOTHESIS)
    assert (a.data_offset.value, a.data_offset.level) == (0, EvidenceLevel.HYPOTHESIS)
    assert a.sample_rate.level is EvidenceLevel.UNKNOWN and a.sample_rate.resolve_hint
    assert a.center_frequency.level is EvidenceLevel.UNKNOWN
    assert a.iq_order is not None and a.iq_order.level is EvidenceLevel.HYPOTHESIS


def test_raw_file_that_cannot_be_sniffed_leaves_iq_order_unknown(tmp_path: Path) -> None:
    path = tmp_path / "noise.bin"
    path.write_bytes(np.random.default_rng(1).integers(0, 256, 100_000, dtype=np.uint8).tobytes())
    a = read_raw(path).assumptions
    assert a.datatype.level is EvidenceLevel.UNKNOWN
    assert a.iq_order is not None and a.iq_order.level is EvidenceLevel.UNKNOWN
