"""PLAN §2 Scale: a file >= 4 GiB streams through detection end to end, with peak memory
bounded and independent of file size. Slow (writes a multi-GB file, several minutes to run):
excluded from the default `uv run pytest` (see pyproject.toml's addopts), run explicitly with
`uv run pytest -m slow tests/dsp/test_scale.py`.
"""

import sys
from pathlib import Path

import numpy as np
import psutil
import pytest

from dsp.detect import detect
from dsp.ingest.formats import SampleFormat
from dsp.ingest.reader import SampleReader
from dsp.synth.chain import Scene, SignalSpec, generate

GIB = 1 << 30
TARGET_BYTES = 4 * GIB
# cf64_le (16 bytes/sample) reaches 4 GiB with the fewest samples of any datatype Sanket reads:
# detect()'s cost scales with sample count, not file size, so this keeps the test's own runtime
# down without making the file (or the streaming it must do) any less real.
FORMAT = SampleFormat.parse("cf64_le")
WRITE_CHUNK_SAMPLES = 1 << 23  # ~128 MiB per chunk while writing the file
GROWTH_CEILING_BYTES = 512 * (1 << 20)  # far below the file size, at any file size


def _peak_rss_bytes(process: psutil.Process) -> int:
    """The process's historical peak resident/working-set size, the closest cross-platform
    proxy to PLAN §2's "RSS ceiling": Windows' `peak_wset`, POSIX's `ru_maxrss` (via `resource`,
    stdlib, POSIX-only), or plain current RSS as a last resort (Linux fills its rss field with
    the current value at the time of the call, so calling this frequently while a suspiciously
    memory-hungry stage runs still catches a real spike even without a true high-water mark).
    """
    info = process.memory_info()
    if sys.platform == "win32":
        return int(getattr(info, "peak_wset", info.rss))
    try:
        import resource

        maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return maxrss * 1024 if sys.platform != "darwin" else maxrss  # KiB on Linux, bytes on mac
    except ImportError:
        return int(info.rss)


def _write_scale_file(path: Path, total_samples: int, burst: np.ndarray, burst_start: int) -> None:
    """The file, written in bounded-size chunks (not materialised whole in memory): AWGN with
    `burst` spliced in at `burst_start`, at the same power (-20 dB) the burst was normalised to.
    """
    rng = np.random.default_rng(0)
    noise_scale = 10 ** (-20.0 / 20) / np.sqrt(2)
    written = 0
    with path.open("wb") as f:
        while written < total_samples:
            count = min(WRITE_CHUNK_SAMPLES, total_samples - written)
            chunk = noise_scale * (
                rng.standard_normal(count) + 1j * rng.standard_normal(count)
            ).astype(np.complex128)
            if written <= burst_start < written + count:
                b0 = burst_start - written
                b1 = min(count, b0 + len(burst))
                chunk[b0:b1] = burst[: b1 - b0]
            f.write(FORMAT.encode(chunk))
            written += count


@pytest.mark.slow
def test_a_4gib_file_streams_through_detection_with_bounded_memory(tmp_path: Path) -> None:
    total_samples = -(-TARGET_BYTES // FORMAT.sample_bytes)  # ceil division: >= 4 GiB on disk
    burst_start = total_samples // 2
    spec = SignalSpec("qpsk", sps=8.0, frame=None, offset=0.1, power_db=0.0)
    burst_scene = Scene(1 << 18, (spec,), noise_db=-20.0)
    burst = generate(burst_scene, seed=1).samples.astype(np.complex128)

    path = tmp_path / "scale.raw"
    _write_scale_file(path, total_samples, burst, burst_start)
    size = path.stat().st_size
    assert size >= TARGET_BYTES

    process = psutil.Process()
    baseline = _peak_rss_bytes(process)
    with SampleReader(path, FORMAT) as reader:
        assert reader.num_samples == total_samples
        # a single FFT size: this test is about memory, not re-measuring the multi-resolution
        # search's own cost, which the (fast) tests in tests/dsp/test_detect.py already cover
        result = detect(reader, real=False, fft_sizes=(4096,))
    peak = _peak_rss_bytes(process)

    assert peak - baseline < GROWTH_CEILING_BYTES, (
        f"RSS grew by {(peak - baseline) / GIB:.2f} GiB processing a "
        f"{size / GIB:.2f} GiB file: memory is not staying bounded"
    )
    assert any(
        abs(d.centre - spec.offset) < 0.05 and d.start <= burst_start <= d.stop
        for d in result.detections
    ), "the planted burst was not found in the 4 GiB file"
