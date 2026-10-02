"""Outer Reed-Solomon decoding (PLAN M5): bounded-distance decoding over GF(2^8).

Supports CCSDS 131.0-B's RS(255, 223) in its **conventional (polynomial) basis** representation
only - CCSDS also allows a dual-basis symbol representation (a fixed bit-remapping per byte);
that is NOT implemented here and any dual-basis-encoded stream will fail to decode. Shortened
codes (n < 255, e.g. DVB-S's RS(204, 188)) are supported through the same left-zero-pad
convention `dsp.synth.fec.ReedSolomon.encode` uses, so this decodes a synth-encoded block
exactly; `dsp.synth` itself is not imported (product code stays independent of the generator).

The decoder is the Berlekamp-Massey / Chien / Forney chain, step for step the algorithm `galois`
(`ReedSolomon.decode` and `.detect`) runs, as one Numba kernel cached on disk. It replaces the
`galois` call because that library compiles its field arithmetic anew in every process (tens of
seconds, once per process, before the first outer-code decode of a recording). `galois` still
encodes the synthetic ground truth, and `tests/dsp/test_rs.py` checks this decoder against it
word for word: corrected words and error counts, including words past the correction limit.

CCSDS interleaving (depth I, typically 1-5): I codewords are written one per row and
transmitted column by column - exactly `dsp.deinterleave.Block(I, 255)`. `scan_interleave_depths`
tries I = 1..5 (or a caller-given range) and reports every depth tried, so a caller can log each
as a ledger hypothesis (project rule: every hypothesis tried counts, thresholds are corrected
for that count) - it is not itself a search or acceptance decision; that belongs in `dsp.analyse`.
"""

from dataclasses import dataclass, field
from functools import cache
from typing import Any

import numba  # pyright: ignore[reportMissingTypeStubs]
import numpy as np
from numpy.typing import NDArray

from dsp.deinterleave import Block, deinterleave

N_FULL = 255  # GF(2^8): the unshortened RS codeword length every CCSDS/DVB variant shortens from.

# CCSDS 131.0-B RS(255, 223): field x^8 + x^7 + x^2 + x + 1, roots alpha^(11 j), j = 112..143,
# conventional (not dual-basis) basis - matches `dsp.synth.fec.RS_CCSDS` exactly.
CCSDS_FIELD_POLY = 0x187
CCSDS_FIRST_ROOT = 112
CCSDS_ROOT_POWER = 11


def _mulmod(a: int, b: int, poly: int) -> int:
    """Carry-less product of two GF(2^8) elements, reduced by the field polynomial."""
    out = 0
    while b:
        if b & 1:
            out ^= a
        b >>= 1
        a <<= 1
        if a & 0x100:
            a ^= poly
    return out


@cache
def _field(field_poly: int) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    """The exp (doubled, so a sum of two logs indexes it) and log tables of GF(2^8) over
    `field_poly`, to its smallest primitive element (the one `galois` calls `primitive_element`)."""
    for g in range(2, 256):
        power, order = g, 1
        while power != 1 and order <= N_FULL:
            power, order = _mulmod(power, g, field_poly), order + 1
        if power == 1 and order == N_FULL:
            break
    else:
        raise ValueError(f"{field_poly:#x} has no primitive element in GF(2^8)")
    exp = np.zeros(2 * N_FULL, np.int64)
    log = np.zeros(256, np.int64)
    value = 1
    for i in range(N_FULL):
        exp[i] = exp[i + N_FULL] = value
        log[value] = i
        value = _mulmod(value, g, field_poly)
    return exp, log


@numba.njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def _mul(a: int, b: int, exp: Any, log: Any) -> int:  # pragma: no cover - compiled
    if a == 0 or b == 0:
        return 0
    return exp[log[a] + log[b]]


