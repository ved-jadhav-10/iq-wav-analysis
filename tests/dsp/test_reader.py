from pathlib import Path

import numpy as np
import pytest

from dsp.ingest.formats import SampleFormat
from dsp.ingest.reader import SampleReader

CI16 = SampleFormat.parse("ci16_le")


@pytest.fixture
def recording(tmp_path: Path) -> tuple[Path, np.ndarray]:
    rng = np.random.default_rng(1)
    samples = (rng.uniform(-0.5, 0.5, 1000) + 1j * rng.uniform(-0.5, 0.5, 1000)).astype(
        np.complex64
    )
    path = tmp_path / "x.iq"
    path.write_bytes(CI16.encode(samples))
    return path, samples


def test_chunks_cover_the_file_exactly_once(recording: tuple[Path, np.ndarray]) -> None:
    path, samples = recording
    with SampleReader(path, CI16) as reader:
        chunks = list(reader.chunks(size=300))
    assert [len(c) for c in chunks] == [300, 300, 300, 100]
    np.testing.assert_allclose(np.concatenate(chunks), samples, atol=2**-15)


def test_random_access_and_reads_past_the_end(recording: tuple[Path, np.ndarray]) -> None:
    path, samples = recording
    with SampleReader(path, CI16) as reader:
        np.testing.assert_allclose(reader.read(500, 10), samples[500:510], atol=2**-15)
        assert len(reader.read(995, 100)) == 5
        assert len(reader.read(2000, 10)) == 0


def test_header_offset_and_trailing_bytes(tmp_path: Path) -> None:
    path = tmp_path / "x.iq"
    path.write_bytes(b"HDR!" + CI16.encode(np.array([0.5 + 0.5j, -0.5j])) + b"\x01\x02")
    with SampleReader(path, CI16, offset_bytes=4) as reader:
        assert (reader.num_samples, reader.trailing_bytes) == (2, 2)
        np.testing.assert_allclose(reader.read(0, 2), [0.5 + 0.5j, -0.5j], atol=2**-15)


def test_empty_file_yields_nothing(tmp_path: Path) -> None:
    path = tmp_path / "empty.iq"
    path.write_bytes(b"")
    with SampleReader(path, CI16) as reader:
        assert list(reader.chunks()) == []


def test_offset_outside_file_is_rejected(recording: tuple[Path, np.ndarray]) -> None:
    with pytest.raises(ValueError, match="outside the file"):
        SampleReader(recording[0], CI16, offset_bytes=10**9)


def test_length_bounds_the_samples_read(tmp_path: Path) -> None:
    path = tmp_path / "x.wav"
    path.write_bytes(b"HDR!" + CI16.encode(np.array([0.5 + 0.5j, -0.5j, 0.25])) + b"TAIL")
    with SampleReader(path, CI16, offset_bytes=4, length_bytes=8) as reader:
        assert (reader.num_samples, reader.trailing_bytes) == (2, 0)
        np.testing.assert_allclose(reader.read(0, 10), [0.5 + 0.5j, -0.5j], atol=2**-15)


def test_length_past_the_end_is_rejected(recording: tuple[Path, np.ndarray]) -> None:
    with pytest.raises(ValueError, match="overrun"):
        SampleReader(recording[0], CI16, offset_bytes=4, length_bytes=4000)


def test_24_bit_samples_are_read_in_chunks(tmp_path: Path) -> None:
    fmt = SampleFormat.parse("ci24_le")
    x = np.exp(2j * np.pi * 0.01 * np.arange(1000)) * 0.9
    path = tmp_path / "x.iq"
    path.write_bytes(fmt.encode(x))
    with SampleReader(path, fmt) as reader:
        np.testing.assert_allclose(np.concatenate(list(reader.chunks(333))), x, atol=2**-23)


def test_segments_across_files_read_as_one_stream(tmp_path: Path) -> None:
    from dsp.ingest.reader import Segment, SegmentReader

    x = np.exp(2j * np.pi * 0.01 * np.arange(1200)) * 0.5
    segments = []
    for i in range(12):  # more files than the reader keeps open at once
        path = tmp_path / f"part{i}.iq"
        path.write_bytes(b"H" * i + CI16.encode(x[i * 100 : (i + 1) * 100]) + b"T")
        segments.append(Segment(path, i, 400))
    with SegmentReader(segments, CI16) as reader:
        assert reader.num_samples == 1200
        np.testing.assert_allclose(reader.read(0, 1200), x, atol=2**-15)
        np.testing.assert_allclose(reader.read(95, 210), x[95:305], atol=2**-15)
        np.testing.assert_allclose(reader.read(1150, 99), x[1150:], atol=2**-15)
        np.testing.assert_allclose(np.concatenate(list(reader.chunks(77))), x, atol=2**-15)


def test_a_segment_past_the_end_of_its_file_is_rejected(tmp_path: Path) -> None:
    from dsp.ingest.reader import Segment, SegmentReader

    path = tmp_path / "x.iq"
    path.write_bytes(bytes(100))
    with pytest.raises(ValueError, match="overruns"):
        SegmentReader([Segment(path, 50, 60)], CI16)
