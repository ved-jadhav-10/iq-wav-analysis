"""NumPy .npy, SDRangel .sdriq and MIDAS Blue readers, against files of known content."""

import struct
import zlib
from pathlib import Path

import numpy as np
import pytest

from dsp.evidence import EvidenceLevel
from dsp.ingest.blue import read_blue
from dsp.ingest.formats import SampleFormat
from dsp.ingest.npy import read_npy
from dsp.ingest.recording import Recording
from dsp.ingest.sdriq import read_sdriq
from dsp.results import Results

N = 2000


def tone(n: int = N) -> np.ndarray:
    return 0.5 * np.exp(2j * np.pi * 0.011 * np.arange(n))


def samples_of(rec: Recording) -> np.ndarray:
    with rec.reader() as reader:
        return reader.read(0, reader.num_samples)


def review(rec: Recording) -> set[str]:
    results = Results(sanket_version="0.1.0", assumptions=rec.assumptions, stages=())
    return {item.parameter for item in results.needs_review}


# -- NumPy .npy (written by NumPy itself) ------------------------------------------------------


@pytest.mark.parametrize(
    ("dtype", "datatype"),
    [("<c8", "cf32_le"), ("<c16", "cf64_le"), (">c8", "cf32_be"), ("<f4", "rf32_le"),
     ("<i2", "ri16_le"), (">i2", "ri16_be"), ("|u1", "ru8"), ("|i1", "ri8")],
)  # fmt: skip
def test_npy_one_dimensional_arrays_are_measured(tmp_path: Path, dtype: str, datatype: str) -> None:
    x = tone() if dtype[1] == "c" else np.real(tone())
    fmt = SampleFormat.parse(datatype)
    raw = np.frombuffer(fmt.encode(x), dtype=np.dtype(dtype))
    path = tmp_path / "x.npy"
    np.save(path, raw)
    rec = read_npy(path)
    assert (rec.datatype.value, rec.datatype.level) == (datatype, EvidenceLevel.MEASURED)
    assert rec.data_offset.level is EvidenceLevel.MEASURED
    assert rec.sample_rate.level is EvidenceLevel.UNKNOWN
    lsb = 1e-6 if fmt.kind == "f" else 2.0 ** (1 - fmt.bits)
    np.testing.assert_allclose(samples_of(rec), x, atol=lsb)
    assert review(rec) == set()


def test_npy_two_columns_are_iq_by_convention(tmp_path: Path) -> None:
    x = tone()
    path = tmp_path / "iq_fs=2.4M.npy"
    np.save(path, np.stack([np.real(x), np.imag(x)], axis=1).astype("<f4"))
    rec = read_npy(path)
    assert (rec.datatype.value, rec.datatype.level) == ("cf32_le", EvidenceLevel.HYPOTHESIS)
    assert review(rec) == {"datatype", "iq_order"}
    assert rec.sample_rate.alternatives[0].value == 2.4e6
    np.testing.assert_allclose(samples_of(rec), x, atol=1e-6)


@pytest.mark.parametrize(
    ("array", "why"),
    [
        (np.zeros((2, 100), "<f4"), "planar"),
        (np.asfortranarray(np.zeros((100, 2), "<f4")), "planar"),
        (np.zeros((4, 5, 6), "<f4"), "3-dimensional"),
        (np.zeros(100, "<i8"), "no sample format"),
        (np.zeros(100, "<f2"), "no sample format"),
        (np.zeros(100, [("a", "<f4"), ("b", "<i2")]), "Structured"),
    ],
)
def test_npy_arrays_without_one_sample_stream_are_unknown(
    tmp_path: Path, array: np.ndarray, why: str
) -> None:
    path = tmp_path / "x.npy"
    np.save(path, array)
    rec = read_npy(path)
    assert rec.datatype.level is EvidenceLevel.UNKNOWN
    assert why in rec.datatype.evidence[0]
    assert rec.datatype.resolve_hint


