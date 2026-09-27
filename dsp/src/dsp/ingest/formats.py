"""SigMF `core:datatype` sample formats: parsing, decoding to normalised floats, and encoding."""

import re
from dataclasses import dataclass
from typing import Any, Literal, cast

import numpy as np
from numpy.typing import NDArray

_DATATYPE = re.compile(
    r"^(?P<shape>[rc])(?P<kind>[fiu])(?P<bits>8|16|32|64)(?:_(?P<endian>le|be))?$"
)

Kind = Literal["f", "i", "u"]
Endian = Literal["le", "be"]
_BITS: dict[Kind, tuple[int, ...]] = {"f": (32, 64), "i": (8, 16, 32), "u": (8, 16, 32)}


@dataclass(frozen=True)
class SampleFormat:
    is_complex: bool
    kind: Kind
    bits: int
    endian: Endian | None

    @classmethod
    def parse(cls, datatype: str) -> "SampleFormat":
        match = _DATATYPE.match(datatype)
        if match is None:
            raise ValueError(f"not a SigMF core:datatype: {datatype!r}")
        kind = cast(Kind, match["kind"])
        bits = int(match["bits"])
        endian = cast(Endian | None, match["endian"])
        if bits not in _BITS[kind]:
            raise ValueError(f"not a SigMF core:datatype: {datatype!r}")
        if bits == 8 and endian is not None:
            raise ValueError(f"{datatype!r}: 8-bit datatypes take no byte order")
        if bits > 8 and endian is None:
            raise ValueError(f"{datatype!r} needs a byte order (_le or _be)")
        return cls(match["shape"] == "c", kind, bits, endian)

    @property
    def datatype(self) -> str:
        suffix = f"_{self.endian}" if self.endian else ""
        return f"{'c' if self.is_complex else 'r'}{self.kind}{self.bits}{suffix}"

    @property
    def component_dtype(self) -> np.dtype[Any]:
        order = {"le": "<", "be": ">", None: "|"}[self.endian]
        return np.dtype(f"{order}{self.kind}{self.bits // 8}")

    @property
    def sample_bytes(self) -> int:
        return self.bits // 8 * (2 if self.is_complex else 1)

    @property
    def _full_scale(self) -> float:
        return 1.0 if self.kind == "f" else float(2 ** (self.bits - 1))

    def decode(self, raw: NDArray[Any], *, swap_iq: bool = False) -> NDArray[Any]:
        """Components as stored -> complex64 (complex formats) or float32, integers scaled to ±1."""
        x = raw.astype(np.float64)
        if self.kind == "u":
            x -= self._full_scale
        x /= self._full_scale
        if not self.is_complex:
            return x.astype(np.float32)
        i, q = (x[1::2], x[0::2]) if swap_iq else (x[0::2], x[1::2])
        return (i + 1j * q).astype(np.complex64)

    def encode(self, samples: NDArray[Any]) -> bytes:
        """Inverse of decode: normalised samples -> stored bytes; integers rounded and clipped."""
        if self.is_complex:
            x = np.empty(2 * len(samples), dtype=np.float64)
            x[0::2], x[1::2] = np.real(samples), np.imag(samples)
        else:
            x = np.asarray(samples, dtype=np.float64)
        if self.kind != "f":
            x = np.rint(x * self._full_scale)
            if self.kind == "u":
                x += self._full_scale
            info = np.iinfo(self.component_dtype)
            x = np.clip(x, info.min, info.max)
        return x.astype(self.component_dtype).tobytes()


ALL_DATATYPES: tuple[str, ...] = tuple(
    f"{shape}{kind}{bits}{suffix}"
    for shape in "rc"
    for kind, sizes in _BITS.items()
    for bits in sizes
    for suffix in (("",) if bits == 8 else ("_le", "_be"))
)
