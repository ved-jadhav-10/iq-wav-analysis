"""NaN and infinite samples in a float file: the readers hand every stage 0 in their place, and
the capture-quality stage says how many there were (never a silent repair)."""

from pathlib import Path

import numpy as np

from dsp.evidence import EvidenceLevel
from dsp.ingest.raw import RawRecording, read_raw
from dsp.quality import capture_quality


def _file(tmp_path: Path, x: np.ndarray) -> Path:
    path = tmp_path / "x.cf32"
    path.write_bytes(x.astype(np.complex64).tobytes())
    return path


def _read(path: Path) -> RawRecording:
    return read_raw(path)


def test_readers_give_zero_for_non_finite_samples_and_raw_reads_keep_them(tmp_path: Path) -> None:
    x = np.exp(2j * np.pi * 0.05 * np.arange(10_000)).astype(np.complex64)
    x[10] = np.nan
    x[20] = complex(np.inf, 0)
    x[30] = complex(0, -np.inf)
    with _read(_file(tmp_path, x)).reader(datatype="cf32_le") as reader:
        clean = reader.read(0, 10_000)
        raw = reader.read_raw(0, 10_000)
    assert np.isfinite(clean).all()
    assert clean[10] == 0 and clean[20] == 0 and clean[30] == 0
    assert np.array_equal(clean[40:], x[40:])  # everything else untouched
    assert not np.isfinite(raw).all()


def test_capture_quality_counts_exactly_the_non_finite_samples(tmp_path: Path) -> None:
    rng = np.random.default_rng(3)
    x = (rng.standard_normal(50_000) + 1j * rng.standard_normal(50_000)).astype(np.complex64)
    bad = rng.choice(50_000, 123, replace=False)
    x[bad] = np.nan
    with _read(_file(tmp_path, x)).reader(datatype="cf32_le") as reader:
        params = {p.id: p for p in capture_quality(reader)}
    p = params["non_finite_samples"]
    assert p.value == 123 and p.level is EvidenceLevel.MEASURED
    assert p.warnings and "0" in p.warnings[0]


def test_a_clean_file_has_no_non_finite_parameter(tmp_path: Path) -> None:
    rng = np.random.default_rng(4)
    x = (rng.standard_normal(20_000) + 1j * rng.standard_normal(20_000)).astype(np.complex64)
    with _read(_file(tmp_path, x)).reader(datatype="cf32_le") as reader:
        assert "non_finite_samples" not in {p.id for p in capture_quality(reader)}


def test_an_all_nan_file_is_still_surveyable(tmp_path: Path) -> None:
    x = np.full(20_000, np.nan, np.complex64)
    with _read(_file(tmp_path, x)).reader(datatype="cf32_le") as reader:
        params = {p.id: p for p in capture_quality(reader)}
    assert params["non_finite_samples"].value == 20_000
