import pytest
from third_party import classify


@pytest.mark.parametrize(
    "licence",
    [
        "MIT",
        "BSD-3-Clause",
        "Apache-2.0",
        "ISC",
        "OFL-1.1",
        "LGPL-3.0-or-later",
        "MIT OR Apache-2.0",
    ],
)
def test_permissive_and_lgpl_are_allowed(licence: str) -> None:
    assert classify(licence) == "allowed"


@pytest.mark.parametrize(
    "licence",
    ["GPL-3.0-only", "AGPL-3.0", "GNU General Public License v2 (GPLv2)", "CC-BY-NC-SA-4.0"],
)
def test_copyleft_and_non_commercial_are_denied(licence: str) -> None:
    assert classify(licence) == "denied"


@pytest.mark.parametrize("licence", ["", "Proprietary", "SEE LICENSE IN LICENSE.txt"])
def test_missing_or_unrecognised_needs_review(licence: str) -> None:
    assert classify(licence) == "unknown"


def test_only_the_gcc_runtime_exception_admits_gpl() -> None:
    assert classify("GPL-3.0-or-later WITH GCC-exception-3.1") == "allowed"
    assert classify("GPL-3.0-or-later WITH Classpath-exception-2.0") == "denied"
    assert classify("GPL-3.0-or-later") == "denied"
