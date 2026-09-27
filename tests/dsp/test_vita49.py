import struct
from pathlib import Path

import numpy as np
import pytest

from dsp.evidence import EvidenceLevel
from dsp.ingest.formats import SampleFormat
from dsp.ingest.vita49 import read_vita49
from dsp.synth.waveforms import awgn, frequency_shift, psk_symbols, shape

CI16_BE = SampleFormat.parse("ci16_be")
SID = 0x0000_0A01
RADIX = 1 << 20


def qpsk(n: int = 8192) -> np.ndarray:
    rng = np.random.default_rng(4)
    x = frequency_shift(shape(psk_symbols(rng, n // 4 + 1, 4), 4, 0.35)[:n], 0.1)
    x = x + awgn(rng, n, 0.01)
    return 0.3 * x / np.sqrt(np.mean(np.abs(x) ** 2))


def header(kind: int, words: int, *, cls: bool, trailer: bool, count: int) -> bytes:
    word = kind << 28 | cls << 27 | trailer << 26 | 1 << 22 | 1 << 20 | (count & 0xF) << 16
    return struct.pack(">I", word | words)


def data_packet(payload: bytes, count: int, sid: int | None = SID, trailer: bool = True) -> bytes:
    kind = 0 if sid is None else 1
    prologue = (struct.pack(">I", sid) if sid is not None else b"") + bytes(8)  # class ID
    prologue += struct.pack(">IQ", 1_700_000_000, count * 1000)  # TSI and TSF
    tail = struct.pack(">I", 0) if trailer else b""
    words = 1 + (len(prologue) + len(payload) + len(tail)) // 4
    return header(kind, words, cls=True, trailer=trailer, count=count) + prologue + payload + tail


def payload_format(complexity: int = 1, item_format: int = 0, bits: int = 16) -> int:
    w1 = complexity << 29 | item_format << 24 | (bits - 1) << 6 | (bits - 1)
    return w1 << 32


def context_packet(
    *, rate: float | None = 2.4e6, rf: float | None = 162e6, fmt: int | None = None
) -> bytes:
    cif0, fields = 0, b""
    cif0 |= 1 << 29
    fields += struct.pack(">q", int(200e3 * RADIX))  # bandwidth
    if rf is not None:
        cif0 |= 1 << 27
        fields += struct.pack(">q", int(rf * RADIX))
    cif0 |= 1 << 23
    fields += struct.pack(">I", 0)  # gain, one word, skipped
    if rate is not None:
        cif0 |= 1 << 21
        fields += struct.pack(">q", int(rate * RADIX))
    if fmt is not None:
        cif0 |= 1 << 15
        fields += struct.pack(">Q", fmt)
    body = struct.pack(">I", SID) + bytes(8) + struct.pack(">IQ", 0, 0) + struct.pack(">I", cif0)
    body += fields
    return header(4, 1 + len(body) // 4, cls=True, trailer=False, count=0) + body


def recording(x: np.ndarray, per_packet: int = 500, sid: int | None = SID, trailer: bool = True):
    raw = CI16_BE.encode(x)
    size = per_packet * 4
    return [
        data_packet(raw[i : i + size], k, sid, trailer)
        for k, i in enumerate(range(0, len(raw), size))
    ]


def samples_of(path: Path) -> np.ndarray:
    with read_vita49(path).reader() as reader:
        return reader.read(0, reader.num_samples)


def test_context_and_data_packets_give_measured_parameters_and_exact_samples(
    tmp_path: Path,
) -> None:
    x = qpsk()
    path = tmp_path / "x.vrt"
    path.write_bytes(context_packet(fmt=payload_format()) + b"".join(recording(x)))
    rec = read_vita49(path)
    a = rec.assumptions
    assert (rec.datatype.value, rec.datatype.level) == ("ci16_be", EvidenceLevel.MEASURED)
    assert (a.sample_rate.value, a.sample_rate.level) == (2.4e6, EvidenceLevel.MEASURED)
    assert (a.center_frequency.value, a.center_frequency.level) == (162e6, EvidenceLevel.MEASURED)
    assert a.iq_order is not None and a.iq_order.convention is None
    np.testing.assert_allclose(samples_of(path), x, atol=2**-15)


def test_packets_without_stream_id_or_trailer(tmp_path: Path) -> None:
    x = qpsk()
    path = tmp_path / "x.vrt"
    body = b"".join(recording(x, per_packet=333, sid=None, trailer=False))
    path.write_bytes(context_packet(fmt=payload_format()) + body)
    np.testing.assert_allclose(samples_of(path), x, atol=2**-15)


def test_without_a_payload_format_the_sniffer_proposes_one(tmp_path: Path) -> None:
    x = qpsk()
    path = tmp_path / "x.vrt"
    path.write_bytes(context_packet(fmt=None) + b"".join(recording(x)))
    rec = read_vita49(path)
    assert (rec.datatype.value, rec.datatype.level) == ("ci16_be", EvidenceLevel.HYPOTHESIS)
    assert any("format sniffer" in e for e in rec.datatype.evidence)
    iq = rec.assumptions.iq_order
    assert iq is not None and iq.convention  # listed for review


def test_without_context_rate_and_frequency_are_unknown(tmp_path: Path) -> None:
    path = tmp_path / "x.vrt"
    path.write_bytes(b"".join(recording(qpsk())))
    a = read_vita49(path).assumptions
    assert a.sample_rate.level is EvidenceLevel.UNKNOWN
    assert a.center_frequency.level is EvidenceLevel.UNKNOWN


def test_only_the_first_stream_is_read_and_others_are_warned(tmp_path: Path) -> None:
    x, y = qpsk(), qpsk()[::-1]
    mine, other = recording(x), recording(y, sid=0xBEEF)
    interleaved = b"".join(p for pair in zip(mine, other, strict=True) for p in pair)
    path = tmp_path / "x.vrt"
    path.write_bytes(context_packet(fmt=payload_format()) + interleaved)
    rec = read_vita49(path)
    assert any("other data stream" in w for w in rec.datatype.warnings)
    np.testing.assert_allclose(samples_of(path), x, atol=2**-15)


def test_vrl_frames_are_unwrapped(tmp_path: Path) -> None:
    x = qpsk()
    packets = [context_packet(fmt=payload_format()), *recording(x)]
    frames = b""
    for k in range(0, len(packets), 4):
        body = b"".join(packets[k : k + 4])
        words = 3 + len(body) // 4
        frames += b"VRLP" + struct.pack(">I", (k // 4) << 20 | words) + body + b"VEND"
    path = tmp_path / "x.vrl"
    path.write_bytes(frames)
    np.testing.assert_allclose(samples_of(path), x, atol=2**-15)


def test_trailing_garbage_stops_reading_with_a_warning(tmp_path: Path) -> None:
    x = qpsk()
    path = tmp_path / "x.vrt"
    path.write_bytes(context_packet(fmt=payload_format()) + b"".join(recording(x)) + b"\xff" * 10)
    rec = read_vita49(path)
    assert any("don't form a VITA 49 packet" in w for w in rec.datatype.warnings)
    np.testing.assert_allclose(samples_of(path), x, atol=2**-15)


@pytest.mark.parametrize(
    "fmt", [payload_format(complexity=2), payload_format(bits=12), payload_format(item_format=1)]
)
def test_undecodable_payload_formats_are_unknown(tmp_path: Path, fmt: int) -> None:
    path = tmp_path / "x.vrt"
    path.write_bytes(context_packet(fmt=fmt) + b"".join(recording(qpsk())))
    rec = read_vita49(path)
    assert rec.datatype.level is EvidenceLevel.UNKNOWN
    assert rec.datatype.resolve_hint


def test_float_payloads(tmp_path: Path) -> None:
    x = qpsk()
    raw = SampleFormat.parse("cf32_be").encode(x)
    packets = [data_packet(raw[i : i + 4000], k) for k, i in enumerate(range(0, len(raw), 4000))]
    path = tmp_path / "x.vrt"
    path.write_bytes(
        context_packet(fmt=payload_format(item_format=0x0E, bits=32)) + b"".join(packets)
    )
    assert read_vita49(path).datatype.value == "cf32_be"
    np.testing.assert_allclose(samples_of(path), x, atol=1e-6)


def test_a_file_that_isnt_vita49_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "x.vrt"
    path.write_bytes(bytes(4000))
    with pytest.raises(ValueError, match="VITA 49"):
        read_vita49(path)
