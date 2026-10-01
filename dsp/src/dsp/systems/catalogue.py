"""The known-system catalogue as data (`catalogue.toml`), loaded and validated once."""

import tomllib
from dataclasses import dataclass
from pathlib import Path

CATALOGUE_PATH = Path(__file__).with_name("catalogue.toml")

# The rate tolerance when matching a measured symbol rate to an entry: the larger of three of
# the estimate's own standard deviations and this fraction of the entry's rate.
RATE_TOLERANCE = 0.02
TONE_TOLERANCE = 0.25


@dataclass(frozen=True)
class SystemEntry:
    id: str
    name: str
    specification: str
    licence: str
    check: str  # which of this package's checks verifies it
    modulations: tuple[str, ...]
    symbol_rates: tuple[float, ...]  # empty: any
    codes: tuple[str, ...]
    sync: str
    frame_check: str
    tone_spacing_hz: float | None = None
    interleavers: tuple[str, ...] = ()  # bit interleavers the entry allows (none by default)
    descramblers: tuple[str, ...] = ()
    outer_codes: tuple[str, ...] = ()
    header_bytes: int | None = None  # the entry's fixed header, for the frame table's split


@dataclass(frozen=True)
class Catalogue:
    version: str
    entries: tuple[SystemEntry, ...]


def load(path: Path = CATALOGUE_PATH) -> Catalogue:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    entries = tuple(
        SystemEntry(
            id=e["id"],
            name=e["name"],
            specification=e["specification"],
            licence=e["licence"],
            check=e["check"],
            modulations=tuple(e["modulations"]),
            symbol_rates=tuple(float(r) for r in e["symbol_rates"]),
            codes=tuple(e["codes"]),
            sync=e["sync"],
            frame_check=e["frame_check"],
            tone_spacing_hz=e.get("tone_spacing_hz"),
            interleavers=tuple(e.get("interleavers", ())),
            descramblers=tuple(e.get("descramblers", ())),
            outer_codes=tuple(e.get("outer_codes", ())),
            header_bytes=e.get("header_bytes"),
        )
        for e in raw["system"]
    )
    if len({e.id for e in entries}) != len(entries):
        raise ValueError("catalogue entry ids must be unique")
    return Catalogue(str(raw["version"]), entries)


CATALOGUE = load()