@numba.njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def _syndromes(
    word: Any, exp: Any, log: Any, first_root: int, root_power: int, out: Any
) -> bool:  # pragma: no cover - compiled
    """S_l = r(alpha^(first_root + l)) for every root, by Horner over the word's symbols (most
    significant first); whether any is nonzero."""
    nonzero = False
    for ell in range(len(out)):
        log_x = (root_power * (first_root + ell)) % N_FULL
        y = 0
        for j in range(len(word)):
            y = word[j] ^ (0 if y == 0 else exp[log[y] + log_x])
        out[ell] = y
        if y != 0:
            nonzero = True
    return nonzero


@numba.njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def _detect(
    words: Any, exp: Any, log: Any, first_root: int, root_power: int, nroots: int
) -> Any:  # pragma: no cover - compiled
    flags = np.zeros(len(words), np.bool_)
    syndrome = np.zeros(nroots, np.int64)
    for i in range(len(words)):
        flags[i] = _syndromes(words[i], exp, log, first_root, root_power, syndrome)
    return flags


@numba.njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def _eval(coeffs: Any, size: int, log_x: int, exp: Any, log: Any) -> int:  # pragma: no cover
    """The polynomial with ascending `coeffs[:size]` at alpha^log_x."""
    y = 0
    for j in range(size - 1, -1, -1):
        y = coeffs[j] ^ (0 if y == 0 else exp[log[y] + log_x])
    return y


@numba.njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def _decode(
    words: Any, exp: Any, log: Any, first_root: int, root_power: int, nroots: int
) -> tuple[Any, Any]:  # pragma: no cover - compiled
    """Berlekamp-Massey, Chien search and Forney values per word, under `galois`'s rules: a
    locator of degree v is taken when 2 v <= nroots and it has v roots among the word's
    positions; anything else is -1 and the word comes back as received."""
    count, n = words.shape
    out = words.copy()
    n_errors = np.zeros(count, np.int64)
    syndrome = np.zeros(nroots, np.int64)
    connection = np.zeros(nroots, np.int64)
    best = np.zeros(nroots, np.int64)
    saved = np.zeros(nroots, np.int64)
    omega = np.zeros(nroots, np.int64)
    derivative = np.zeros(nroots, np.int64)
    positions = np.zeros(nroots + 1, np.int64)
    for w in range(count):
        if not _syndromes(words[w], exp, log, first_root, root_power, syndrome):
            continue
        # Berlekamp-Massey over the whole syndrome sequence.
        connection[:] = 0
        connection[0] = 1
        best[:] = 0
        best[0] = 1
        length = 0
        gap = 1
        last = 1
        for step in range(nroots):
            d = 0
            for i in range(length + 1):
                d ^= _mul(syndrome[step - i], connection[i], exp, log)
            if d == 0:
                gap += 1
                continue
            ratio = _mul(d, exp[N_FULL - log[last]], exp, log)
            if 2 * length > step:
                for i in range(gap, nroots):
                    connection[i] ^= _mul(ratio, best[i - gap], exp, log)
                gap += 1
            else:
                saved[:] = connection
                for i in range(gap, nroots):
                    connection[i] ^= _mul(ratio, best[i - gap], exp, log)
                length = step + 1 - length
                best[:] = saved
                last = d
                gap = 1
        # The locator is the connection polynomial cut to its degree.
        v = min(length, nroots - 1)
        while v > 0 and connection[v] == 0:
            v -= 1
        if 2 * v > nroots:
            n_errors[w] = -1
            continue
        # Chien search: the positions i (ascending degree) where the locator vanishes at alpha^-i.
        found = 0
        for i in range(n):
            if _eval(connection, v + 1, (-root_power * i) % N_FULL, exp, log) == 0:
                positions[found] = i
                found += 1
        if found != v:
            n_errors[w] = -1
            continue
        # Evaluator (locator x syndrome mod x^nroots) and the locator's formal derivative.
        for i in range(nroots):
            acc = 0
            for j in range(min(i, v) + 1):
                acc ^= _mul(connection[j], syndrome[i - j], exp, log)
            omega[i] = acc
        for j in range(v):
            derivative[j] = connection[j + 1] if j % 2 == 0 else 0
        failed = False
        for k in range(found):
            i = positions[k]
            log_x = (-root_power * i) % N_FULL
            numerator = _eval(omega, nroots, log_x, exp, log)
            denominator = _eval(derivative, v, log_x, exp, log)
            if denominator == 0:
                failed = True
                break
            value = 0
            if numerator != 0:
                shift = log[numerator] - log[denominator] + log_x * (first_root - 1)
                value = exp[shift % N_FULL]
            out[w, n - 1 - i] ^= value
        if failed:
            out[w] = words[w]
            n_errors[w] = -1
        else:
            n_errors[w] = v
    return out, n_errors


