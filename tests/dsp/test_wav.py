import struct
import wave
from pathlib import Path

import numpy as np
import pytest

from dsp.evidence import EvidenceLevel
from dsp.ingest.formats import SampleFormat
from dsp.ingest.raw import read_raw
from dsp.ingest.sniff import detect_container, sniff
from dsp.ingest.wav import (
    AUDIO_IMPROPRIETY,
    W64_RIFF,
    W64_WAVE,
    WavError,
    read_header,
    read_wav,
)
from dsp.results import NO_FILES, Assumptions, Results
from dsp.synth.waveforms import awgn, frequency_shift, psk_symbols, shape

N = 1 << 15
_TAIL = bytes.fromhex("f3acd3118cd100c04f8edb8a")
_SUBFORMAT_TAIL = bytes.fromhex("000000001000800000aa00389b71")


def qpsk(seed: int = 0, offset: float = 0.1, n: int = N) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = frequency_shift(shape(psk_symbols(rng, n // 4 + 1, 4), 4, 0.35)[:n], offset)
    x = x + awgn(rng, n, 0.01)
    return 0.3 * x / np.sqrt(np.mean(np.abs(x) ** 2))


def auxi_body(center: int, start: tuple[int, ...] = (2024, 3, 5, 14, 9, 30, 250)) -> bytes:
    """SYSTEMTIME start and stop, then CenterFreq, ADFrequency, IFFrequency, Bandwidth, IQOffset."""
    year, month, day, hour, minute, second, ms = start
    systemtime = struct.pack("<8H", year, month, 2, day, hour, minute, second, ms)
    return systemtime * 2 + struct.pack("<5I", center, 64_000_000, 0, 200_000, 0) + bytes(16)


def fmt_body(tag: int, channels: int, rate: int, bits: int, order: str, extensible: bool) -> bytes:
    align = channels * bits // 8
    base = struct.pack(order + "HHIIHH", 0xFFFE if extensible else tag, channels, rate,
                       rate * align, align, bits)  # fmt: skip
    if not extensible:
        return base
    return base + struct.pack(order + "HHI", 22, bits, 0) + struct.pack("<H", tag) + _SUBFORMAT_TAIL


def make_wav(
    path: Path,
    data: bytes,
    *,
    tag: int = 1,
    channels: int = 2,
    rate: int = 96_000,
    bits: int = 16,
    container: str = "RIFF",
    extensible: bool = False,
    auxi: bytes | None = None,
    auxi_after: bool = False,
    stated_size: int | None = None,
    extra: bytes = b"",
) -> Path:
    """Write a WAV container around `data`; `extra` is a raw chunk placed before fmt."""
    order = ">" if container == "RIFX" else "<"
    fmt = fmt_body(tag, channels, rate, bits, order, extensible)
    if container == "Wave64":

        def w64(fourcc: bytes, body: bytes) -> bytes:
            pad = (-len(body)) % 8
            return fourcc + _TAIL + struct.pack("<Q", 24 + len(body)) + body + bytes(pad)

        body = w64(b"fmt ", fmt)
        body += w64(b"auxi", auxi) if auxi and not auxi_after else b""
        body += w64(b"data", data)
        body += w64(b"auxi", auxi) if auxi and auxi_after else b""
        path.write_bytes(W64_RIFF + struct.pack("<Q", 40 + len(body)) + W64_WAVE + body)
        return path

    def chunk(fourcc: bytes, body: bytes, size: int | None = None) -> bytes:
        return (
            fourcc
            + struct.pack(order + "I", len(body) if size is None else size)
            + body
            + (b"\x00" if len(body) % 2 else b"")
        )

    size = stated_size
    ds64 = b""
    if container in ("RF64", "BW64"):
        size = 0xFFFFFFFF
        ds64 = chunk(b"ds64", struct.pack("<QQQI", 0, len(data), len(data) // 4, 0))
    body = ds64 + extra + chunk(b"fmt ", fmt)
    body += chunk(b"auxi", auxi) if auxi and not auxi_after else b""
    body += chunk(b"data", data, size)
    body += chunk(b"auxi", auxi) if auxi and auxi_after else b""
    riff_size = 0xFFFFFFFF if container in ("RF64", "BW64") else 4 + len(body)
    path.write_bytes(container.encode() + struct.pack(order + "I", riff_size) + b"WAVE" + body)
    return path


def samples_of(path: Path) -> np.ndarray:
    with read_wav(path).reader() as reader:
        return reader.read(0, reader.num_samples)


# -- independent writer: the standard library's wave module ------------------------------------


@pytest.mark.parametrize("width", [1, 2, 3, 4])
def test_stdlib_mono_pcm_is_read_exactly(tmp_path: Path, width: int) -> None:
    fmt = SampleFormat.parse({1: "ru8", 2: "ri16_le", 3: "ri24_le", 4: "ri32_le"}[width])
    x = 0.5 * np.sin(2 * np.pi * 0.01 * np.arange(4000))
    path = tmp_path / "mono.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(width)
        w.setframerate(22_050)
        w.writeframes(fmt.encode(x))
    rec = read_wav(path)
    a = rec.assumptions
    assert (rec.datatype.value, rec.datatype.level) == (fmt.datatype, EvidenceLevel.MEASURED)
    assert (a.sample_rate.value, a.sample_rate.level) == (22_050.0, EvidenceLevel.MEASURED)
    assert (a.data_offset.value, a.data_offset.level) == (44, EvidenceLevel.MEASURED)
    assert a.iq_order is None
    np.testing.assert_allclose(samples_of(path), x, atol=2.0 ** (1 - 8 * width))


def test_stdlib_stereo_iq_is_proposed_as_iq(tmp_path: Path) -> None:
    fmt = SampleFormat.parse("ci16_le")
    x = qpsk()
    path = tmp_path / "iq.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(192_000)
        w.writeframes(fmt.encode(x))
    rec = read_wav(path)
    assert rec.quadrature is not None and rec.quadrature.verdict == "iq"
    assert (rec.datatype.value, rec.datatype.level) == ("ci16_le", EvidenceLevel.HYPOTHESIS)
    assert rec.datatype.convention is None
    np.testing.assert_allclose(samples_of(path), x, atol=2**-15)


# -- encodings and containers ------------------------------------------------------------------


ENCODINGS = [(1, 8, "u"), (1, 16, "i"), (1, 24, "i"), (1, 32, "i"), (3, 32, "f"), (3, 64, "f")]


@pytest.mark.parametrize(("tag", "bits", "kind"), ENCODINGS)
@pytest.mark.parametrize("extensible", [False, True])
@pytest.mark.parametrize("channels", [1, 2])
def test_every_encoding_decodes_to_the_source(
    tmp_path: Path, tag: int, bits: int, kind: str, extensible: bool, channels: int
) -> None:
    endian = "" if bits == 8 else "_le"
    fmt = SampleFormat.parse(f"{'c' if channels == 2 else 'r'}{kind}{bits}{endian}")
    x = qpsk() if channels == 2 else np.real(qpsk())
    path = make_wav(
        tmp_path / "x.wav", fmt.encode(x), tag=tag, channels=channels, bits=bits,
        extensible=extensible,
    )  # fmt: skip
    rec = read_wav(path)
    assert rec.datatype.value == fmt.datatype
    lsb = 1e-6 if kind == "f" else 2.0 ** (1 - bits)
    np.testing.assert_allclose(samples_of(path), x, atol=lsb)


@pytest.mark.parametrize("container", ["RIFX", "RF64", "BW64", "Wave64"])
def test_every_container_reads_the_same_samples(tmp_path: Path, container: str) -> None:
    fmt = SampleFormat.parse("ci16_be" if container == "RIFX" else "ci16_le")
    x = qpsk()
    path = make_wav(tmp_path / "x.wav", fmt.encode(x), container=container)
    rec = read_wav(path)
    assert rec.header.container == container
    assert rec.datatype.value == fmt.datatype
    assert rec.header.warnings == ()
    np.testing.assert_allclose(samples_of(path), x, atol=2**-15)
    assert detect_container(path.read_bytes()[:40]) == "wav"


def test_auxi_chunk_gives_measured_centre_frequency_and_start_time(tmp_path: Path) -> None:
    for after in (False, True):
        path = make_wav(
            tmp_path / f"a{after}.wav", SampleFormat.parse("ci16_le").encode(qpsk()),
            auxi=auxi_body(7_100_000), auxi_after=after,
        )  # fmt: skip
        rec = read_wav(path)
        center = rec.assumptions.center_frequency
        assert (center.value, center.level) == (7_100_000.0, EvidenceLevel.MEASURED)
        assert rec.start_time is not None
        assert rec.start_time.value == "2024-03-05T14:09:30.250"
        assert "time zone" in rec.start_time.warnings[0]


def test_auxi_with_an_invalid_time_has_no_start_time(tmp_path: Path) -> None:
    path = make_wav(
        tmp_path / "x.wav", SampleFormat.parse("ci16_le").encode(qpsk()),
        auxi=auxi_body(100_000_000, start=(0, 0, 0, 0, 0, 0, 0)),
    )  # fmt: skip
    rec = read_wav(path)
    assert rec.start_time is None
    assert rec.assumptions.center_frequency.value == 100_000_000.0


def test_without_auxi_the_centre_frequency_comes_from_the_name_or_is_unknown(
    tmp_path: Path,
) -> None:
    data = SampleFormat.parse("ci16_le").encode(qpsk())
    named = read_wav(make_wav(tmp_path / "HDSDR_20240305_140930Z_7100kHz_RF.wav", data))
    center = named.assumptions.center_frequency
    assert (center.value, center.level) == (None, EvidenceLevel.UNKNOWN)
    assert [a.value for a in center.alternatives] == [7_100_000.0]
    bare = read_wav(make_wav(tmp_path / "x.wav", data)).assumptions.center_frequency
    assert bare.level is EvidenceLevel.UNKNOWN and bare.alternatives == ()


def test_odd_sized_chunks_are_padded(tmp_path: Path) -> None:
    x = qpsk()
    extra = b"LIST" + struct.pack("<I", 5) + b"INFOx\x00"
    path = make_wav(tmp_path / "x.wav", SampleFormat.parse("ci16_le").encode(x), extra=extra)
    np.testing.assert_allclose(samples_of(path), x, atol=2**-15)


# -- damaged and unfinished files --------------------------------------------------------------


def test_truncated_data_is_clamped_with_a_warning(tmp_path: Path) -> None:
    data = SampleFormat.parse("ci16_le").encode(qpsk())
    path = make_wav(tmp_path / "x.wav", data, stated_size=len(data) * 2)
    rec = read_wav(path)
    assert rec.header.data_bytes == len(data)
    assert any("truncated" in w for w in rec.datatype.warnings)


@pytest.mark.parametrize("stated", [0, 0xFFFFFFFF])
def test_unstated_data_size_runs_to_the_end_with_a_warning(tmp_path: Path, stated: int) -> None:
    x = qpsk()
    path = make_wav(tmp_path / "x.wav", SampleFormat.parse("ci16_le").encode(x), stated_size=stated)
    rec = read_wav(path)
    assert any("doesn't state its size" in w for w in rec.datatype.warnings)
    np.testing.assert_allclose(samples_of(path), x, atol=2**-15)


@pytest.mark.parametrize(
    ("data", "match"),
    [
        (b"RIFF\x04\x00\x00\x00WAVE", "no complete fmt chunk"),
        (b"RIFF\x1c\x00\x00\x00WAVEfmt \x10\x00\x00\x00" + bytes(16), "no data chunk"),
        (b"not a wav file at all, just bytes", "not a WAV file"),
    ],
)
def test_broken_containers_are_refused(tmp_path: Path, data: bytes, match: str) -> None:
    path = tmp_path / "x.wav"
    path.write_bytes(data)
    with pytest.raises(WavError, match=match):
        read_header(path)


@pytest.mark.parametrize(
    ("tag", "channels", "bits", "hint"),
    [(7, 1, 8, "Convert"), (1, 3, 16, "Extract one channel"), (1, 1, 12, "Convert")],
)
def test_undecodable_encodings_are_unknown_and_say_why(
    tmp_path: Path, tag: int, channels: int, bits: int, hint: str
) -> None:
    path = make_wav(tmp_path / "x.wav", bytes(3000), tag=tag, channels=channels, bits=bits)
    rec = read_wav(path)
    assert rec.datatype.level is EvidenceLevel.UNKNOWN
    assert rec.datatype.resolve_hint and hint in rec.datatype.resolve_hint
    a = rec.assumptions
    assert a.iq_order is not None and a.iq_order.level is EvidenceLevel.UNKNOWN
    with pytest.raises(ValueError, match="UNKNOWN"):
        rec.reader()


def test_a_zero_header_rate_is_unknown_with_candidates(tmp_path: Path) -> None:
    path = make_wav(tmp_path / "x.wav", SampleFormat.parse("ci16_le").encode(qpsk()), rate=0)
    rate = read_wav(path).assumptions.sample_rate
    assert rate.level is EvidenceLevel.UNKNOWN
    assert rate.alternatives and rate.resolve_hint


# -- quadrature check --------------------------------------------------------------------------


def stereo(path: Path, left: np.ndarray, right: np.ndarray) -> Path:
    return make_wav(path, SampleFormat.parse("ci16_le").encode(left + 1j * right))


def test_identical_channels_are_not_taken_as_iq(tmp_path: Path) -> None:
    a = np.real(qpsk())
    rec = read_wav(stereo(tmp_path / "x.wav", a, a))
    assert rec.quadrature is not None and rec.quadrature.identical
    assert rec.datatype.level is EvidenceLevel.UNKNOWN
    assert [alt.value for alt in rec.datatype.alternatives] == ["ci16_le"]
    assert rec.datatype.resolve_hint and "ri16_le" in rec.datatype.resolve_hint


def test_a_silent_channel_is_not_taken_as_iq(tmp_path: Path) -> None:
    rec = read_wav(stereo(tmp_path / "x.wav", np.real(qpsk()), np.zeros(N)))
    assert rec.datatype.level is EvidenceLevel.UNKNOWN
    assert "silent" in rec.datatype.evidence[-1]


@pytest.mark.parametrize("delay", [0, 5, 100])
def test_delayed_stereo_audio_is_not_taken_as_iq(tmp_path: Path, delay: int) -> None:
    rng = np.random.default_rng(3)
    sound = np.convolve(rng.standard_normal(N + delay), np.ones(8) / 8, "same")
    left = sound[delay:] + 0.05 * rng.standard_normal(N)
    right = sound[:N] + 0.05 * rng.standard_normal(N)
    rec = read_wav(stereo(tmp_path / "x.wav", 0.3 * left, 0.3 * right))
    assert rec.quadrature is not None and rec.quadrature.impropriety > AUDIO_IMPROPRIETY
    assert rec.datatype.level is EvidenceLevel.UNKNOWN


def test_centred_iq_is_proposed_by_convention_and_listed_for_review(tmp_path: Path) -> None:
    x = qpsk(offset=0.0)
    rec = read_wav(stereo(tmp_path / "x.wav", np.real(x), np.imag(x)))
    assert rec.quadrature is not None and rec.quadrature.verdict == "inconclusive"
    assert (rec.datatype.value, rec.datatype.level) == ("ci16_le", EvidenceLevel.HYPOTHESIS)
    assert rec.datatype.convention
    results = Results(
        sanket_version="0.1.0",
        recording=NO_FILES,
        catalogues=(),
        assumptions=rec.assumptions,
        stages=(),
    )
    assert {item.parameter for item in results.needs_review} == {"datatype", "iq_order"}


def test_offset_iq_leaves_only_the_iq_order_for_review(tmp_path: Path) -> None:
    x = qpsk()
    rec = read_wav(stereo(tmp_path / "x.wav", np.real(x), np.imag(x)))
    results = Results(
        sanket_version="0.1.0",
        recording=NO_FILES,
        catalogues=(),
        assumptions=rec.assumptions,
        stages=(),
    )
    assert [item.parameter for item in results.needs_review] == ["iq_order"]
    Assumptions.model_validate(rec.assumptions.model_dump())


def test_quadrature_check_reads_a_bounded_sample_of_a_long_file(tmp_path: Path) -> None:
    x = qpsk(n=1 << 19)
    rec = read_wav(stereo(tmp_path / "x.wav", np.real(x), np.imag(x)))
    assert rec.quadrature is not None and rec.quadrature.frames == 4 * (1 << 16)


# -- the raw path refuses WAV containers -------------------------------------------------------


@pytest.mark.parametrize("container", ["RIFF", "RIFX", "RF64", "Wave64"])
def test_raw_ingest_refuses_every_wav_container(tmp_path: Path, container: str) -> None:
    path = make_wav(
        tmp_path / "x.bin", SampleFormat.parse("ci16_le").encode(qpsk()), container=container
    )
    assert sniff(path).container == "wav"
    with pytest.raises(ValueError, match="WAV"):
        read_raw(path)


def test_an_unrecognised_extensible_sub_format_is_unknown(tmp_path: Path) -> None:
    path = make_wav(tmp_path / "x.wav", bytes(4000), tag=0x0055, extensible=True)
    rec = read_wav(path)
    assert rec.datatype.level is EvidenceLevel.UNKNOWN
    assert "format tag 0x0055" in rec.datatype.evidence[1]


def test_a_corrupt_chunk_size_is_not_loaded(tmp_path: Path) -> None:
    x = qpsk()
    huge = b"auxi" + struct.pack("<I", 0x7FFFFFF0) + auxi_body(1_000_000)
    path = make_wav(tmp_path / "x.wav", SampleFormat.parse("ci16_le").encode(x))
    path.write_bytes(path.read_bytes() + huge)
    rec = read_wav(path)
    assert rec.header.auxi is not None and rec.header.auxi.center_frequency == 1_000_000
    np.testing.assert_allclose(samples_of(path), x, atol=2**-15)
