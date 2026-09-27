"""0 silent defaults (PLAN §5 M1 exit gate): every reader, given a file that doesn't state a
fact, reports that fact as UNKNOWN or HYPOTHESIS with its evidence, never as MEASURED.

Each case writes the barest file its container allows, named with rate and centre-frequency
tags so file-name hints are present too: a hint may become a candidate, never a measurement.
The facts the container does state are checked MEASURED, so no case passes by reading nothing.
"""

import io
import json
import struct
import tarfile
import wave
import zlib
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from dsp.evidence import EvidenceLevel
from dsp.ingest.audio import read_audio
from dsp.ingest.blue import read_blue
from dsp.ingest.formats import SampleFormat
from dsp.ingest.npy import read_npy
from dsp.ingest.raw import read_raw
from dsp.ingest.sdriq import read_sdriq
from dsp.ingest.sequence import numbered_sequence, read_sequence
from dsp.ingest.sigmf import read_sigmf, read_sigmf_archive
from dsp.ingest.vita49 import read_vita49
from dsp.ingest.wav import read_wav
from dsp.results import Assumptions
from dsp.synth.waveforms import awgn, frequency_shift, psk_symbols, shape

FACTS = ("datatype", "data_offset", "sample_rate", "center_frequency")
TAGS = "162.025MHz_2.4MSps"  # file-name hints for both rate and centre frequency
CU8 = SampleFormat.parse("cu8")
CI16_LE = SampleFormat.parse("ci16_le")
CI16_BE = SampleFormat.parse("ci16_be")


