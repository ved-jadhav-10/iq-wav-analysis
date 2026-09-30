"""Outer Reed-Solomon decoding via `galois` (PLAN M5; project rule: use `galois` for
finite fields and RS, don't depend on scikit-commpy/pyldpc).

Supports CCSDS 131.0-B's RS(255, 223) in its **conventional (polynomial) basis** representation
only - CCSDS also allows a dual-basis symbol representation (a fixed bit-remapping per byte);
that is NOT implemented here and any dual-basis-encoded stream will fail to decode. Shortened
codes (n < 255, e.g. DVB-S's RS(204, 188)) are supported through the same left-zero-pad
convention `dsp.synth.fec.ReedSolomon.encode` uses, so this decodes a synth-encoded block
exactly; `dsp.synth` itself is not imported (product code stays independent of the generator).

CCSDS interleaving (depth I, typically 1-5): I codewords are written one per row and
transmitted column by column - exactly `dsp.deinterleave.Block(I, 255)`. `scan_interleave_depths`
tries I = 1..5 (or a caller-given range) and reports every depth tried, so a caller can log each
as a ledger hypothesis (project rule: every hypothesis tried counts, thresholds are corrected
for that count) - it is not itself a search or acceptance decision; that belongs in `dsp.analyse`.
"""

from dataclasses import dataclass, field
from functools import cache
from typing import Any

import galois  # pyright: ignore[reportMissingTypeStubs]
import numpy as np

from dsp.deinterleave import Block, deinterleave

N_FULL = 255  # GF(2^8): the unshortened RS codeword length every CCSDS/DVB variant shortens from.

# CCSDS 131.0-B RS(255, 223): field x^8 + x^7 + x^2 + x + 1, roots alpha^(11 j), j = 112..143,
# conventional (not dual-basis) basis - matches `dsp.synth.fec.RS_CCSDS` exactly.
CCSDS_FIELD_POLY = 0x187
CCSDS_FIRST_ROOT = 112
CCSDS_ROOT_POWER = 11


@cache
def _code(field_poly: int, first_root: int, root_power: int, k_full: int) -> Any:
    """The full-length (`N_FULL`, `k_full`) code a shortened (n, k) code borrows from - same
    construction as `dsp.synth.fec._rs`, so a synth-encoded codeword decodes exactly."""
    gf = galois.GF(2**8, irreducible_poly=field_poly)
    alpha = gf.primitive_element**root_power
    return galois.ReedSolomon(N_FULL, k_full, c=first_root, field=gf, alpha=alpha, systematic=True)


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
    code = _code(field_poly, first_root, root_power, N_FULL - (n - k))
    gf = code.field
    full = np.concatenate([np.zeros(N_FULL - n, np.uint8), np.frombuffer(codeword_bytes, np.uint8)])
    message, n_corrected = code.decode(gf(full), errors=True)
    n_corrected = int(n_corrected)
    if n_corrected < 0:
        return None
    payload = np.asarray(message, np.uint8)[-k:]
    return bytes(payload), n_corrected


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
    unknown: the grid is where some codeword is error-free (zero syndrome, galois `detect`, one
    batched call per window) at one of the 8 bit alignments x 255 byte phases; every codeword on
    that grid is then decoded. None if no window holds an error-free codeword. The all-ones word
    is a codeword of this code (no root is alpha^0), so a bit-inverted stream decodes too, to
    inverted messages."""
    code = _code(CCSDS_FIELD_POLY, CCSDS_FIRST_ROOT, CCSDS_ROOT_POWER, 223)
    window = np.arange(N_FULL)[:, None] + np.arange(N_FULL)[None, :]  # phase x byte
    for alignment in range(8):
        usable = (len(bits) - alignment) // 8 * 8
        data = np.packbits(np.asarray(bits[alignment : alignment + usable], np.uint8))
        for w in range(min(GRID_SCAN_WORDS, len(data) // N_FULL - 1)):
            errors = np.asarray(code.detect(code.field(data[w * N_FULL + window])))
            clean = np.flatnonzero(~errors)
            if len(clean) == 0:
                continue
            phase = int(clean[0]) + w * N_FULL
            count = (len(data) - phase) // N_FULL
            words = code.field(data[phase : phase + count * N_FULL].reshape(count, N_FULL))
            messages, n_errors = code.decode(words, errors=True)
            n_errors = np.asarray(n_errors)
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
