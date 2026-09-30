"""The ground-truth generator, checked against catalogue values and by inverting its own chain."""

import json
import zlib
from pathlib import Path

import galois
import numpy as np
import pytest

from dsp.evidence import EvidenceLevel
from dsp.ingest.sigmf import read_sigmf
from dsp.synth import fec
from dsp.synth import interleave as il
from dsp.synth.bits import (
    CRCS,
    SCRAMBLERS,
    FrameSpec,
    Scrambler,
    frames,
    int_bits,
    to_bits,
    to_bytes,
)
from dsp.synth.chain import Scene, SignalSpec, generate, write_sigmf
from dsp.synth.impair import Impairments
from dsp.synth.modulate import fsk, gray, gray_position, map_bits, pulse_shape, resample

# -- bits: CRCs, frames, scrambler -------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(CRCS))
def test_crc_catalogue_check_values(name: str) -> None:
    crc = CRCS[name]
    assert crc.compute(to_bits(b"123456789")) == crc.check


def test_crc32_matches_zlib_on_random_data() -> None:
    data = np.random.default_rng(1).integers(0, 256, 1000, dtype=np.uint8).tobytes()
    assert CRCS["CRC-32"].compute(to_bits(data)) == zlib.crc32(data)


def test_frames_have_the_sync_word_counter_payload_and_a_passing_crc() -> None:
    spec = FrameSpec(payload_bytes=8)
    payloads = np.arange(24, dtype=np.uint8).reshape(3, 8)
    bits = frames(spec, payloads, first_count=65535).reshape(3, spec.length)
    crc = CRCS["CRC-16/CCITT-FALSE"]
    for i, row in enumerate(bits):
        assert to_bytes(row[:32]).hex() == "1acffc1d"
        assert int("".join(map(str, row[32:48])), 2) == (65535 + i) % 65536
        assert to_bytes(row[48:112]) == payloads[i].tobytes()
        assert crc.compute(row[32:-16]) == int("".join(map(str, row[-16:])), 2)


def test_ccsds_randomiser_sequence_and_period() -> None:
    s = SCRAMBLERS["CCSDS"]
    assert isinstance(s, Scrambler)
    seq = s.sequence(255 * 3)
    assert to_bytes(seq[:64]).hex() == "ff480ec09a0d70bc"
    assert np.array_equal(seq[:255], seq[255:510])
    bits = np.random.default_rng(2).integers(0, 2, 300, dtype=np.uint8)
    assert np.array_equal(s.apply(s.apply(bits)), bits)


# -- FEC ---------------------------------------------------------------------------------------


def test_convolutional_impulse_response_is_the_generators() -> None:
    out = fec.Convolutional(7, fec.K7).encode(np.r_[1, np.zeros(6, np.uint8)])
    assert "".join(map(str, out[0::2])) == "1111001"  # 171 octal
    assert "".join(map(str, out[1::2])) == "1011011"  # 133 octal


def test_convolutional_textbook_sequence_and_termination() -> None:
    code = fec.Convolutional(3, (0o7, 0o5))
    assert "".join(map(str, code.encode(np.array([1, 0, 1, 1])))) == "11100001"
    assert len(code.encode(np.array([1, 0, 1, 1]), terminate=True)) == 12


def test_puncturing_keeps_the_pattern_in_order() -> None:
    u = np.random.default_rng(3).integers(0, 2, 30, dtype=np.uint8)
    full = fec.Convolutional(7, fec.K7).encode(u).reshape(-1, 2)  # rows: (X, Y)
    punctured = fec.Convolutional(7, fec.K7, fec.PUNCTURES["3/4"]).encode(u)
    expected = []
    for t, (x, y) in enumerate(full):
        expected += [x] if t % 3 == 2 else ([x, y] if t % 3 == 0 else [y])  # X1 Y1 Y2 X3
    assert np.array_equal(punctured, expected)
    assert fec.Convolutional(7, fec.K7, fec.PUNCTURES["7/8"]).rate == (7, 8)