def qpsk(n: int = 1 << 14) -> np.ndarray:
    rng = np.random.default_rng(7)
    x = frequency_shift(shape(psk_symbols(rng, n // 4 + 1, 4), 4, 0.35)[:n], 0.1)
    x = x + awgn(rng, n, 0.01)
    return 0.3 * x / np.sqrt(np.mean(np.abs(x) ** 2))


def raw(tmp: Path) -> Assumptions:
    path = tmp / f"rec_{TAGS}.cu8"
    path.write_bytes(CU8.encode(qpsk()))
    return read_raw(path).assumptions


def raw_noise_bytes(tmp: Path) -> Assumptions:
    path = tmp / f"rec_{TAGS}.bin"
    path.write_bytes(np.random.default_rng(1).integers(0, 256, 1 << 15, np.uint8).tobytes())
    return read_raw(path).assumptions


def sigmf_meta(tmp: Path, global_: dict[str, object]) -> Path:
    meta = tmp / f"rec_{TAGS}.sigmf-meta"
    meta.write_text(json.dumps({"global": global_, "captures": [{"core:sample_start": 0}]}))
    meta.with_suffix(".sigmf-data").write_bytes(CI16_LE.encode(qpsk()))
    return meta


def sigmf_bare(tmp: Path) -> Assumptions:
    return read_sigmf(sigmf_meta(tmp, {"core:version": "1.2.0"})).assumptions


def sigmf_no_rate_or_frequency(tmp: Path) -> Assumptions:
    return read_sigmf(sigmf_meta(tmp, {"core:datatype": "ci16_le"})).assumptions


def sigmf_archive(tmp: Path) -> Assumptions:
    path = tmp / f"set_{TAGS}.sigmf"
    meta = json.dumps({"global": {"core:datatype": "ci16_le"}, "captures": []}).encode()
    with tarfile.open(path, "w", format=tarfile.PAX_FORMAT) as tar:
        members = ((f"set/a_{TAGS}.sigmf-meta", meta), (f"set/a_{TAGS}.sigmf-data", bytes(4000)))
        for name, data in members:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    (rec,) = read_sigmf_archive(path)
    return rec.assumptions


def stdlib_wav(path: Path, x: np.ndarray, rate: int = 96_000) -> Path:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(CI16_LE.encode(x))
    return path


def wav_without_auxi(tmp: Path) -> Assumptions:
    return read_wav(stdlib_wav(tmp / f"rec_{TAGS}.wav", qpsk())).assumptions


def wav_zero_rate(tmp: Path) -> Assumptions:
    path = stdlib_wav(tmp / f"rec_{TAGS}.wav", qpsk())
    data = bytearray(path.read_bytes())
    data[24:28] = bytes(4)  # fmt chunk: sample rate
    data[28:32] = bytes(4)  # and byte rate
    path.write_bytes(bytes(data))
    return read_wav(path).assumptions


def npy(tmp: Path) -> Assumptions:
    path = tmp / f"rec_{TAGS}.npy"
    np.save(path, qpsk().astype("<c8"))
    return read_npy(path).assumptions


def sdriq_bad_crc(tmp: Path) -> Assumptions:
    head = struct.pack("<IQQII", 250_000, 145_800_000, 1_700_000_000_123, 16, 0)
    path = tmp / f"rec_{TAGS}.sdriq"
    path.write_bytes(head + struct.pack("<I", zlib.crc32(head) ^ 1) + CI16_LE.encode(qpsk()))
    return read_sdriq(path).assumptions


def blue_without_rate_or_frequency(tmp: Path) -> Assumptions:
    data = CI16_LE.encode(qpsk())
    hcb = bytearray(512)
    hcb[0:12] = b"BLUEEEEIEEEI"
    struct.pack_into("<dd", hcb, 32, 512.0, len(data))
    struct.pack_into("<i", hcb, 48, 1000)
    hcb[52:54] = b"CI"
    struct.pack_into("<ddi", hcb, 256, 0.0, 1.0, 3)  # xunits 3: not a time axis
    path = tmp / f"rec_{TAGS}.blue"
    path.write_bytes(bytes(hcb) + data)
    return read_blue(path).assumptions


def vita49_without_context(tmp: Path) -> Assumptions:
    raw = CI16_BE.encode(qpsk())
    packets = b""
    for count, i in enumerate(range(0, len(raw), 2000)):
        payload = raw[i : i + 2000]
        body = struct.pack(">I", 0x0A01) + bytes(8) + struct.pack(">IQ", 1_700_000_000, 0)
        body += payload + struct.pack(">I", 0)
        word = 1 << 28 | 1 << 27 | 1 << 26 | 1 << 22 | 1 << 20 | (count & 0xF) << 16
        packets += struct.pack(">I", word | (1 + len(body) // 4)) + body
    path = tmp / f"rec_{TAGS}.vrt"
    path.write_bytes(packets)
    return read_vita49(path).assumptions


def flac_mono(tmp: Path) -> Assumptions:
    path = tmp / f"rec_{TAGS}.flac"
    sf.write(path, np.real(qpsk()), 48_000, subtype="PCM_16")
    return read_audio(path).assumptions


def raw_sequence(tmp: Path) -> Assumptions:
    for n, part in enumerate(np.array_split(qpsk(), 3), start=1):
        (tmp / f"rec_{TAGS}_{n:03d}.cu8").write_bytes(CU8.encode(part))
    return read_sequence(numbered_sequence(tmp / f"rec_{TAGS}_001.cu8")).assumptions


def wav_sequence(tmp: Path) -> Assumptions:
    for n, part in enumerate(np.array_split(qpsk(), 3), start=1):
        stdlib_wav(tmp / f"rec_{TAGS}_{n:03d}.wav", part)
    return read_sequence(numbered_sequence(tmp / f"rec_{TAGS}_001.wav")).assumptions


# reader case -> the facts its file doesn't state
CASES: dict[str, tuple[Callable[[Path], Assumptions], set[str]]] = {
    "raw": (raw, set(FACTS)),
    "raw, random bytes": (raw_noise_bytes, set(FACTS)),
    "SigMF, bare global": (sigmf_bare, {"datatype", "sample_rate", "center_frequency"}),
    "SigMF, datatype only": (sigmf_no_rate_or_frequency, {"sample_rate", "center_frequency"}),
    "SigMF archive": (sigmf_archive, {"sample_rate", "center_frequency"}),
    # Two channels are I/Q only as a HYPOTHESIS from the quadrature check.
    "stereo WAV without auxi": (wav_without_auxi, {"datatype", "center_frequency"}),
    "stereo WAV with a zero rate": (wav_zero_rate, {"datatype", "sample_rate", "center_frequency"}),
    "NumPy .npy": (npy, {"sample_rate", "center_frequency"}),
    ".sdriq with a bad CRC": (sdriq_bad_crc, set(FACTS)),
    "MIDAS Blue": (blue_without_rate_or_frequency, {"sample_rate", "center_frequency"}),
    "VITA 49": (vita49_without_context, {"datatype", "sample_rate", "center_frequency"}),
    "FLAC": (flac_mono, {"center_frequency"}),
    "raw sequence": (raw_sequence, set(FACTS)),
    "stereo WAV sequence": (wav_sequence, {"datatype", "center_frequency"}),
}  # fmt: skip


@pytest.mark.parametrize("case", CASES)
def test_unstated_facts_are_never_measured(tmp_path: Path, case: str) -> None:
    build, unstated = CASES[case]
    a = build(tmp_path)
    for fact in FACTS:
        p = getattr(a, fact)
        if fact in unstated:
            assert p.level in (EvidenceLevel.UNKNOWN, EvidenceLevel.HYPOTHESIS), (fact, p.level)
            assert p.evidence, f"{fact} is {p.level} without saying why"
        else:
            assert p.level is EvidenceLevel.MEASURED, (fact, p.level)
    # Samples can't show which component comes first: IQ order is never measured.
    if a.iq_order is not None:
        assert a.iq_order.level in (EvidenceLevel.UNKNOWN, EvidenceLevel.HYPOTHESIS)


@pytest.mark.parametrize("case", CASES)
def test_file_name_hints_are_candidates_not_values(tmp_path: Path, case: str) -> None:
    build, unstated = CASES[case]
    a = build(tmp_path)
    for fact, hinted in (("sample_rate", 2.4e6), ("center_frequency", 162.025e6)):
        p = getattr(a, fact)
        if fact not in unstated:
            continue
        assert p.value != hinted  # never taken from the name
        if p.level is EvidenceLevel.UNKNOWN:
            assert hinted in [alt.value for alt in p.alternatives], fact
