"""FEC encoders for the ground-truth generator: convolutional (with puncturing), Reed-Solomon,
LDPC from a parity-check matrix, and repetition. Decoders belong to M5; these only encode.

Convolutional generators are octal, written as the standards write them: the most significant
of the K bits taps the current input and the least significant the input K-1 steps back, so a
single 1 followed by zeros produces each generator's bits in order (171 octal: 1111001).
Puncturing keeps the bits where the pattern holds 1, reading the
pattern column by column (one column per input bit, one row per output branch), as in DVB-S
and CCSDS. Reed-Solomon uses `galois`; the field polynomial, first consecutive root and the
generator root's power are parameters, so CCSDS and DVB codes are both expressible. LDPC
encoding derives a generator matrix from any parity-check matrix H through `galois`; the
catalogued standard codes (`dsp.fec.ldpc`) encode systematically through `galois` too, by
solving for the parity columns, a path that shares nothing with the decoder side's `dsp.gf2`.
"""

from dataclasses import dataclass
from functools import cache
from typing import Any

import galois  # pyright: ignore[reportMissingTypeStubs]
import numpy as np
from numpy.typing import NDArray

from dsp.fec.ldpc import LdpcCode
from dsp.synth.bits import Bits, to_bits, to_bytes


@dataclass(frozen=True)
class Convolutional:
    constraint: int  # K
    generators: tuple[int, ...]  # octal values, one per output branch
    puncture: tuple[tuple[int, ...], ...] | None = None  # rows = branches, columns = period

    @property
    def rate(self) -> tuple[int, int]:
        if self.puncture is None:
            return 1, len(self.generators)
        return len(self.puncture[0]), sum(map(sum, self.puncture))

    def encode(self, bits: NDArray[Any], *, terminate: bool = False) -> Bits:
        """Encode from the all-zero state; `terminate` appends K-1 zero tail bits."""
        u = np.asarray(bits, dtype=np.uint8)
        if terminate:
            u = np.concatenate([u, np.zeros(self.constraint - 1, np.uint8)])
        branches: list[NDArray[np.uint8]] = []
        for g in self.generators:
            k = self.constraint
            taps = np.array([(g >> (k - 1 - i)) & 1 for i in range(k)], dtype=np.uint8)
            branches.append((np.convolve(u, taps)[: len(u)] % 2).astype(np.uint8))
        coded = np.stack(branches)  # branch x time
        if self.puncture is None:
            return coded.T.ravel().astype(np.uint8)
        pattern = np.array(self.puncture, dtype=bool)
        period = pattern.shape[1]
        keep = np.tile(pattern, (1, -(-len(u) // period)))[:, : len(u)]
        return coded.T[keep.T].astype(np.uint8)

    def truth(self) -> dict[str, Any]:
        k, n = self.rate
        return {
            "code": "convolutional",
            "constraintLength": self.constraint,
            "generatorsOctal": [f"{g:o}" for g in self.generators],
            "puncture": [list(r) for r in self.puncture] if self.puncture else None,
            "rate": f"{k}/{n}",
        }


# K = 7, rate 1/2 (171, 133 octal): CCSDS, DVB-S, IEEE 802.11. Punctured rates as in DVB-S
# (EN 300 421): rows are X then Y.
K7 = (0o171, 0o133)
PUNCTURES: dict[str, tuple[tuple[int, ...], ...]] = {
    "2/3": ((1, 0), (1, 1)),
    "3/4": ((1, 0, 1), (1, 1, 0)),
    "5/6": ((1, 0, 1, 0, 1), (1, 1, 0, 1, 0)),
    "7/8": ((1, 0, 0, 0, 1, 0, 1), (1, 1, 1, 1, 0, 1, 0)),
}


@dataclass(frozen=True)
class ReedSolomon:
    """RS(n, k) over GF(2^8); shortened codes (n < 255) pad the message with leading zeros."""

    n: int = 255
    k: int = 223
    field_poly: int = 0x11D  # x^8 + x^4 + x^3 + x^2 + 1
    first_root: int = 1  # c: roots are alpha^(power * (c + j)), j = 0 .. n - k - 1
    root_power: int = 1

    def encode(self, data: bytes) -> bytes:
        if len(data) % self.k:
            raise ValueError(f"{len(data)} bytes aren't whole {self.k}-byte RS messages")
        code = _rs(self.field_poly, self.first_root, self.root_power, 255, 255 - (self.n - self.k))
        message = np.frombuffer(data, np.uint8).reshape(-1, self.k)
        if self.n < 255:
            message = np.hstack([np.zeros((len(message), 255 - self.n), np.uint8), message])
        words = np.asarray(code.encode(code.field(message)), dtype=np.uint8)
        return words[:, 255 - self.n :].tobytes()

    def encode_bits(self, bits: NDArray[Any]) -> Bits:
        return to_bits(self.encode(to_bytes(bits)))

    def truth(self) -> dict[str, Any]:
        return {
            "code": "reed-solomon",
            "n": self.n,
            "k": self.k,
            "fieldPolynomial": f"0x{self.field_poly:X}",
            "firstRoot": self.first_root,
            "rootPower": self.root_power,
        }


@cache
def _rs(field_poly: int, first_root: int, root_power: int, n: int, k: int) -> Any:
    field = galois.GF(2**8, irreducible_poly=field_poly)
    alpha = field.primitive_element**root_power
    return galois.ReedSolomon(n, k, c=first_root, field=field, alpha=alpha, systematic=True)


# CCSDS 131.0-B RS(255, 223): field x^8 + x^7 + x^2 + x + 1, roots alpha^(11 j), j = 112..143,
# in conventional (not dual-basis) representation. DVB-S RS(204, 188): shortened RS(255, 239)
# over x^8 + x^4 + x^3 + x^2 + 1 with roots alpha^0 .. alpha^15.
RS_CCSDS = ReedSolomon(255, 223, 0x187, 112, 11)
RS_DVB = ReedSolomon(204, 188, 0x11D, 0, 1)


@dataclass(frozen=True, eq=False)
class Ldpc:
    """Encoding for the code with parity-check matrix H (m x n), via a generator from galois."""

    name: str
    h: NDArray[np.uint8]

    @property
    def generator(self) -> NDArray[np.uint8]:
        return _generator(self.h.tobytes(), self.h.shape)

    @property
    def k(self) -> int:
        return int(self.generator.shape[0])

    @property
    def n(self) -> int:
        return int(self.h.shape[1])

    def encode(self, bits: NDArray[Any]) -> Bits:
        u = np.asarray(bits, dtype=np.uint8)
        if len(u) % self.k:
            raise ValueError(f"{len(u)} bits aren't whole {self.k}-bit LDPC messages")
        return (
            (u.reshape(-1, self.k).astype(np.int64) @ self.generator % 2).astype(np.uint8).ravel()
        )

    def truth(self) -> dict[str, Any]:
        return {"code": "ldpc", "name": self.name, "n": self.n, "k": self.k}


@cache
def _generator(h: bytes, shape: tuple[int, int]) -> NDArray[np.uint8]:
    matrix = galois.GF2(np.frombuffer(h, np.uint8).reshape(shape))
    return np.asarray(matrix.null_space(), dtype=np.uint8)


@dataclass(frozen=True, eq=False)
class StandardLdpc(Ldpc):
    """A catalogued standard code (`dsp.fec.ldpc.CATALOGUE`), encoded systematically.

    The message is the first k bits of the code word and the output is what the standard
    transmits: the last `punctured` columns (CCSDS TM) are dropped, so `n` is the transmitted
    length. `h` is the full parity-check matrix, punctured columns included."""

    code: LdpcCode | None = None

    @property
    def _code(self) -> LdpcCode:
        if self.code is None:
            raise ValueError("StandardLdpc needs its catalogue code; build it with standard_ldpc")
        return self.code

    @property
    def k(self) -> int:
        return self._code.k

    @property
    def n(self) -> int:
        return self._code.transmitted

    @property
    def generator(self) -> NDArray[np.uint8]:
        raise NotImplementedError("a standard code encodes through its parity map, not a G")

    def encode(self, bits: NDArray[Any]) -> Bits:
        code = self._code
        u = np.asarray(bits, dtype=np.uint8)
        if len(u) % code.k:
            raise ValueError(f"{len(u)} bits aren't whole {code.k}-bit LDPC messages")
        messages = u.reshape(-1, code.k)
        t = _parity_map(self.h.tobytes(), self.h.shape, code.k)
        parity = (messages.astype(np.float32) @ t % 2).astype(np.uint8)  # exact: sums <= k
        word = np.hstack([messages, parity])
        return word[:, : code.transmitted].ravel()

    def truth(self) -> dict[str, Any]:
        code = self._code
        return {
            "code": "ldpc",
            "name": self.name,
            "n": self.n,
            "k": self.k,
            "standard": code.family,
            "source": code.source,
            "punctured": code.punctured,
        }


@cache
def _parity_map(h: bytes, shape: tuple[int, int], k: int) -> NDArray[np.float32]:
    """T with parity = message T (mod 2): H = [A | B], B (the last n - k columns) invertible."""
    matrix = galois.GF2(np.frombuffer(h, np.uint8).reshape(shape))
    a, b = matrix[:, :k], matrix[:, k:]
    return np.asarray(np.linalg.inv(b) @ a, dtype=np.float32).T


def standard_ldpc(code: LdpcCode) -> StandardLdpc:
    """The ground-truth encoder for a catalogue code."""
    return StandardLdpc(code.name, code.dense(), code)


def regular_ldpc(n: int, column_weight: int, row_weight: int, seed: int) -> Ldpc:
    """A random (column_weight, row_weight)-regular H (Gallager's construction), for testing."""
    if n % row_weight:
        raise ValueError("n must be a multiple of the row weight")
    rng = np.random.default_rng(seed)
    rows = n // row_weight
    base = np.zeros((rows, n), np.uint8)
    for r in range(rows):
        base[r, r * row_weight : (r + 1) * row_weight] = 1
    h = np.vstack([base] + [base[:, rng.permutation(n)] for _ in range(column_weight - 1)])
    return Ldpc(f"gallager({n},{column_weight},{row_weight}) seed {seed}", h)


@dataclass(frozen=True)
class Repetition:
    times: int

    def encode(self, bits: NDArray[Any]) -> Bits:
        return np.repeat(np.asarray(bits, dtype=np.uint8), self.times)

    def truth(self) -> dict[str, Any]:
        return {"code": "repetition", "times": self.times}