def _gf_tables(poly: int) -> tuple[list[int], list[int]]:
    exp, log, x = [0] * 510, [0] * 256, 1
    for i in range(255):
        exp[i] = exp[i + 255] = x
        log[x] = i
        x <<= 1
        if x & 0x100:
            x ^= poly
    return exp, log


def _evaluate(codeword: bytes, point_log: int, exp: list[int], log: list[int]) -> int:
    """Horner evaluation of the codeword polynomial (first byte = highest power) at alpha^k."""
    acc = 0
    for symbol in codeword:
        acc = (exp[(log[acc] + point_log) % 255] if acc else 0) ^ symbol
    return acc


@pytest.mark.parametrize(
    ("code", "roots"),
    [(fec.RS_CCSDS, [11 * j for j in range(112, 144)]), (fec.RS_DVB, list(range(16)))],
)
def test_reed_solomon_codewords_vanish_at_the_generator_roots(
    code: fec.ReedSolomon, roots: list[int]
) -> None:
    message = np.random.default_rng(4).integers(0, 256, code.k * 2, dtype=np.uint8).tobytes()
    words = code.encode(message)
    exp, log = _gf_tables(code.field_poly)
    for w in range(2):
        word = words[w * code.n : (w + 1) * code.n]
        assert word[: code.k] == message[w * code.k : (w + 1) * code.k]  # systematic
        assert all(_evaluate(word, r % 255, exp, log) == 0 for r in roots)


def test_ldpc_codewords_satisfy_every_parity_check() -> None:
    code = fec.regular_ldpc(96, 3, 6, seed=5)
    u = np.random.default_rng(5).integers(0, 2, code.k * 3, dtype=np.uint8)
    words = code.encode(u).reshape(3, code.n)
    assert not (code.h.astype(np.int64) @ words.T % 2).any()
    assert code.k == code.n - np.linalg.matrix_rank(galois.GF2(code.h))


# -- interleavers ------------------------------------------------------------------------------


def test_block_and_helical_permutations() -> None:
    assert il.Block(2, 3).permutation().tolist() == [0, 3, 1, 4, 2, 5]
    assert il.Helical(3, 3).permutation().tolist() == [0, 3, 6, 4, 7, 1, 8, 2, 5]


@pytest.mark.parametrize(
    "spec",
    [il.Block(8, 12), il.Helical(8, 12), il.QPP[40], il.QPP[6144], il.Wifi(48, 1),
     il.Wifi(192, 4), il.RandomPermutation(96, 1)],
)  # fmt: skip
def test_every_block_interleaver_is_a_permutation_that_inverts(spec: il.BlockInterleaver) -> None:
    perm = spec.permutation()
    assert sorted(perm.tolist()) == list(range(spec.size))
    x = np.arange(spec.size * 3)
    assert np.array_equal(il.deinterleave(il.interleave(x, spec), spec), x)


def test_standard_permutation_values() -> None:
    assert il.QPP[40].permutation()[:4].tolist() == [0, 13, 6, 19]  # (3 i + 10 i^2) mod 40
    perm = il.Wifi(48, 1).permutation()
    assert perm[3] == 1 and perm[0] == 0  # input bit 1 goes to output 3


def test_convolutional_interleaver_inverts_with_its_lag() -> None:
    spec = il.Convolutional(4, 3)
    x = np.arange(1, 401)
    y = spec.deinterleave(spec.interleave(x))
    lag = (4 - 1) * 4 * 3
    assert np.array_equal(y[lag:], x[: len(x) - lag])


# -- modulation --------------------------------------------------------------------------------


