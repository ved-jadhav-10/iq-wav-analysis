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
