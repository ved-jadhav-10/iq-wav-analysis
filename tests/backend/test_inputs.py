"""What a path can name: a file, a folder of recordings, a numbered sequence (PLAN §5 M7)."""

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from backend.inputs import Input, RecordingError, expand, open_input


def touch(folder: Path, *names: str) -> None:
    for name in names:
        (folder / name).write_bytes(b"")


def names(inputs: tuple[Input, ...]) -> list[list[str]]:
    return [[p.name for p in item.paths] for item in inputs]


def test_a_folder_is_a_batch_of_its_recordings_in_name_order(tmp_path: Path) -> None:
    touch(tmp_path, "b.cu8", "a.cu8", ".hidden.cu8", "notes.txt", "run.json", "c.wav")
    touch(tmp_path, "d.sigmf-meta", "d.sigmf-data", "lone.sigmf-data")
    (tmp_path / "sub").mkdir()
    touch(tmp_path / "sub", "deep.cu8")
    # The data file of a SigMF pair is not a second recording; one with no metadata still is.
    assert names(expand(tmp_path)) == [
        ["a.cu8"],
        ["b.cu8"],
        ["c.wav"],
        ["d.sigmf-meta"],
        ["lone.sigmf-data"],
    ]


def test_a_file_is_itself_and_a_missing_or_empty_path_is_refused(tmp_path: Path) -> None:
    touch(tmp_path, "one.cu8")
    assert names(expand(tmp_path / "one.cu8")) == [["one.cu8"]]
    with pytest.raises(RecordingError, match="not a file or a folder"):
        expand(tmp_path / "missing.cu8")
    empty = tmp_path / "empty"
    empty.mkdir()
    touch(empty, "readme.md")
    with pytest.raises(RecordingError, match="holds no recordings"):
        expand(empty)


def test_numbered_files_are_separate_recordings_unless_a_sequence_is_asked_for(
    tmp_path: Path,
) -> None:
    touch(tmp_path, "cap_1.cu8", "cap_2.cu8")
    assert names(expand(tmp_path)) == [["cap_1.cu8"], ["cap_2.cu8"]]
    assert names(expand(tmp_path, sequence=True)) == [["cap_1.cu8", "cap_2.cu8"]]


def test_a_folder_sequence_joins_each_numbered_run_and_leaves_lone_files_alone(
    tmp_path: Path,
) -> None:
    touch(tmp_path, "cap_10.cu8", "cap_9.cu8", "other_1.cu8", "other_2.cu8", "solo.cu8")
    touch(tmp_path, "x_1.sigmf-meta", "x_2.sigmf-meta")  # SigMF is never joined
    assert names(expand(tmp_path, sequence=True)) == [
        ["cap_9.cu8", "cap_10.cu8"],  # by number, not by name
        ["other_1.cu8", "other_2.cu8"],
        ["solo.cu8"],
        ["x_1.sigmf-meta"],
        ["x_2.sigmf-meta"],
    ]
    assert Input((tmp_path / "cap_9.cu8", tmp_path / "cap_10.cu8")).name == "cap_9.cu8 (+1 files)"


def test_a_file_asked_to_be_a_sequence_takes_its_numbered_siblings_if_it_has_any(
    tmp_path: Path,
) -> None:
    touch(tmp_path, "alone_1.cu8", "cap_1.cu8", "cap_2.cu8")
    assert names(expand(tmp_path / "alone_1.cu8", sequence=True)) == [["alone_1.cu8"]]
    assert names(expand(tmp_path / "cap_2.cu8", sequence=True)) == [["cap_1.cu8", "cap_2.cu8"]]


def test_a_sequence_opens_as_one_recording_holding_every_sample(
    tmp_path: Path, samples: NDArray[np.complex128], write_wav: Callable[..., Path]
) -> None:
    peak = float(np.max(np.abs(samples)))
    whole = write_wav(tmp_path / "whole.wav", samples, peak=peak)
    for i, part in enumerate(np.array_split(samples, 3)):
        write_wav(tmp_path / f"part_{i}.wav", part, peak=peak)
    (item,) = expand(tmp_path / "part_0.wav", sequence=True)
    joined = open_input(item)
    assert joined.container == "Numbered sequence"
    assert joined.recording.sample_format is not None
    with joined.recording.reader() as a, open_input(Input((whole,))).recording.reader() as b:
        assert a.num_samples == b.num_samples == len(samples)
        np.testing.assert_array_equal(a.read(0, a.num_samples), b.read(0, b.num_samples))


def test_what_cannot_be_read_is_a_recording_error_saying_why(
    tmp_path: Path, samples: NDArray[np.complex128], write_wav: Callable[..., Path]
) -> None:
    packed = tmp_path / "capture.cu8.gz"
    packed.write_bytes(b"\x1f\x8b" + bytes(30))
    with pytest.raises(RecordingError, match="compressed"):
        open_input(Input((packed,)))
    write_wav(tmp_path / "a_1.wav", samples)
    (tmp_path / "a_2.wav").write_bytes(b"this one is not a WAV file")
    with pytest.raises(RecordingError, match="as one recording"):
        open_input(Input((tmp_path / "a_1.wav", tmp_path / "a_2.wav")))
