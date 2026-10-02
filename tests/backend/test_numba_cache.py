import os
from pathlib import Path

import pytest
from numba.core import config  # pyright: ignore[reportMissingTypeStubs]

from backend.numba_cache import FrozenLocator


def kernel() -> None:  # a stand-in: only its line number is read
    return None


def test_the_cache_goes_to_the_given_folder_for_a_file_that_is_not_on_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "CACHE_DIR", str(tmp_path))
    locator = FrozenLocator.from_function(kernel, os.path.join("dsp", "framing.py"))
    assert locator is not None
    assert Path(locator.get_cache_path()).parent == tmp_path
    assert Path(locator.get_cache_path()).is_dir()


def test_the_subfolder_does_not_depend_on_the_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    here = FrozenLocator.get_suitable_cache_subpath(os.path.join("dsp", "framing.py"))
    monkeypatch.chdir(tmp_path)
    assert FrozenLocator.get_suitable_cache_subpath(os.path.join("dsp", "framing.py")) == here
    assert here.startswith("dsp_")
    assert FrozenLocator.get_suitable_cache_subpath(os.path.join("gf2", "matrix.py")) != here


def test_without_a_cache_folder_it_steps_aside(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "CACHE_DIR", "")
    assert FrozenLocator.from_function(kernel, "dsp/framing.py") is None
