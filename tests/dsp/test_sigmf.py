import io
import json
import tarfile
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from dsp.evidence import EvidenceLevel
from dsp.ingest.assumptions import RATE_HINT
from dsp.ingest.formats import SampleFormat
from dsp.ingest.sigmf import SigmfRecording, read_sigmf, read_sigmf_archive


def write(tmp_path: Path, global_: dict[str, Any], captures: Any = None, data: bytes = b"") -> Path:
    meta = tmp_path / "rec.sigmf-meta"
    body: dict[str, Any] = {"global": global_}
    if captures is not None:
        body["captures"] = captures
    meta.write_text(json.dumps(body), encoding="utf-8")
    (tmp_path / "rec.sigmf-data").write_bytes(data)
    return meta


def test_complete_metadata_is_measured(tmp_path: Path) -> None:
    meta = write(
        tmp_path,
        {"core:datatype": "ci16_le", "core:sample_rate": 250_000},
        [{"core:sample_start": 0, "core:frequency": 518_000}],
        data=bytes(16),
    )
    rec = read_sigmf(meta)
    assert rec.data_path == tmp_path / "rec.sigmf-data"
    assert (rec.datatype.value, rec.datatype.level) == ("ci16_le", EvidenceLevel.MEASURED)
    assert (rec.sample_rate.value, rec.sample_rate.unit) == (250_000.0, "S/s")
    assert (rec.center_frequency.value, rec.center_frequency.unit) == (518_000.0, "Hz")
    assert rec.sample_format is not None and rec.sample_format.sample_bytes == 4


@pytest.mark.parametrize("rate", [None, 0, -1, "250k", float("nan"), True])
def test_missing_or_invalid_sample_rate_is_unknown_never_defaulted(
    tmp_path: Path, rate: object
) -> None:
    global_: dict[str, Any] = {"core:datatype": "cf32_le"}
    if rate is not None:
        global_["core:sample_rate"] = rate
    rec = read_sigmf(write(tmp_path, global_))
    assert rec.sample_rate.level is EvidenceLevel.UNKNOWN
    assert rec.sample_rate.value is None
    assert rec.sample_rate.resolve_hint == RATE_HINT


@pytest.mark.parametrize("datatype", [None, "cf16_le", 7])
def test_missing_or_invalid_datatype_is_unknown(tmp_path: Path, datatype: object) -> None:
    global_: dict[str, Any] = {"core:sample_rate": 1e6}
    if datatype is not None:
        global_["core:datatype"] = datatype
    rec = read_sigmf(write(tmp_path, global_))
    assert rec.datatype.level is EvidenceLevel.UNKNOWN
    assert rec.sample_format is None


def test_size_inconsistent_with_datatype_is_warned(tmp_path: Path) -> None:
    rec = read_sigmf(write(tmp_path, {"core:datatype": "cf32_le"}, data=bytes(8 * 10 + 3)))
    assert rec.datatype.level is EvidenceLevel.MEASURED
    assert "3 byte(s)" in rec.datatype.warnings[0]


def test_missing_centre_frequency_is_unknown(tmp_path: Path) -> None:
    rec = read_sigmf(write(tmp_path, {"core:datatype": "cu8"}, [{"core:sample_start": 0}]))
    assert rec.center_frequency.level is EvidenceLevel.UNKNOWN


def test_data_offset_is_zero_by_the_sigmf_spec_or_read_from_header_bytes(tmp_path: Path) -> None:
    rec = read_sigmf(write(tmp_path, {"core:datatype": "cu8"}, [{"core:sample_start": 0}]))
    assert (rec.data_offset.value, rec.data_offset.level) == (0, EvidenceLevel.MEASURED)
    rec = read_sigmf(
        write(tmp_path, {"core:datatype": "ci16_le"}, [{"core:header_bytes": 6}], bytes(6 + 16))
    )
    assert rec.data_offset.value == 6
    assert rec.datatype.warnings == ()  # the size check excludes the header


@pytest.mark.parametrize("header", [-1, 2.5, "6", True])
def test_invalid_header_bytes_is_unknown(tmp_path: Path, header: object) -> None:
    rec = read_sigmf(write(tmp_path, {"core:datatype": "cu8"}, [{"core:header_bytes": header}]))
    assert rec.data_offset.level is EvidenceLevel.UNKNOWN


def test_the_24_bit_extension_is_not_accepted_as_sigmf(tmp_path: Path) -> None:
    rec = read_sigmf(write(tmp_path, {"core:datatype": "ri24_le"}))
    assert rec.datatype.level is EvidenceLevel.UNKNOWN
    assert "not a SigMF core:datatype" in rec.datatype.evidence[0]


# -- datasets, captures and archives -----------------------------------------------------------

CI8 = SampleFormat.parse("ci8")


def signal(n: int = 1000) -> np.ndarray:
    return 0.5 * np.exp(2j * np.pi * 0.013 * np.arange(n))


def samples_of(rec: SigmfRecording) -> np.ndarray:
    with rec.reader() as reader:
        return reader.read(0, reader.num_samples)


def test_multi_capture_non_conforming_dataset_skips_each_header(tmp_path: Path) -> None:
    x = signal()
    data = b"HDR0" + CI8.encode(x[:500]) + b"HDR1" + CI8.encode(x[500:]) + b"TRAILER"
    (tmp_path / "rec.dat").write_bytes(data)
    meta = {
        "global": {"core:datatype": "ci8", "core:dataset": "rec.dat", "core:trailing_bytes": 7},
        "captures": [
            {"core:sample_start": 0, "core:header_bytes": 4, "core:frequency": 1e6},
            {"core:sample_start": 500, "core:header_bytes": 4, "core:frequency": 1e6},
        ],
    }
    path = tmp_path / "rec.sigmf-meta"
    path.write_text(json.dumps(meta), encoding="utf-8")
    rec = read_sigmf(path)
    assert rec.data_offset.value == 4
    assert rec.datatype.warnings == ()
    np.testing.assert_allclose(samples_of(rec), x, atol=2**-7)