def _words(codewords: Any) -> NDArray[np.uint8]:
    return np.ascontiguousarray(codewords, np.uint8)


def detect(
    codewords: Any,
    *,
    first_root: int = CCSDS_FIRST_ROOT,
    root_power: int = CCSDS_ROOT_POWER,
    roots: int = 32,
    field_poly: int = CCSDS_FIELD_POLY,
) -> NDArray[np.bool_]:
    """Which rows of `codewords` (words x 255 bytes) are not code words: a nonzero syndrome."""
    exp, log = _field(field_poly)
    flags: NDArray[np.bool_] = np.asarray(
        _detect(_words(codewords), exp, log, first_root, root_power, roots), np.bool_
    )
    return flags


def correct(
    codewords: Any,
    *,
    first_root: int = CCSDS_FIRST_ROOT,
    root_power: int = CCSDS_ROOT_POWER,
    roots: int = 32,
    field_poly: int = CCSDS_FIELD_POLY,
) -> tuple[NDArray[np.uint8], NDArray[np.int64]]:
    """Each row of `codewords` (words x 255 bytes) corrected, and the symbols corrected in each
    (-1: more errors than the code can correct, the row returned as received)."""
    exp, log = _field(field_poly)
    fixed, errors = _decode(_words(codewords), exp, log, first_root, root_power, roots)
    return np.asarray(fixed, np.uint8), np.asarray(errors, np.int64)


def decode_block(
    codeword_bytes: bytes,
    *,
    n: int = 255,
    k: int = 223,
    field_poly: int = CCSDS_FIELD_POLY,
    first_root: int = CCSDS_FIRST_ROOT,
    root_power: int = CCSDS_ROOT_POWER,
) -> tuple[bytes, int] | None:
    """Decode one (n, k) RS codeword (conventional basis). Returns `(message_bytes, n_corrected)`
    on success, or `None` when the codeword has more errors than the code can correct (t = (n -
    k) // 2) - never raises for a bad codeword. `n < 255` (a shortened code, e.g. DVB's (204,
    188)) reconstructs the full `N_FULL`-symbol codeword by re-padding the same `255 - n` leading
    zero bytes `dsp.synth.fec.ReedSolomon.encode` strips before transmission."""
    if len(codeword_bytes) != n:
        raise ValueError(f"codeword is {len(codeword_bytes)} bytes, expected {n}")
    full = np.concatenate([np.zeros(N_FULL - n, np.uint8), np.frombuffer(codeword_bytes, np.uint8)])
    fixed, errors = correct(
        full[None, :],
        first_root=first_root,
        root_power=root_power,
        roots=n - k,
        field_poly=field_poly,
    )
    if errors[0] < 0:
        return None
    return bytes(fixed[0, : N_FULL - (n - k)][-k:]), int(errors[0])


GRID_SCAN_WORDS = 4  # codeword-sized windows scanned for an error-free codeword
GRID_HYPOTHESES = 8 * N_FULL  # bit alignment x byte phase, for the caller's ledger count


@dataclass(frozen=True)
class StreamDecode:
    alignment: int  # bit offset of the first byte
    phase: int  # byte offset of the first whole codeword
    codewords: int
    corrected: int  # bytes corrected over all codewords
    failed: int  # codewords beyond the code's t-byte correction, left uncorrected
    bits: Any  # every codeword's message bytes, as bits


