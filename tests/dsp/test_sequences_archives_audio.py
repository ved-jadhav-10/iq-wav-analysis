import gzip
import stat
import wave
import zipfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from dsp.evidence import EvidenceLevel
from dsp.ingest.archives import ArchiveError, decompress, unpacked_size
from dsp.ingest.audio import read_audio
from dsp.ingest.formats import SampleFormat
from dsp.ingest.sequence import numbered_sequence, read_sequence
from dsp.synth.waveforms import awgn, frequency_shift, psk_symbols, shape

CU8 = SampleFormat.parse("cu8")
CI16 = SampleFormat.parse("ci16_le")


def qpsk(n: int = 1 << 15, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = frequency_shift(shape(psk_symbols(rng, n // 4 + 1, 4), 4, 0.35)[:n], 0.1)
    x = x + awgn(rng, n, 0.01)
    return 0.3 * x / np.sqrt(np.mean(np.abs(x) ** 2))


# -- numbered sequences ------------------------------------------------------------------------


def test_numbered_siblings_are_found_in_number_order(tmp_path: Path) -> None:
    for n in (9, 10, 11, 2):
        (tmp_path / f"cap_{n}.cu8").write_bytes(b"")
    (tmp_path / "cap_3.cs8").write_bytes(b"")  # a different suffix is not a sibling
    (tmp_path / "other_4.cu8").write_bytes(b"")
    names = [p.name for p in numbered_sequence(tmp_path / "cap_10.cu8")]
    assert names == ["cap_2.cu8", "cap_9.cu8", "cap_10.cu8", "cap_11.cu8"]
    assert numbered_sequence(tmp_path / "other_4.cu8") == (tmp_path / "other_4.cu8",)


def test_raw_sequence_reads_as_one_recording_and_reports_gaps(tmp_path: Path) -> None:
    x = qpsk()
    parts = np.array_split(x, 4)
    for n, part in zip((1, 2, 3, 5), parts, strict=True):
        (tmp_path / f"rec_{n:03d}.cu8").write_bytes(CU8.encode(part))
    rec = read_sequence(numbered_sequence(tmp_path / "rec_001.cu8"))
    assert rec.datatype.value == "cu8"
    assert any("skips file number(s) 4" in w for w in rec.datatype.warnings)
    with rec.reader() as reader:
        np.testing.assert_allclose(reader.read(0, reader.num_samples), x, atol=2**-7)


def stereo_wav(path: Path, x: np.ndarray, rate: int = 96_000) -> Path:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(CI16.encode(x))
    return path


def test_wav_sequence_reads_as_one_recording(tmp_path: Path) -> None:
    x = qpsk()
    paths = [
        stereo_wav(tmp_path / f"SDRSharp_{i}.wav", part)
        for i, part in enumerate(np.array_split(x, 3))
    ]
    rec = read_sequence(paths)
    assert (rec.datatype.value, rec.sample_rate.value) == ("ci16_le", 96_000.0)
    with rec.reader() as reader:
        np.testing.assert_allclose(reader.read(0, reader.num_samples), x, atol=2**-15)


def test_mismatched_wav_files_or_mixed_kinds_are_refused(tmp_path: Path) -> None:
    a = stereo_wav(tmp_path / "a_1.wav", qpsk(4096))
    b = stereo_wav(tmp_path / "a_2.wav", qpsk(4096), rate=48_000)
    with pytest.raises(ValueError, match="doesn't match"):
        read_sequence([a, b])
    raw = tmp_path / "a_3.wav"
    raw.write_bytes(CU8.encode(qpsk(4096)))
    with pytest.raises(ValueError, match="all WAV files or all raw"):
        read_sequence([a, raw])


def test_raw_files_that_sniff_differently_leave_the_format_unknown(tmp_path: Path) -> None:
    (tmp_path / "r_1.bin").write_bytes(CU8.encode(qpsk()))
    (tmp_path / "r_2.bin").write_bytes(SampleFormat.parse("cf32_le").encode(qpsk()))
    rec = read_sequence(numbered_sequence(tmp_path / "r_1.bin"))
    assert rec.datatype.level is EvidenceLevel.UNKNOWN
    assert {a.value for a in rec.datatype.alternatives} == {"cu8", "cf32_le"}


# -- .gz and .zip ------------------------------------------------------------------------------


def test_gzip_is_decompressed_with_its_size_known_first(tmp_path: Path) -> None:
    data = CU8.encode(qpsk())
    packed = tmp_path / "capture.cu8.gz"
    packed.write_bytes(gzip.compress(data))
    size = unpacked_size(packed)
    assert (size.bytes, size.exact) == (len(data), True)
    (out,) = decompress(packed, tmp_path / "work", limit_bytes=10**9)
    assert out.name == "capture.cu8" and out.read_bytes() == data


def test_zip_members_are_decompressed_under_the_target(tmp_path: Path) -> None:
    packed = tmp_path / "set.zip"
    with zipfile.ZipFile(packed, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("set/a.cu8", b"a" * 5000)
        z.writestr("set/sub/b.cu8", b"b" * 3000)
        z.writestr("set/empty/", b"")
    assert unpacked_size(packed).bytes == 8000
    out = decompress(packed, tmp_path / "work", limit_bytes=10**9)
    assert sorted(p.relative_to(tmp_path / "work").as_posix() for p in out) == [
        "set/a.cu8",
        "set/sub/b.cu8",
    ]


@pytest.mark.parametrize("name", ["../escape.bin", "/abs.bin", "C:/drive.bin", "a/../../x.bin"])
def test_zip_names_that_escape_are_refused(tmp_path: Path, name: str) -> None:
    packed = tmp_path / "evil.zip"
    with zipfile.ZipFile(packed, "w") as z:
        z.writestr("ok.bin", b"fine")
        z.writestr(name, b"payload")
    with pytest.raises(ArchiveError, match=r"unsafe|outside"):
        decompress(packed, tmp_path / "work", limit_bytes=10**9)
    assert not any((tmp_path / "work").rglob("*.bin"))  # nothing partial is left
    assert not (tmp_path / "escape.bin").exists()


def test_zip_symlinks_are_refused(tmp_path: Path) -> None:
    packed = tmp_path / "link.zip"
    info = zipfile.ZipInfo("link.bin")
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(packed, "w") as z:
        z.writestr(info, "/etc/passwd")
    with pytest.raises(ArchiveError, match="symbolic link"):
        decompress(packed, tmp_path / "work", limit_bytes=10**9)


def test_decompression_bombs_are_stopped_by_ratio_and_by_limit(tmp_path: Path) -> None:
    packed = tmp_path / "zeros.bin.gz"
    packed.write_bytes(gzip.compress(bytes(20 << 20)))  # 20 MiB of zeros: ratio ~1000
    with pytest.raises(ArchiveError, match="decompression bomb"):
        decompress(packed, tmp_path / "w1", limit_bytes=10**12, max_ratio=100)
    with pytest.raises(ArchiveError, match="limit"):
        decompress(packed, tmp_path / "w2", limit_bytes=1 << 20, max_ratio=10**6)
    assert not any((tmp_path / "w1").iterdir()) and not any((tmp_path / "w2").iterdir())


def test_damaged_or_unknown_archives_are_refused(tmp_path: Path) -> None:
    damaged = tmp_path / "x.gz"
    noise = np.random.default_rng(0).integers(0, 256, 100_000, dtype=np.uint8).tobytes()
    damaged.write_bytes(gzip.compress(noise)[:5000])
    with pytest.raises(ArchiveError, match="damaged"):
        decompress(damaged, tmp_path / "w", limit_bytes=10**9)
    plain = tmp_path / "x.bin"
    plain.write_bytes(b"not compressed")
    with pytest.raises(ArchiveError, match="neither gzip nor zip"):
        unpacked_size(plain)


# -- compressed audio --------------------------------------------------------------------------


def test_flac_mono_is_measured_and_exact(tmp_path: Path) -> None:
    x = np.round(np.real(qpsk()) * 2**15) / 2**15
    path = tmp_path / "x.flac"
    sf.write(path, x, 48_000, subtype="PCM_16")
    rec = read_audio(path)
    assert (rec.datatype.value, rec.datatype.level) == ("ri16_le", EvidenceLevel.MEASURED)
    assert (rec.sample_rate.value, rec.lossy) == (48_000.0, False)
    with rec.reader() as reader:
        np.testing.assert_allclose(reader.read(0, reader.num_samples), x, atol=2**-15)


def test_flac_stereo_iq_passes_the_quadrature_check(tmp_path: Path) -> None:
    x = qpsk()
    path = tmp_path / "iq.flac"
    sf.write(path, np.stack([np.real(x), np.imag(x)], 1), 192_000, subtype="PCM_24")
    rec = read_audio(path)
    assert rec.quadrature is not None and rec.quadrature.verdict == "iq"
    assert rec.datatype.value == "ci24_le"
    with rec.reader() as reader:
        np.testing.assert_allclose(reader.read(100, 500), x[100:600], atol=2**-22)


def test_lossy_audio_is_warned_and_flagged(tmp_path: Path) -> None:
    x = 0.5 * np.sin(2 * np.pi * 1000 / 48_000 * np.arange(48_000))
    path = tmp_path / "x.ogg"
    sf.write(path, x, 48_000, format="OGG", subtype="VORBIS")
    rec = read_audio(path)
    assert rec.lossy and rec.datatype.value == "rf32_le"
    assert "capped at HYPOTHESIS" in rec.datatype.warnings[0]
    with rec.reader() as reader:
        y = reader.read(0, reader.num_samples)
    assert abs(np.corrcoef(x[1000:40_000], y[1000:40_000])[0, 1]) > 0.99


def test_wav_is_not_compressed_audio(tmp_path: Path) -> None:
    path = stereo_wav(tmp_path / "x.wav", qpsk(4096))
    with pytest.raises(ValueError, match="not compressed audio"):
        read_audio(path)