@pytest.mark.parametrize("modulation", ["bpsk", "qpsk", "8psk", "16qam", "64qam"])
def test_constellations_have_unit_energy_and_gray_neighbours(modulation: str) -> None:
    width = {"bpsk": 1, "qpsk": 2, "8psk": 3, "16qam": 4, "64qam": 6}[modulation]
    labels = np.arange(1 << width)
    bits = ((labels[:, None] >> np.arange(width - 1, -1, -1)) & 1).astype(np.uint8)
    points = map_bits(bits.ravel(), modulation)
    assert np.mean(np.abs(points) ** 2) == pytest.approx(1.0)
    distances = np.abs(points[:, None] - points[None, :])
    nearest = np.min(distances + np.eye(len(points)) * 9, axis=1)
    for a in range(len(points)):
        for b in range(len(points)):
            if a != b and distances[a, b] < nearest[a] * 1.01:
                assert bin(a ^ b).count("1") == 1


def test_qpsk_point_convention() -> None:
    assert map_bits(np.array([0, 0, 1, 0]), "qpsk") == pytest.approx(
        np.array([1 + 1j, -1 + 1j]) / np.sqrt(2)
    )


def test_fsk_tones_follow_the_gray_mapped_bits() -> None:
    bits = np.array([0, 0, 0, 1, 1, 1, 1, 0], dtype=np.uint8)
    x = fsk(bits, 4, 16, 0.02)
    freq = np.diff(np.unwrap(np.angle(x))) / (2 * np.pi)
    # Labels 00, 01, 11, 10 walk the tones in order: neighbouring tones differ in one bit.
    for k, level in enumerate([0, 1, 2, 3]):
        assert freq[k * 16 + 8] == pytest.approx((2 * level - 3) * 0.02)


def test_pulse_shaping_and_resampling() -> None:
    symbols = map_bits(np.random.default_rng(6).integers(0, 2, 400, dtype=np.uint8), "qpsk")
    rect = pulse_shape(symbols, 4, "rect", 0.0)
    assert np.allclose(rect[::4], symbols)
    x = np.exp(2j * np.pi * 0.03 * np.arange(3000))
    t = np.arange(200, 2800, 1.37)
    assert np.max(np.abs(resample(x, t) - np.exp(2j * np.pi * 0.03 * t))) < 1e-4


# -- the chain ---------------------------------------------------------------------------------


def test_generation_is_deterministic_and_seeded() -> None:
    scene = Scene(20_000, (SignalSpec("8psk", sps=3.7),))
    a, b, c = generate(scene, 1), generate(scene, 1), generate(scene, 2)
    assert np.array_equal(a.samples, b.samples)
    assert not np.array_equal(a.samples, c.samples)