def test_conforming_multi_capture_reads_straight_through(tmp_path: Path) -> None:
    x = signal()
    captures = [{"core:sample_start": 0, "core:frequency": 1e6}, {"core:sample_start": 400}]
    meta = write(tmp_path, {"core:datatype": "ci8"}, captures, CI8.encode(x))
    rec = read_sigmf(meta)
    assert len(rec.segments) == 1
    np.testing.assert_allclose(samples_of(rec), x, atol=2**-7)


def test_a_changing_centre_frequency_is_warned(tmp_path: Path) -> None:
    captures = [
        {"core:sample_start": 0, "core:frequency": 1e6},
        {"core:sample_start": 400, "core:frequency": 2e6},
    ]
    rec = read_sigmf(write(tmp_path, {"core:datatype": "ci8"}, captures, CI8.encode(signal())))
    assert rec.center_frequency.value == 1e6
    assert "2000000.0 Hz" in rec.center_frequency.warnings[0]


@pytest.mark.parametrize("dataset", ["../secret.bin", "/etc/passwd", r"C:\x.bin", "a/b.bin", ""])
def test_core_dataset_must_be_a_plain_file_name(tmp_path: Path, dataset: str) -> None:
    path = tmp_path / "rec.sigmf-meta"
    path.write_text(json.dumps({"global": {"core:datatype": "ci8", "core:dataset": dataset}}))
    with pytest.raises(ValueError, match="plain file name"):
        read_sigmf(path)


def test_interleaved_channels_are_unknown(tmp_path: Path) -> None:
    rec = read_sigmf(write(tmp_path, {"core:datatype": "ci8", "core:num_channels": 2}))
    assert rec.datatype.level is EvidenceLevel.UNKNOWN
    assert rec.datatype.resolve_hint and "one channel" in rec.datatype.resolve_hint
    with pytest.raises(ValueError, match="UNKNOWN"):
        rec.reader()


def test_metadata_only_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="metadata only"):
        read_sigmf(write(tmp_path, {"core:datatype": "ci8", "core:metadata_only": True}))


def test_out_of_order_captures_leave_the_offset_unknown(tmp_path: Path) -> None:
    captures = [{"core:sample_start": 500}, {"core:sample_start": 0}]
    rec = read_sigmf(write(tmp_path, {"core:datatype": "ci8"}, captures, bytes(2000)))
    assert rec.data_offset.level is EvidenceLevel.UNKNOWN
    assert rec.segments == ()


def test_a_capture_outside_the_dataset_leaves_the_offset_unknown(tmp_path: Path) -> None:
    captures = [{"core:sample_start": 0, "core:header_bytes": 5000}]
    rec = read_sigmf(write(tmp_path, {"core:datatype": "ci8"}, captures, bytes(2000)))
    assert rec.data_offset.level is EvidenceLevel.UNKNOWN
    assert "outside the dataset" in rec.data_offset.evidence[0]


def tar_with(path: Path, files: dict[str, bytes]) -> Path:
    with tarfile.open(path, "w", format=tarfile.PAX_FORMAT) as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return path


def test_archive_recordings_are_read_in_place(tmp_path: Path) -> None:
    x, y = signal(), signal(700) * 0.5
    meta_a = {"global": {"core:datatype": "ci8", "core:sample_rate": 48000}, "captures": []}
    meta_b = {"global": {"core:datatype": "cf32_le", "core:sample_rate": 1e6}}
    path = tar_with(
        tmp_path / "set.sigmf",
        {
            "set/a.sigmf-meta": json.dumps(meta_a).encode(),
            "set/a.sigmf-data": CI8.encode(x),
            "set/b.sigmf-meta": json.dumps(meta_b).encode(),
            "set/b.sigmf-data": SampleFormat.parse("cf32_le").encode(y),
            "set/README.txt": b"not sigmf",
        },
    )
    a, b = read_sigmf_archive(path)
    assert (a.name, a.sample_rate.value, b.sample_rate.value) == ("set/a.sigmf-meta", 48000, 1e6)
    assert a.data_path == path and a.segments[0].offset % 512 == 0
    np.testing.assert_allclose(samples_of(a), x, atol=2**-7)
    np.testing.assert_allclose(samples_of(b), y, atol=1e-7)
    assert not (tmp_path / "set").exists()  # nothing was extracted


def test_archive_without_its_dataset_cannot_be_read(tmp_path: Path) -> None:
    meta = {"global": {"core:datatype": "ci8"}}
    path = tar_with(tmp_path / "x.sigmf", {"x.sigmf-meta": json.dumps(meta).encode()})
    (rec,) = read_sigmf_archive(path)
    with pytest.raises(ValueError, match="can't be located"):
        rec.reader()


def test_an_archive_with_no_recording_or_compressed_is_refused(tmp_path: Path) -> None:
    empty = tar_with(tmp_path / "e.sigmf", {"notes.txt": b"hi"})
    with pytest.raises(ValueError, match="no SigMF recording"):
        read_sigmf_archive(empty)
    packed = tmp_path / "p.sigmf"
    with tarfile.open(packed, "w:gz") as tar:
        info = tarfile.TarInfo("x.sigmf-meta")
        info.size = 2
        tar.addfile(info, io.BytesIO(b"{}"))
    with pytest.raises(ValueError, match="uncompressed tar"):
        read_sigmf_archive(packed)