def test_npy_truncated_data_is_warned_and_clamped(tmp_path: Path) -> None:
    path = tmp_path / "x.npy"
    np.save(path, tone().astype("<c8"))
    path.write_bytes(path.read_bytes()[:-800])
    rec = read_npy(path)
    assert "truncated" in rec.datatype.warnings[0]
    assert len(samples_of(rec)) == N - 100


def test_npy_that_isnt_one_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "x.npy"
    path.write_bytes(b"not numpy at all")
    with pytest.raises(ValueError, match="not a NumPy"):
        read_npy(path)


# -- SDRangel .sdriq ---------------------------------------------------------------------------


def sdriq(path: Path, data: bytes, *, rate: int = 250_000, bits: int = 16, bad_crc: bool = False):
    head = struct.pack("<IQQII", rate, 145_800_000, 1_700_000_000_123, bits, 0)
    crc = zlib.crc32(head) ^ (1 if bad_crc else 0)
    path.write_bytes(head + struct.pack("<I", crc) + data)
    return path


def test_sdriq_16_bit_header_is_measured(tmp_path: Path) -> None:
    x = tone()
    rec = read_sdriq(sdriq(tmp_path / "x.sdriq", SampleFormat.parse("ci16_le").encode(x)))
    a = rec.assumptions
    assert (rec.datatype.value, rec.datatype.level) == ("ci16_le", EvidenceLevel.MEASURED)
    assert (a.sample_rate.value, a.center_frequency.value) == (250_000.0, 145_800_000.0)
    assert rec.start_time is not None and rec.start_time.value == "2023-11-14T22:13:20.123Z"
    np.testing.assert_allclose(samples_of(rec), x, atol=2**-15)
    assert review(rec) == set()


def test_sdriq_24_bit_is_32_bit_words_with_a_level_warning(tmp_path: Path) -> None:
    words = np.round(np.stack([np.real(tone()), np.imag(tone())], 1).ravel() * 2**23).astype("<i4")
    rec = read_sdriq(sdriq(tmp_path / "x.sdriq", words.tobytes(), bits=24))
    assert rec.datatype.value == "ci32_le"
    assert "48 dB" in rec.datatype.warnings[0]
    np.testing.assert_allclose(samples_of(rec) * 256, tone(), atol=2**-22)


def test_sdriq_with_a_bad_crc_is_only_a_hypothesis(tmp_path: Path) -> None:
    rec = read_sdriq(sdriq(tmp_path / "x.sdriq", bytes(400), bad_crc=True))
    assert rec.datatype.level is EvidenceLevel.HYPOTHESIS
    assert rec.sample_rate.level is EvidenceLevel.HYPOTHESIS
    assert "mismatch" in rec.datatype.evidence[0]


def test_sdriq_odd_sample_size_is_unknown(tmp_path: Path) -> None:
    rec = read_sdriq(sdriq(tmp_path / "x.sdriq", bytes(400), bits=12))
    assert rec.datatype.level is EvidenceLevel.UNKNOWN


# -- MIDAS Blue --------------------------------------------------------------------------------


def blue(
    path: Path,
    data: bytes,
    *,
    code: str = "CI",
    rep: str = "EEEI",
    xdelta: float = 1 / 2.4e6,
    xunits: int = 1,
    file_type: int = 1000,
    keywords: str = "",
    extended: dict[str, float] | None = None,
    detached: bool = False,
    claimed: int | None = None,
) -> Path:
    o = "<" if rep == "EEEI" else ">"
    ext = b""
    for tag, value in (extended or {}).items():
        body = struct.pack(o + "d", value)
        pad = (-(8 + len(body) + len(tag))) % 8
        lkey = 8 + len(body) + len(tag) + pad
        ext += struct.pack(o + "ihbc", lkey, lkey - len(body), len(tag), b"D") + body
        ext += tag.encode() + bytes(pad)
    data_start = 512
    ext_start = 0 if not ext else (512 + (0 if detached else len(data)) + 511) // 512
    hcb = bytearray(512)
    hcb[0:12] = b"BLUE" + rep.encode() + rep.encode()
    struct.pack_into(o + "5i", hcb, 12, int(detached), 0, 0, ext_start, len(ext))
    size = len(data) if claimed is None else claimed
    struct.pack_into(o + "dd", hcb, 32, 0.0 if detached else data_start, size)
    struct.pack_into(o + "i", hcb, 48, file_type)
    hcb[52:54] = code.encode()
    struct.pack_into(o + "i", hcb, 160, len(keywords))
    hcb[164 : 164 + len(keywords)] = keywords.encode()
    struct.pack_into(o + "ddi", hcb, 256, 0.0, xdelta, xunits)
    body = bytes(hcb) + (b"" if detached else data)
    if ext:
        body += bytes(ext_start * 512 - len(body)) + ext
    path.write_bytes(body)
    if detached:
        path.with_suffix(".det").write_bytes(data)
    return path