def test_the_chain_inverts_back_to_the_payloads() -> None:
    """Symbol decisions -> bit deinterleaver -> RS systematic part -> descramble -> frames."""
    frame = FrameSpec(payload_bytes=32)
    spec = SignalSpec(
        "bpsk", sps=4, pulse="rect", frame=frame, scrambler="CCSDS", outer=fec.RS_CCSDS,
        interleaver=il.Block(8, 255),
    )  # fmt: skip
    g = generate(Scene(60_000, (spec,), noise_db=-200), seed=3)
    decisions = (g.samples[2::4].real < 0).astype(np.uint8)
    assert np.array_equal(decisions, g.signals[0].coded[: len(decisions)])
    usable = len(decisions) // (8 * 255) * (8 * 255)
    stream = il.deinterleave(decisions[:usable], spec.interleaver)  # type: ignore[arg-type]
    words = to_bytes(stream)
    message = b"".join(words[i : i + 223] for i in range(0, len(words) - 254, 255))
    framed = to_bits(message)
    rows = framed[: len(framed) // frame.length * frame.length].reshape(-1, frame.length)
    crc = CRCS["CRC-16/CCITT-FALSE"]
    for i, row in enumerate(rows):
        body = SCRAMBLERS["CCSDS"].apply(row[32:])
        assert to_bytes(row[:32]).hex() == "1acffc1d"
        assert crc.compute(body[:-16]) == int("".join(map(str, body[-16:])), 2)
        assert to_bytes(body[16 : 16 + 256]) == g.signals[0].payloads[i].tobytes()


def test_the_recording_starts_mid_stream() -> None:
    spec = SignalSpec("qpsk", sps=4, stream_offset=101, frame=FrameSpec(payload_bytes=8))
    g = generate(Scene(4000, (spec,)), seed=4)
    framed = g.signals[0].framed
    assert np.array_equal(g.signals[0].coded[:500], framed[101:601])


def test_levels_follow_the_scene() -> None:
    scene = Scene(
        200_000,
        (SignalSpec("16qam", sps=4, power_db=-3), SignalSpec("noise", power_db=-10)),
        noise_db=-20,
    )
    g = generate(scene, 5)
    power = 10 * np.log10(np.mean(np.abs(g.samples) ** 2))
    expected = 10 * np.log10(10**-0.3 + 10**-1 + 10**-2)
    assert power == pytest.approx(expected, abs=0.1)
    first = g.truth["signals"][0]
    assert (first["snrDb"], first["esn0Db"]) == (17.0, pytest.approx(17 + 10 * np.log10(4)))


@pytest.mark.parametrize("modulation", ["am", "fm", "2fsk", "8fsk", "64qam"])
def test_every_kind_of_signal_generates(modulation: str) -> None:
    spec = SignalSpec(modulation, sps=7.5, frame=None, impairments=Impairments(
        cfo=1e-3, phase_noise=1e-3, iq_gain_db=0.5, iq_phase_deg=2, clock_ppm=50,
        multipath=((0, 1, 0), (2.5, 0.3, 1)), fading_doppler=1e-4, agc_db=3, agc_period=5000,
        clip=3.0,
    ))  # fmt: skip
    g = generate(Scene(30_000, (spec,)), 6)
    assert g.samples.shape == (30_000,) and np.all(np.isfinite(g.samples))
    assert g.truth["signals"][0]["modulation"] == modulation


def test_sigmf_output_carries_the_truth_and_reads_back(tmp_path: Path) -> None:
    scene = Scene(
        50_000,
        (SignalSpec("qpsk", sps=8, offset=0.1), SignalSpec("2fsk", sps=16, start=10_000,
                                                           duration=20_000, offset=-0.2)),
        sample_rate=1e6,
        center_frequency=144.8e6,
    )  # fmt: skip
    g = generate(scene, 7)
    meta_path = write_sigmf(tmp_path / "scene", g, scene, "cf32_le")
    rec = read_sigmf(meta_path)
    assert (rec.sample_rate.value, rec.sample_rate.level) == (1e6, EvidenceLevel.MEASURED)
    assert rec.center_frequency.value == 144.8e6
    with rec.reader() as reader:
        np.testing.assert_allclose(reader.read(0, reader.num_samples), g.samples, atol=1e-6)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    first, second = meta["annotations"]
    assert first["sanket:truth"]["symbolRate"] == 125_000
    assert (second["core:sample_start"], second["core:sample_count"]) == (10_000, 20_000)
    assert first["core:freq_lower_edge"] < 144.9e6 < first["core:freq_upper_edge"]
    assert meta["global"]["sanket:truth"]["seed"] == 7


def test_integer_output_is_scaled_to_the_requested_level(tmp_path: Path) -> None:
    scene = Scene(20_000, (SignalSpec("qpsk"),))
    g = generate(scene, 8)
    rec = read_sigmf(write_sigmf(tmp_path / "x", g, scene, "ci16_le", level_dbfs=-20))
    with rec.reader() as reader:
        x = reader.read(0, reader.num_samples)
    rms_db = 10 * np.log10(np.mean(np.abs(x) ** 2) / 2)
    assert rms_db == pytest.approx(-20, abs=0.1)
    assert int_bits(5, 4).tolist() == [0, 1, 0, 1]


def test_gray_position_inverts_gray() -> None:
    p = np.arange(1024)
    assert np.array_equal(gray_position(gray(p)), p)
