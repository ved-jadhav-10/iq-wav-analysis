import json
from pathlib import Path
from typing import Any

import pytest

from dsp.evidence import EvidenceLevel
from dsp.ingest.assumptions import RATE_HINT
from dsp.ingest.sigmf import read_sigmf


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