@pytest.mark.parametrize(
    ("code", "rep", "datatype"),
    [("CI", "EEEI", "ci16_le"), ("CF", "IEEE", "cf32_be"), ("SB", "EEEI", "ri8"),
     ("SD", "IEEE", "rf64_be"), ("CL", "EEEI", "ci32_le")],
)  # fmt: skip
def test_blue_formats_and_byte_orders(tmp_path: Path, code: str, rep: str, datatype: str) -> None:
    fmt = SampleFormat.parse(datatype)
    x = tone() if fmt.is_complex else np.real(tone())
    rec = read_blue(blue(tmp_path / "x.blue", fmt.encode(x), code=code, rep=rep))
    assert (rec.datatype.value, rec.datatype.level) == (datatype, EvidenceLevel.MEASURED)
    assert (rec.sample_rate.value, rec.sample_rate.level) == (2.4e6, EvidenceLevel.MEASURED)
    lsb = 1e-6 if fmt.kind == "f" else 2.0 ** (1 - fmt.bits)
    np.testing.assert_allclose(samples_of(rec), x, atol=lsb)


@pytest.mark.parametrize("where", ["main", "extended"])
def test_blue_rf_freq_keyword_gives_the_centre_frequency(tmp_path: Path, where: str) -> None:
    data = SampleFormat.parse("ci16_le").encode(tone())
    path = blue(
        tmp_path / "x.blue",
        data,
        keywords="RF_FREQ=162025000.0\x00" if where == "main" else "",
        extended={"RF_FREQ": 162_025_000.0, "GAIN": 20.0} if where == "extended" else None,
    )
    center = read_blue(path).center_frequency
    assert (center.value, center.level) == (162_025_000.0, EvidenceLevel.MEASURED)


def test_blue_without_a_time_interval_leaves_the_rate_unknown(tmp_path: Path) -> None:
    rec = read_blue(blue(tmp_path / "x.blue", bytes(800), xunits=3))
    assert rec.sample_rate.level is EvidenceLevel.UNKNOWN
    assert rec.sample_rate.alternatives


def test_blue_framed_type_2000_is_unknown(tmp_path: Path) -> None:
    rec = read_blue(blue(tmp_path / "x.blue", bytes(800), file_type=2000))
    assert rec.datatype.level is EvidenceLevel.UNKNOWN
    assert "frames" in rec.datatype.evidence[0]


def test_blue_detached_data_is_read_from_the_det_file(tmp_path: Path) -> None:
    x = tone()
    rec = read_blue(
        blue(tmp_path / "x.tmp", SampleFormat.parse("ci16_le").encode(x), detached=True)
    )
    np.testing.assert_allclose(samples_of(rec), x, atol=2**-15)


def test_blue_truncated_data_is_warned(tmp_path: Path) -> None:
    data = SampleFormat.parse("ci16_le").encode(tone())
    rec = read_blue(blue(tmp_path / "x.blue", data, claimed=len(data) * 2))
    assert "truncated" in rec.datatype.warnings[0]
    assert len(samples_of(rec)) == N


def test_not_a_blue_file_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "x.blue"
    path.write_bytes(bytes(1000))
    with pytest.raises(ValueError, match="not a MIDAS Blue"):
        read_blue(path)
