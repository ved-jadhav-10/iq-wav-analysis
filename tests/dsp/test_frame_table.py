import csv
import io
import json

import pytest

from dsp.frame_table import DESCRIPTIONS, FORMATS, MEDIA_TYPES, render
from dsp.report import Frame


def frame(index: int, crc: str, payload: str) -> Frame:
    return Frame(
        index=index,
        start_bit=100 * index,
        sync_word="1ACFFC1D",
        length_bits=8 * (len(payload) // 2) + 48,
        crc=crc,  # type: ignore[arg-type]
        header_hex="12 34 56 78",
        payload_hex=payload,
    )


FRAMES = (frame(1, "pass", "0A1B"), frame(2, "fail", "FFFF"), frame(3, "pass", "00"))


def test_every_format_is_described_and_typed() -> None:
    assert set(FORMATS) == set(DESCRIPTIONS) == set(MEDIA_TYPES) == {"json", "csv", "hex", "bits"}


def test_json_carries_every_frame_with_its_crc_outcome() -> None:
    data = json.loads(render(FRAMES, "json"))
    assert [f["crc"] for f in data["frames"]] == ["pass", "fail", "pass"]
    assert data["frames"][0] == {
        "index": 1,
        "startBit": 100,
        "syncWord": "1ACFFC1D",
        "lengthBits": 64,
        "crc": "pass",
        "headerHex": "12 34 56 78",
        "payloadHex": "0A1B",
    }


def test_csv_has_a_header_row_and_one_row_per_frame() -> None:
    rows = list(csv.reader(io.StringIO(render(FRAMES, "csv"))))
    assert rows[0] == [
        "index",
        "start_bit",
        "length_bits",
        "crc",
        "sync_word",
        "header_hex",
        "payload_hex",
    ]
    assert [r[3] for r in rows[1:]] == ["pass", "fail", "pass"]
    assert rows[1][-1] == "0A1B" and rows[1][-2] == "12 34 56 78"


def test_hex_and_bits_carry_only_crc_passing_payloads_one_per_line() -> None:
    assert render(FRAMES, "hex") == "0A1B\n00\n"
    # Leading zeros are kept: a payload is bytes, so 0x0A1B is sixteen bits.
    assert render(FRAMES, "bits") == "0000101000011011\n00000000\n"


@pytest.mark.parametrize("fmt", FORMATS)
def test_an_empty_table_is_an_empty_document(fmt: str) -> None:
    text = render((), fmt)  # type: ignore[arg-type]
    assert text in (
        "",
        '{\n  "frames": []\n}\n',
        "index,start_bit,length_bits,crc,sync_word,header_hex,payload_hex\n",
    )
