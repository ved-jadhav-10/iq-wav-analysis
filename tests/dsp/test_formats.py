import numpy as np
import pytest

from dsp.ingest.formats import ALL_DATATYPES, SampleFormat


def test_vocabulary_is_complete() -> None:
    # r|c, times: f32/f64 with both byte orders, i/u 8 without, i/u 16 and 32 with both = 2 * 14
    assert len(ALL_DATATYPES) == 28
    assert {"cf32_le", "ci16_be", "cu8", "ri8", "rf64_be", "cu32_le"} <= set(ALL_DATATYPES)


@pytest.mark.parametrize("datatype", ALL_DATATYPES)
def test_every_datatype_parses_to_itself(datatype: str) -> None:
    assert SampleFormat.parse(datatype).datatype == datatype


@pytest.mark.parametrize(
    "bad", ["", "cf16_le", "ci8_le", "ci16", "cf32", "ci64_le", "cx32_le", "cf32_LE", "cf32_le "]
)
def test_invalid_datatypes_are_rejected(bad: str) -> None:
    with pytest.raises(ValueError):
        SampleFormat.parse(bad)


@pytest.mark.parametrize("datatype", ALL_DATATYPES)
def test_every_datatype_round_trips(datatype: str) -> None:
    fmt = SampleFormat.parse(datatype)
    rng = np.random.default_rng(7)
    samples = rng.uniform(-0.9, 0.9, 1000)
    if fmt.is_complex:
        samples = samples + 1j * rng.uniform(-0.9, 0.9, 1000)
    raw = np.frombuffer(fmt.encode(samples), fmt.component_dtype)
    decoded = fmt.decode(raw)
    lsb = 1e-6 if fmt.kind == "f" else 1 / 2 ** (fmt.bits - 1)
    assert decoded.shape == samples.shape
    np.testing.assert_allclose(decoded, samples, atol=lsb)


def test_byte_order_is_honoured() -> None:
    samples = np.array([0.5 - 0.25j])
    little = SampleFormat.parse("ci16_le").encode(samples)
    big = SampleFormat.parse("ci16_be").encode(samples)
    assert big == np.frombuffer(little, "<i2").astype(">i2").tobytes()
    assert little != big


def test_unsigned_formats_are_offset_binary() -> None:
    assert SampleFormat.parse("cu8").encode(np.array([0j])) == bytes([128, 128])


def test_integers_clip_rather_than_wrap() -> None:
    raw = SampleFormat.parse("ri8").encode(np.array([1.5, -1.5]))
    assert list(np.frombuffer(raw, "i1")) == [127, -128]


def test_iq_swap_exchanges_components() -> None:
    fmt = SampleFormat.parse("cf32_le")
    raw = np.frombuffer(fmt.encode(np.array([0.1 + 0.2j])), fmt.component_dtype)
    np.testing.assert_allclose(fmt.decode(raw, swap_iq=True), [0.2 + 0.1j], atol=1e-7)


@pytest.mark.parametrize("datatype", ["ri24_le", "ri24_be", "ci24_le", "ci24_be"])
def test_24_bit_extension_round_trips_but_is_not_sigmf(datatype: str) -> None:
    fmt = SampleFormat.parse(datatype)
    assert not fmt.is_sigmf and datatype not in ALL_DATATYPES
    assert fmt.sample_bytes == (6 if fmt.is_complex else 3)
    samples = np.array([0.5, -0.5, 1.0, -1.0, 2**-23, 0.0] * 2)
    if fmt.is_complex:
        samples = samples[:6] + 1j * samples[6:]
    data = fmt.encode(samples)
    assert len(data) == len(samples) * fmt.sample_bytes
    decoded = fmt.decode(fmt.components(data))
    expected = np.clip(np.real(samples), -1, 1 - 2**-23) + 1j * np.clip(
        np.imag(samples), -1, 1 - 2**-23
    )
    np.testing.assert_allclose(
        decoded, expected if fmt.is_complex else np.real(expected), atol=2**-24
    )


def test_24_bit_layout_is_three_bytes_per_component() -> None:
    assert SampleFormat.parse("ri24_le").encode(np.array([-(2**-23)])) == b"\xff\xff\xff"
    assert SampleFormat.parse("ri24_be").encode(np.array([0.5])) == b"\x40\x00\x00"
    assert SampleFormat.parse("ri24_le").encode(np.array([0.5])) == b"\x00\x00\x40"


@pytest.mark.parametrize("bad", ["ru24_le", "rf24_le", "ri24"])
def test_24_bit_extension_is_signed_integer_only(bad: str) -> None:
    with pytest.raises(ValueError):
        SampleFormat.parse(bad)


@pytest.mark.parametrize("datatype", ALL_DATATYPES)
def test_every_sigmf_datatype_is_sigmf(datatype: str) -> None:
    assert SampleFormat.parse(datatype).is_sigmf
