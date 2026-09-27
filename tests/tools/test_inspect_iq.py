import gzip
from pathlib import Path

import numpy as np
from inspect_iq import report

from dsp.ingest.formats import SampleFormat
from dsp.synth.waveforms import awgn, frequency_shift, psk_symbols, shape


def qpsk(n: int = 1 << 14) -> np.ndarray:
    rng = np.random.default_rng(5)
    x = frequency_shift(shape(psk_symbols(rng, n // 4 + 1, 4), 4, 0.35)[:n], 0.1)
    return 0.3 * (x + awgn(rng, n, 0.01))


def test_raw_file_reports_the_sniffed_format_and_what_is_unknown(tmp_path: Path) -> None:
    path = tmp_path / "rec.cu8"
    path.write_bytes(SampleFormat.parse("cu8").encode(qpsk()))
    text = report(path)
    assert "Reader: raw (format sniffer)" in text
    assert "| Sample format | cu8 | HYPOTHESIS |" in text
    assert "UNKNOWN: Sample rate, Centre frequency" in text
    assert "Needs review: data_offset" in text
    assert "I/Q power ratio" in text


def test_compressed_files_are_sized_not_unpacked(tmp_path: Path) -> None:
    path = tmp_path / "rec.cu8.gz"
    path.write_bytes(gzip.compress(bytes(5000)))
    assert "unpacks to 5,000 bytes" in report(path)
    assert not (tmp_path / "rec.cu8").exists()