def decode_stream(bits: Any) -> StreamDecode | None:
    """Decode a continuous stream of CCSDS RS(255,223) codewords (depth 1) whose grid is
    unknown: the grid is where some codeword is error-free (zero syndrome, one
    batched call per window) at one of the 8 bit alignments x 255 byte phases; every codeword on
    that grid is then decoded. None if no window holds an error-free codeword. The all-ones word
    is a codeword of this code (no root is alpha^0), so a bit-inverted stream decodes too, to
    inverted messages."""
    window = np.arange(N_FULL)[:, None] + np.arange(N_FULL)[None, :]  # phase x byte
    for alignment in range(8):
        usable = (len(bits) - alignment) // 8 * 8
        data = np.packbits(np.asarray(bits[alignment : alignment + usable], np.uint8))
        for w in range(min(GRID_SCAN_WORDS, len(data) // N_FULL - 1)):
            errors = detect(data[w * N_FULL + window])
            clean = np.flatnonzero(~errors)
            if len(clean) == 0:
                continue
            phase = int(clean[0]) + w * N_FULL
            count = (len(data) - phase) // N_FULL
            words = data[phase : phase + count * N_FULL].reshape(count, N_FULL)
            fixed, n_errors = correct(words)
            messages = fixed[:, :223]
            return StreamDecode(
                alignment,
                phase,
                count,
                int(n_errors[n_errors > 0].sum()),
                int((n_errors < 0).sum()),
                np.unpackbits(np.asarray(messages, np.uint8).ravel()),
            )
    return None


@dataclass(frozen=True)
class DepthAttempt:
    """One interleave depth tried: `ok` is whether every one of its `depth` codewords decoded.
    A caller logs one ledger row per attempt, whether or not it succeeded (project rule: every
    hypothesis tried counts toward the multiple-testing correction)."""

    depth: int
    ok: bool
    messages: tuple[bytes, ...] = field(default=())
    corrected: tuple[int, ...] = field(default=())


def scan_interleave_depths(
    data: bytes,
    depths: range = range(1, 6),
    *,
    n: int = 255,
    k: int = 223,
    field_poly: int = CCSDS_FIELD_POLY,
    first_root: int = CCSDS_FIRST_ROOT,
    root_power: int = CCSDS_ROOT_POWER,
) -> tuple[DepthAttempt, ...]:
    """Try CCSDS-style depth-I interleaving of `data` for each `I` in `depths` (default 1..5,
    the typical CCSDS range): de-interleave the first whole `I * n`-byte block as `I` codewords
    of `n` bytes each (`dsp.deinterleave.Block(I, n)`, the classic "write one codeword per row,
    read column by column" CCSDS interleaver) and try `decode_block` on every one. Returns one
    `DepthAttempt` per depth, in order, whether or not it decoded - short input (`len(data) < I *
    n`) counts as a tried-and-failed attempt at that depth, not a skip."""
    attempts: list[DepthAttempt] = []
    for depth in depths:
        block_bytes = depth * n
        if len(data) < block_bytes:
            attempts.append(DepthAttempt(depth, False))
            continue
        raw = np.frombuffer(data[:block_bytes], np.uint8)
        codewords = deinterleave(raw, Block(depth, n)).reshape(depth, n)
        decoded = [
            decode_block(
                cw.tobytes(),
                n=n,
                k=k,
                field_poly=field_poly,
                first_root=first_root,
                root_power=root_power,
            )
            for cw in codewords
        ]
        if all(d is not None for d in decoded):
            sure = [d for d in decoded if d is not None]
            attempts.append(
                DepthAttempt(
                    depth,
                    True,
                    messages=tuple(d[0] for d in sure),
                    corrected=tuple(d[1] for d in sure),
                )
            )
        else:
            attempts.append(DepthAttempt(depth, False))
    return tuple(attempts)
