"""The versions of the rule sets an analysis runs with (PLAN §7).

Each catalogue is versioned apart from the program, so a result can say which rules produced it:
bump a number here when an entry is added, removed or changed in the catalogue it names. The
known-system catalogue carries its own version in `systems/catalogue.toml`.
"""

from dsp.results import CatalogueVersion
from dsp.systems.catalogue import load

# Convolutional codes and punctured rates (`dsp.fec`), block, helical, 802.11, QPP and Forney
# interleavers (`dsp.deinterleave`).
FEC_CATALOGUE = "0.1.0"
# Sync words, CRC parameter sets and descramblers (`dsp.framing`, `dsp.scramble`).
FRAMING_CATALOGUE = "0.1.0"


def catalogue_versions() -> tuple[CatalogueVersion, ...]:
    """Every rule set's name and version, in a fixed order."""
    return (
        CatalogueVersion(name="fec-interleaver", version=FEC_CATALOGUE),
        CatalogueVersion(name="framing", version=FRAMING_CATALOGUE),
        CatalogueVersion(name="known-systems", version=load().version),
    )
