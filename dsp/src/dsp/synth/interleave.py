"""Interleavers for the ground-truth generator; each permutes a stream of bits or symbols.

- Block (rows x cols): written row by row, read column by column.
- Convolutional (Forney, I branches, delay step M): element t goes to branch t mod I, which
  delays it by (t mod I) * M elements; delay lines start full of zeros.
- Helical (rows x cols), also called diagonal: written row by row, read column by column with
  column c starting c rows down, wrapping around, so consecutive outputs walk a diagonal.
- Standard permutations: LTE turbo QPP, pi(i) = (f1 i + f2 i^2) mod K (3GPP TS 36.212), and the
  IEEE 802.11 BCC interleaver's two permutations (IEEE 802.11 §17.3.5.7).
- A seeded random permutation, for negative tests only: Sanket never claims to recover it.

Block-based interleavers need a whole number of blocks; the chain pads to fit and records it.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class Block:
    rows: int
    cols: int

    @property
    def size(self) -> int:
        return self.rows * self.cols

    def permutation(self) -> NDArray[np.int64]:
        """out[j] = in[permutation[j]]."""
        return np.arange(self.size).reshape(self.rows, self.cols).T.ravel()

    def truth(self) -> dict[str, Any]:
        return {"interleaver": "block", "rows": self.rows, "cols": self.cols}


@dataclass(frozen=True)
class Helical:
    rows: int
    cols: int

    @property
    def size(self) -> int:
        return self.rows * self.cols

    def permutation(self) -> NDArray[np.int64]:
        c = np.repeat(np.arange(self.cols), self.rows)
        r = (np.tile(np.arange(self.rows), self.cols) + c) % self.rows
        return r * self.cols + c

    def truth(self) -> dict[str, Any]:
        return {"interleaver": "helical", "rows": self.rows, "cols": self.cols}


@dataclass(frozen=True)
class Qpp:
    k: int
    f1: int
    f2: int

    @property
    def size(self) -> int:
        return self.k

    def permutation(self) -> NDArray[np.int64]:
        i = np.arange(self.k, dtype=np.int64)
        p = (self.f1 * i + self.f2 * i * i) % self.k
        if len(np.unique(p)) != self.k:
            raise ValueError(f"QPP ({self.f1}, {self.f2}) isn't a permutation of {self.k}")
        return p

    def truth(self) -> dict[str, Any]:
        return {"interleaver": "lte-qpp", "k": self.k, "f1": self.f1, "f2": self.f2}


# Entries of 3GPP TS 36.212 Table 5.1.3-3.
QPP = {40: Qpp(40, 3, 10), 6144: Qpp(6144, 263, 480)}


@dataclass(frozen=True)
class Wifi:
    """IEEE 802.11 BCC interleaver for one OFDM symbol of n_cbps coded bits, n_bpsc per carrier."""

    n_cbps: int
    n_bpsc: int

    @property
    def size(self) -> int:
        return self.n_cbps

    def permutation(self) -> NDArray[np.int64]:
        n, s = self.n_cbps, max(self.n_bpsc // 2, 1)
        k = np.arange(n)
        i = (n // 16) * (k % 16) + k // 16
        j = s * (i // s) + (i + n - (16 * i) // n) % s
        # Input bit k lands at output position j, so out[j] = in[k].
        perm = np.empty(n, dtype=np.int64)
        perm[j] = k
        return perm

    def truth(self) -> dict[str, Any]:
        return {"interleaver": "ieee-802.11", "nCbps": self.n_cbps, "nBpsc": self.n_bpsc}


@dataclass(frozen=True)
class RandomPermutation:
    size: int
    seed: int

    def permutation(self) -> NDArray[np.int64]:
        return np.random.default_rng(self.seed).permutation(self.size)

    def truth(self) -> dict[str, Any]:
        return {"interleaver": "random", "size": self.size, "seed": self.seed}


BlockInterleaver = Block | Helical | Qpp | Wifi | RandomPermutation


def interleave(x: NDArray[Any], spec: BlockInterleaver) -> NDArray[Any]:
    if len(x) % spec.size:
        raise ValueError(f"{len(x)} elements aren't whole {spec.size}-element blocks")
    return x.reshape(-1, spec.size)[:, spec.permutation()].ravel()


def deinterleave(x: NDArray[Any], spec: BlockInterleaver) -> NDArray[Any]:
    if len(x) % spec.size:
        raise ValueError(f"{len(x)} elements aren't whole {spec.size}-element blocks")
    out = np.empty_like(x.reshape(-1, spec.size))
    out[:, spec.permutation()] = x.reshape(-1, spec.size)
    return out.ravel()


@dataclass(frozen=True)
class Convolutional:
    branches: int  # I
    step: int  # M

    def interleave(self, x: NDArray[Any]) -> NDArray[Any]:
        return self._delay(x, lambda b: b * self.step)

    def deinterleave(self, x: NDArray[Any]) -> NDArray[Any]:
        """Undo the interleaver; the output lags the input by (I - 1) * I * M elements."""
        return self._delay(x, lambda b: (self.branches - 1 - b) * self.step)

    def _delay(self, x: NDArray[Any], delay: Callable[[int], int]) -> NDArray[Any]:
        out = np.zeros_like(x)
        for b in range(self.branches):
            lane = x[b :: self.branches]
            d = delay(b)
            shifted = np.concatenate([np.zeros(d, x.dtype), lane])[: len(lane)]
            out[b :: self.branches] = shifted
        return out

    def truth(self) -> dict[str, Any]:
        return {"interleaver": "convolutional", "branches": self.branches, "step": self.step}
