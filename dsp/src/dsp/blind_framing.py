"""Blind frame discovery on a decoded bit stream (PLAN M6, requirement R5).

Nothing is assumed about the framing: not the sync word, not the frame length, not the header
layout, not the CRC. Three steps, each with its own significance test and its own count of the
hypotheses it could have produced.

**Sync word and frame length.** Cut the stream into rows of L bits. If L is the frame length,
the sync word's columns hold the same value in every row, while payload columns are fair coins.
A column is *constant* when its ones-count in `u` rows is too lopsided for Binomial(u, ½) at
`COLUMN_P`; a run of R >= `MIN_RUN` consecutive constant columns (circularly, since the frame
need not start at a row boundary) has probability `COLUMN_P ** R` on a structureless stream at
each starting column, so R is chosen to keep the whole search under `alpha` (Bonferroni over
every period, starting column and stream variant). Discovery reads only the first half of
the rows (a contiguous half: alternate rows alias with half the frame length).

**Held-out recurrence.** The second half of the rows then counts how often the discovered word
recurs at the frame period (within R // 8 bit errors), against the chance a random row
matches. Only that count is a `sync_recurrence` proof: the discovery rows agree with the word
by construction.

**What the word is.** All that column constancy can find is the *constant prefix* of the frame:
the sync word plus any constant header bytes that follow it, minus a trailing run of one value,
which is taken to be the top of the next field (a counter's unused high bits). A sync word that
ends in a few of that value loses them. The word is reported as what it is, a constant prefix.

**Header fields.** Right after the constant prefix: byte-aligned constants and counters, each judged
against its chance rate; the first byte that is neither ends the header.

**CRC.** With equal-length frames the CRC's initial value and final XOR cancel when two frames
are XORed, so the XOR of any two frames is a multiple of the generator polynomial; the GCD of
several such multiples is the generator (Ewing's differential method). The remaining affine
constant is then fitted. The generator is fitted on half the frames, and only its passes on the
other half count; every (width, reflection) tried is counted.

**Limits.** One frame length in a stream (no mixed lengths), a sync word of at least `MIN_RUN`
bits, at least `2 * MIN_ROWS` frames, frames shorter than `MAX_PERIOD` bits, the CRC at the very
end of the frame. NRZ-I (differential) encoding is searched as a second stream variant.
"""

import math
from collections import Counter
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from dsp import _scipy
from dsp.framing import Crc, binomial_tail
from dsp.gf2.poly import degree, pgcd, pmod

Bits = NDArray[np.uint8]

MIN_PERIOD = 24
MAX_PERIOD = 4096
MIN_ROWS = 32  # rows in each half (discovery and held-out)
COLUMN_P = 0.01
MIN_RUN = 8
EDGE_P = 1e-3  # a run's end columns must be at least this lopsided, or they are trimmed
ALPHA = 1e-3
Z_MIN = 5.0  # autocorrelation peak, in standard deviations, worth a column test
MAX_CANDIDATES = 6  # periods column-tested per stream variant
Variant = Literal["plain", "nrzi"]


# --- sync word and frame length -----------------------------------------------------------


@dataclass(frozen=True)
class SyncDiscovery:
    variant: Variant  # NRZ-I streams are searched after differencing: `stream` is that stream
    stream: Bits
    period: int  # frame length in bits, sync word included
    start: int  # index in `stream` where the first frame's sync word begins
    word: Bits  # the sync word as it reads in `stream`
    rows: int  # rows the stream was cut into
    hits: int  # held-out rows where the word recurs at the frame period
    heldout: int
    p_value: float  # of `hits` out of `heldout` on a structureless stream, corrected
    threshold: float
    candidates: int  # (variant, period) pairs that passed the column test
    tried: int  # hypotheses the run length was corrected for

    @property
    def verified(self) -> bool:
        """The held-out recurrence is significant: a `sync_recurrence` proof."""
        return self.p_value <= self.threshold

    def frames(self) -> Bits:
        """Every whole frame, one per row, starting at the sync word."""
        n = (len(self.stream) - self.start) // self.period
        body = self.stream[self.start : self.start + n * self.period]
        return body.reshape(n, self.period)


