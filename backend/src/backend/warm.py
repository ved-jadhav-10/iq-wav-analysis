"""Compile the Numba kernels (and galois's Reed-Solomon ones) on tiny inputs, once.

The kernels are `@numba.njit(cache=True)`: the first run on a machine compiles them (several
seconds each) and writes the cache; later runs load it. `warm()` calls each through its public
entry point with the dtypes the analysis really passes, so the first recording a user opens
doesn't pay for compiling mid-analysis. The server starts it on a background thread at start-up
(`start()`), so the first response doesn't wait for it either.
"""

import threading
import time

import numpy as np

from dsp.fec import ldpc, rs, viterbi
from dsp.framing import CRCS
from dsp.gf2 import eliminate, matrix


def warm() -> float:
    """Run every compiled kernel once on a tiny input; the seconds this took."""
    began = time.perf_counter()
    rng = np.random.default_rng(0)

    # GF(2): packed matrices, weights, syndromes, elimination (dsp.gf2).
    bits = rng.integers(0, 2, (8, 70), dtype=np.uint8)
    packed = matrix.pack(bits)
    matrix.row_weights(packed)
    matrix.parity_counts(packed, packed[:2])
    eliminate.rref(packed, 70)

    # Soft-decision Viterbi, K=7 rate 1/2 (dsp.fec.viterbi).
    viterbi.decode(rng.standard_normal(2 * 24))

    # LDPC min-sum decoder and the alignment screen's kernels (dsp.fec.ldpc): a clean stream of
    # a small code runs the soft-syndrome scan, the degenerate-window test and the decoder.
    code = ldpc.by_name("CCSDS TC n=128 k=64")
    words = ldpc.encode(code, rng.integers(0, 2, (3, code.k), dtype=np.uint8)).ravel()
    ldpc.find_alignment(4.0 * (1.0 - 2.0 * words), code, codewords=2)

    # Every catalogued CRC, one frame (dsp.framing); the kernel is shared, the types are not.
    CRCS[0].compute_many(rng.integers(0, 2, (2, 32), dtype=np.uint8))

    # galois's own JIT-compiled field arithmetic, through the CCSDS RS(255, 223) decode path.
    word = bytearray(rs.N_FULL)
    word[3] ^= 0x5A
    rs.decode_block(bytes(word))
    return time.perf_counter() - began


def start() -> threading.Thread:
    """`warm()` on a daemon thread, so a server answers while it runs."""
    thread = threading.Thread(target=warm, name="sanket-warm", daemon=True)
    thread.start()
    return thread