def _to_int(bits: NDArray[np.integer]) -> int:
    data = np.asarray(bits, np.uint8)
    pad = (-len(data)) % 8
    packed = np.packbits(np.concatenate([np.zeros(pad, np.uint8), data]))
    return int.from_bytes(packed.tobytes(), "big")


def _longest_circular_run(flags: NDArray[np.bool_]) -> tuple[int, int]:
    """(start, length) of the longest run of True in a circular boolean array."""
    n = len(flags)
    if flags.all():
        return 0, n
    if not flags.any():
        return 0, 0
    doubled = np.concatenate([flags, flags])
    edges = np.flatnonzero(np.diff(np.concatenate([[0], doubled.view(np.int8), [0]])))
    starts, ends = edges[0::2], edges[1::2]
    lengths = np.minimum(ends - starts, n)
    best = int(np.argmax(lengths))
    return int(starts[best] % n), int(lengths[best])


def _autocorrelation_peaks(s: Bits) -> list[tuple[float, int]]:
    """(z, lag) of the autocorrelation peaks of the +-1 stream between the period bounds, best
    first. A constant column contributes +1 at the frame length whatever its value, so the frame
    length shows up as a peak of about (constant columns / L) x sqrt(N) standard deviations."""
    n = len(s)
    x = 1.0 - 2.0 * s.astype(np.float64)
    lags = np.arange(MIN_PERIOD, min(MAX_PERIOD, n // (2 * MIN_ROWS)) + 1)
    if len(lags) == 0:
        return []
    r = _scipy.autocorrelation(x)
    z = r[lags] / np.sqrt(n - lags)
    above = np.flatnonzero(z >= Z_MIN)  # noise has almost none: the sort and the scan are for those
    peaks: list[tuple[float, int]] = []
    taken = np.zeros(int(lags[-1]) + 3, bool)  # lags within 2 of a peak already kept
    for i in above[np.argsort(-z[above], kind="stable")]:
        lag = int(lags[i])
        if not taken[lag]:
            peaks.append((float(z[i]), lag))
            taken[max(0, lag - 2) : lag + 3] = True
    return peaks


def structure_z(bits: NDArray[np.integer]) -> float:
    """The strongest autocorrelation peak of the stream (either variant), in standard deviations,
    or 0 if it is too short to search. A cheap screen: structureless bits stay below about 4."""
    b = np.asarray(bits, np.uint8)
    best = 0.0
    for s in (b, b[1:] ^ b[:-1]):
        peaks = _autocorrelation_peaks(s)
        if peaks:
            best = max(best, peaks[0][0])
    return best


def _trailing_run(word: Bits) -> int:
    """Length of the run of identical bits at the end of `word`."""
    n = 1
    while n < len(word) and word[-1 - n] == word[-1]:
        n += 1
    return n


def _match_probability(run: int, errors: int) -> float:
    """Chance a random row equals a `run`-bit word within `errors` bit errors."""
    return sum(math.comb(run, i) for i in range(errors + 1)) / 2.0**run


def discover_sync(bits: NDArray[np.integer], *, alpha: float = ALPHA) -> SyncDiscovery | None:
    """Find a recurring sync word and the frame length in `bits`, or None."""
    b = np.asarray(bits, np.uint8)
    variants: tuple[tuple[Variant, Bits], ...] = (("plain", b), ("nrzi", b[1:] ^ b[:-1]))
    # Only the periods where the stream correlates with itself are column-tested; the held-out
    # recurrence, which is what verifies the word, does not depend on how a period was proposed.
    proposals: list[tuple[Variant, Bits, list[int]]] = [
        (variant, s, [lag for _, lag in _autocorrelation_peaks(s)[:MAX_CANDIDATES]])
        for variant, s in variants
    ]
    tried = sum(period for _, _, periods in proposals for period in periods)
    if tried == 0:
        return None
    need = max(MIN_RUN, math.ceil(math.log(alpha / tried) / math.log(COLUMN_P)))

    found: list[tuple[float, int, Variant, Bits, int, int]] = []
    for variant, s, periods in proposals:
        for period in periods:
            rows = len(s) // period
            matrix = s[: rows * period].reshape(rows, period)
            seen = matrix[: rows // 2]
            ones = seen.sum(axis=0, dtype=np.int64)
            lopsided = np.maximum(ones, len(seen) - ones)
            p = np.minimum(1.0, 2 * _scipy.binom_sf(lopsided, len(seen), 0.5))
            constant = p <= COLUMN_P
            if constant.mean() > 0.6:
                continue  # a nearly constant stream has no frame structure to find
            start, run = _longest_circular_run(constant)
            # Weakly lopsided columns at the run's ends are leakage from the next field.
            while run > 0 and p[start % period] > EDGE_P:
                start, run = start + 1, run - 1
            while run > 0 and p[(start + run - 1) % period] > EDGE_P:
                run -= 1
            if run >= need and run <= period // 2:
                columns = (start + np.arange(run)) % period
                # Total evidence in the run: weaker sub-multiples of the true period (the sync
                # row plus a counter's constant high bits) lose to the frame length itself, where
                # every row counts.
                evidence = float(-np.log(np.maximum(p[columns], 1e-300)).sum())
                found.append((evidence, period, variant, s, start, run))
    if not found:
        return None
    _, period, variant, s, start, run = max(found, key=lambda f: (f[0], -f[1], f[2] == "plain"))

    rows = len(s) // period
    matrix = s[: rows * period].reshape(rows, period)
    columns = (start + np.arange(run)) % period
    seen, held = matrix[: rows // 2][:, columns], matrix[rows // 2 :][:, columns]
    word = (2 * seen.sum(axis=0, dtype=np.int64) > len(seen)).astype(np.uint8)
    # A constant run of one value at the end is the top of the next field (a counter that has
    # not yet grown into its high bits), not sync: keep it out of the word.
    tail = _trailing_run(word)
    if tail >= MIN_RUN and run - tail >= MIN_RUN:
        run -= tail
        word = word[:run]
        columns = columns[:run]
        seen, held = seen[:, :run], held[:, :run]
    errors = run // 8
    hits = int(((held != word).sum(axis=1) <= errors).sum())
    p = binomial_tail(hits, len(held), _match_probability(run, errors)) * len(found)
    return SyncDiscovery(
        variant,
        s,
        period,
        start,
        word,
        rows,
        hits,
        len(held),
        min(1.0, p),
        alpha,
        len(found),
        tried,
    )


# --- header fields -------------------------------------------------------------------------


@dataclass(frozen=True)
class Field:
    kind: Literal["sync", "constant", "counter", "variable"]
    start: int  # bit offset from the start of the frame
    width: int  # bits
    value: int | None = None  # constant fields
    step: int | None = None  # counters: the increment per frame
    p_value: float | None = None


FIELD_P = 1e-6
FIELD_WIDTHS = (32, 16, 8)


def _mode(values: list[int]) -> tuple[int, int]:
    """The most common value and how often it occurs."""
    return Counter(values).most_common(1)[0]


def header_fields(
    frames: Bits, sync_width: int, *, max_bits: int = 128, align: int | None = None
) -> tuple[Field, ...]:
    """The sync word, then byte-aligned constant and counter fields, then the first variable byte
    (where the payload begins). `frames` is one row per frame.

    Fields are bytes counted from `sync_width + align`. The constant prefix can stop a few bits
    short of the data (a sync word ending in a run its neighbour also has), so when `align` is
    not given all eight are tried and the one that reads most header bits as fields wins; a
    frame check that fixes the data's alignment (bytes back from the CRC) supplies it."""
    if align is None:
        tries = [header_fields(frames, sync_width, max_bits=max_bits, align=a) for a in range(8)]
        return max(
            tries, key=lambda fs: sum(f.width for f in fs if f.kind in ("constant", "counter"))
        )
    n, length = frames.shape
    fields = [Field("sync", 0, sync_width)]
    pos = sync_width + align
    end = min(length, sync_width + max_bits)
    while pos + 8 <= end:
        found: Field | None = None
        for width in FIELD_WIDTHS:
            if pos + width > end:
                continue
            values = [_to_int(row[pos : pos + width]) for row in frames]
            value, k = _mode(values)
            p_const = binomial_tail(k, n, 2.0**-width)
            if 2 * k >= n and p_const <= FIELD_P:  # most frames share the value
                found = Field("constant", pos, width, value=value, p_value=p_const)
                break
            steps = [d for d in ((b - a) % (1 << width) for a, b in pairwise(values)) if d]
            if steps:
                step, ks = _mode(steps)
                # The step was picked from the data among 2**width possible ones.
                p_counter = min(1.0, binomial_tail(ks, n - 1, 2.0**-width) * (1 << width))
                if 2 * ks >= n - 1 and p_counter <= FIELD_P:  # most steps agree
                    found = Field("counter", pos, width, step=step, p_value=p_counter)
                    break
        if found is None:
            fields.append(Field("variable", pos, 8))
            break
        fields.append(found)
        pos += found.width
    return tuple(fields)


# --- CRC -----------------------------------------------------------------------------------

CRC_WIDTHS = (8, 16, 24, 32)
CRC_ALPHA = 1e-6

# Named parameter sets, to label a fit that matches (`name` stays None otherwise).
KNOWN_CRCS: tuple[Crc, ...] = (
    Crc("CRC-8", 8, 0x07, 0x00, False, False, 0x00),
    Crc("CRC-8/MAXIM", 8, 0x31, 0x00, True, True, 0x00),
    Crc("CRC-16/CCITT-FALSE", 16, 0x1021, 0xFFFF, False, False, 0x0000),
    Crc("CRC-16/XMODEM", 16, 0x1021, 0x0000, False, False, 0x0000),
    Crc("CRC-16/X-25", 16, 0x1021, 0xFFFF, True, True, 0xFFFF),
    Crc("CRC-16/KERMIT", 16, 0x1021, 0x0000, True, True, 0x0000),
    Crc("CRC-16/ARC", 16, 0x8005, 0x0000, True, True, 0x0000),
    Crc("CRC-16/MODBUS", 16, 0x8005, 0xFFFF, True, True, 0x0000),
    Crc("CRC-32", 32, 0x04C11DB7, 0xFFFFFFFF, True, True, 0xFFFFFFFF),
)


@dataclass(frozen=True)
class CrcFit:
    """A CRC found blind: the generator, the bit conventions, and the affine constant that
    combines the initial value and final XOR at this frame length."""

    width: int
    poly: int  # normal form, top bit omitted
    refin: bool
    refout: bool
    constant: int
    name: str | None  # a catalogued CRC that matches every fitted frame, if one does
    fitted: int  # frames the generator was fitted on
    passes: int  # held-out frames whose CRC field equals the fitted CRC
    heldout: int
    p_value: float
    threshold: float
    tried: int

    def check(self, frame: NDArray[np.integer]) -> bool:
        """Whether a frame (body then CRC field, this fit's length) passes."""
        data, stored = _split(np.asarray(frame, np.uint8), self.width, self.refin, self.refout)
        return stored == _remainder(data, self.width, self.poly | (1 << self.width)) ^ self.constant


def _reflect(value: int, width: int) -> int:
    return int(f"{value:0{width}b}"[::-1], 2)


def _split(frame: Bits, width: int, refin: bool, refout: bool) -> tuple[int, int]:
    """(data as a polynomial in the convention the generator divides, CRC register value)."""
    data, crc = frame[:-width], frame[-width:]
    if refin:
        # Bytes are counted back from the CRC. The frame body may begin a few bits before the true
        # data (a discovered prefix that stops short), and those leading bits are constant, so
        # dropping them changes nothing but the affine constant.
        data = data[len(data) % 8 :].reshape(-1, 8)[:, ::-1].ravel()
    stored = _to_int(crc)
    return _to_int(data), _reflect(stored, width) if refout else stored


def _remainder(data: int, width: int, generator: int) -> int:
    return pmod(data << width, generator)


MAX_GCD_WINDOWS = 16


def _generator(pairs: list[tuple[int, int]], width: int) -> int | None:
    """The degree-`width` polynomial that divides the XOR of most consecutive frame pairs.

    Candidates are the GCDs of three consecutive multiples (three intact frames' worth), so a
    few corrupted frames spoil only the windows they touch; the candidate dividing the most
    multiples wins, and must divide at least half of them."""
    multiples = [((d0 ^ d1) << width) ^ (r0 ^ r1) for (d0, r0), (d1, r1) in pairwise(pairs)]
    multiples = [m for m in multiples if m]
    if len(multiples) < 3:
        return None
    candidates: set[int] = set()
    for i in range(min(len(multiples) - 2, MAX_GCD_WINDOWS)):
        g = pgcd(pgcd(multiples[i], multiples[i + 1]), multiples[i + 2])
        if degree(g) == width and g & 1:
            candidates.add(g)
    best, support = None, 0
    for g in candidates:
        divides = sum(pmod(m, g) == 0 for m in multiples)
        if divides > support:
            best, support = g, divides
    return best if best is not None and support * 2 >= len(multiples) else None


def recover_crc(
    frames: NDArray[np.integer],
    *,
    widths: tuple[int, ...] = CRC_WIDTHS,
    alpha: float = CRC_ALPHA,
) -> CrcFit | None:
    """Recover a CRC at the end of equal-length `frames` (one per row, CRC field last), or None.

    Even rows fit the generator; odd rows test it. See the module docstring for the method."""
    f = np.asarray(frames, np.uint8)
    m = f.shape[1]
    train, test = f[0::2], f[1::2]
    if len(train) < 4 or len(test) < 4:
        return None
    variants = [(w, rin, rout) for w in widths for rin in (False, True) for rout in (False, True)]
    tried = len(variants)
    threshold = alpha / tried
    best: CrcFit | None = None
    for width, refin, rout in variants:
        if m <= width:
            continue
        pairs = [_split(row, width, refin, rout) for row in train]
        generator = _generator(pairs, width)
        if generator is None:
            continue
        # The affine constant is the same for every intact frame; take the most common.
        constant, agree = Counter(
            r ^ _remainder(d, width, generator) for d, r in pairs
        ).most_common(1)[0]
        if agree * 2 < len(pairs):
            continue
        fit = CrcFit(
            width,
            generator ^ (1 << width),
            refin,
            rout,
            constant,
            None,
            len(train),
            0,
            0,
            1.0,
            threshold,
            tried,
        )
        passes = sum(fit.check(row) for row in test)
        p = binomial_tail(passes, len(test), 2.0**-width)
        if p <= threshold and (best is None or p < best.p_value):
            best = CrcFit(
                width,
                fit.poly,
                refin,
                rout,
                constant,
                _name(fit, train),
                len(train),
                passes,
                len(test),
                p,
                threshold,
                tried,
            )
    return best


def _name(fit: CrcFit, train: Bits) -> str | None:
    """A catalogued CRC with this generator and conventions whose init and final XOR reproduce
    the fitted frames' CRC fields. The data may start up to 7 bits into the body (a prefix that
    stops short of the true data), so each such start is tried."""
    for known in KNOWN_CRCS:
        if (known.width, known.poly, known.refin, known.refout) != (
            fit.width,
            fit.poly,
            fit.refin,
            fit.refout,
        ):
            continue
        for skip in range(8):
            matches = sum(
                known.compute(row[skip : -fit.width]) == _to_int(row[-fit.width :]) for row in train
            )
            if matches * 10 >= len(train) * 9:  # a few corrupted frames do not hide the name
                return known.name
    return None


# --- the whole analysis --------------------------------------------------------------------


@dataclass(frozen=True)
class BlindFrames:
    sync: SyncDiscovery
    frames: Bits  # one row per whole frame, starting at the sync word
    fields: tuple[Field, ...]
    crc: CrcFit | None  # fitted on the bits after the sync word


def analyse_stream(bits: NDArray[np.integer], *, alpha: float = ALPHA) -> BlindFrames | None:
    """Sync word, frame length, header fields and CRC of a decoded bit stream, all blind.
    None when no sync structure is found; `sync.verified` says whether it recurs on held-out
    frames, and `crc` is None when no CRC is fitted."""
    sync = discover_sync(bits, alpha=alpha)
    if sync is None:
        return None
    frames = sync.frames()
    width = len(sync.word)
    crc = recover_crc(frames[:, width:])
    # Data is whole bytes counted back from the CRC field, which fixes where fields start.
    align = (frames.shape[1] - width - crc.width) % 8 if crc else None
    return BlindFrames(sync, frames, header_fields(frames, width, align=align), crc)
