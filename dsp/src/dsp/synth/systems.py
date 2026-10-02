"""Known-system transmissions for the ground-truth generator (PLAN M6).

Written from the public specifications and independent of `dsp.systems`, which is what these
streams test: nothing here imports the decoder.

SITOR-B / NAVTEX (ITU-R M.476, M.540): 7-bit four-of-seven characters, each sent twice with the
repetition five slots after the first transmission. The structure (valid characters, the repeat
offset, the ZCZC / NNNN frame) is written here independently; the character table itself is data
shared with the decoder (`dsp.systems.ccir476`), so a wrong entry in it would not be caught by
these streams, only by its own checks (35 four-of-seven codes per set, the control codes).

POCSAG (ITU-R M.584-2): a 576-bit preamble of alternating bits, then batches of a synchronisation
codeword and 8 frames of 2 codewords; a codeword is 21 data bits, 10 BCH(31,21) check bits and an
even-parity bit.

AIS (ITU-R M.1371-6): packets of a 24-bit training sequence (0101...), the HDLC flag 01111110,
the message bits and a CRC-16/X.25 frame check sequence (low byte first, each byte least
significant bit first) with a 0 stuffed after five 1s, and a closing flag; the whole stream NRZI
coded (a 0 changes level). Written here from the Recommendation, with its own CRC and stuffing,
independent of `dsp.systems.ais`.

CCSDS TM LDPC (CCSDS 131.0-B-5): the 32-bit attached sync marker 0x1ACFFC1D, then the transmitted
columns of an AR4JA code word whose message is a transfer frame, the code word XORed with the
pseudo-randomiser (x^8 + x^7 + x^5 + x^3 + 1, all ones at the start of every code word, the
marker not covered). The randomiser is written here from its recurrence and checked in the tests
against the standard's published first bytes; the code words come from `synth.fec.standard_ldpc`
(galois), not from the decoder's encoder. The parity-check tables are the one thing shared with
`dsp.fec.ldpc`: a wrong entry in them would not be caught by these streams. The near-misses
(`fault`, `randomiser`, `asm`, `flips`) are streams the check must not accept.
"""

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from dsp.fec.ldpc import by_name
from dsp.synth.bits import Bits, int_bits, to_bits
from dsp.synth.fec import standard_ldpc

POCSAG_SYNC = 0x7CD215D8
POCSAG_IDLE = 0x7A89C197
POCSAG_PREAMBLE_BITS = 576
_BCH = (10, 9, 8, 6, 5, 3, 0)  # exponents of the generator polynomial


def pocsag_codeword(data21: int) -> int:
    """21 data bits -> 32-bit codeword: data, remainder of data * x^10 modulo the generator,
    then a parity bit making the whole word even."""
    register = data21 << 10
    generator = sum(1 << e for e in _BCH)
    for degree in range(30, 9, -1):
        if register & (1 << degree):
            register ^= generator << (degree - 10)
    word31 = (data21 << 10) | register
    return (word31 << 1) | (bin(word31).count("1") & 1)


def pocsag_address(ric: int, function: int) -> int:
    """The address codeword for a 21-bit address: 18 bits here, the low 3 pick the frame."""
    return pocsag_codeword(((ric >> 3) << 2) | function)


def pocsag_text_words(text: str) -> list[int]:
    """Message codewords for 7-bit ASCII, each character least significant bit first, packed 20
    bits to a codeword and padded with the end-of-transmission character 0x04."""
    stream: list[int] = []
    for ch in text:
        stream += [(ord(ch) >> k) & 1 for k in range(7)]
    while len(stream) % 20:
        stream += [(0x04 >> k) & 1 for k in range(7)]
    stream = stream[: len(stream) - len(stream) % 20]
    return [
        pocsag_codeword((1 << 20) | int("".join(map(str, stream[i : i + 20])), 2))
        for i in range(0, len(stream), 20)
    ]


@dataclass(frozen=True)
class Pocsag:
    """A POCSAG transmission: pages of (address, function, text), sent in order, then repeated
    (each repeat preceded by a preamble) so a recording of any length is filled. `corrupt` flips
    that fraction of the bits after coding, to test that a damaged codeword is not trusted."""

    pages: tuple[tuple[int, int, str], ...] = ((1234567, 3, "HELLO SANKET"),)
    corrupt: float = 0.0

    def transmission(self) -> Bits:
        codewords: list[int] = []  # batch slots, the synchronisation codewords excluded
        for ric, function, text in self.pages:
            while len(codewords) % 16 != 2 * (ric & 7):
                codewords.append(POCSAG_IDLE)
            codewords.append(pocsag_address(ric, function))
            codewords += pocsag_text_words(text)
        while len(codewords) % 16:
            codewords.append(POCSAG_IDLE)
        out: list[Bits] = [np.tile(np.array([1, 0], np.uint8), POCSAG_PREAMBLE_BITS // 2)]
        for i in range(0, len(codewords), 16):
            out.append(int_bits(POCSAG_SYNC, 32))
            out += [int_bits(w, 32) for w in codewords[i : i + 16]]
        return np.concatenate(out)

    def truth(self) -> dict[str, object]:
        return {
            "system": "POCSAG",
            "pages": [
                {"address": ric, "function": fn, "text": text} for ric, fn, text in self.pages
            ],
            "batchBits": 544,
            "corrupt": self.corrupt,
        }

    def stream(self, needed: int, rng: np.random.Generator) -> tuple[NDArray[np.uint8], Bits, Bits]:
        """(payload rows, the bits before corruption, the transmitted bits), at least `needed`."""
        one = self.transmission()
        clean = np.tile(one, -(-needed // len(one)))
        sent = clean.copy()
        if self.corrupt:
            sent ^= (rng.random(len(sent)) < self.corrupt).astype(np.uint8)
        return np.zeros((0, 0), np.uint8), clean, sent


def _encode_text(text: str) -> list[int]:
    """CCIR 476 characters for `text`, shifting between the letters and figures sets as needed
    (space, carriage return and line feed are in both and leave the shift alone)."""
    from dsp.systems.ccir476 import FIGS, FIGURES, LETTERS, LTRS

    both = {" ": " ", "\r": "CR", "\n": "LF"}
    letters = {v: k for k, v in LETTERS.items() if len(v) == 1 and v != " "}
    figures = {v: k for k, v in FIGURES.items() if len(v) == 1 and v != " "}
    shared = {v: k for k, v in LETTERS.items() if v in ("CR", "LF", " ")}
    out = [LTRS]
    shift = "letters"
    for ch in text:
        if ch in both:
            out.append(shared[both[ch]])
        elif ch in letters:
            if shift != "letters":
                out.append(LTRS)
                shift = "letters"
            out.append(letters[ch])
        elif ch in figures:
            if shift != "figures":
                out.append(FIGS)
                shift = "figures"
            out.append(figures[ch])
        else:
            raise ValueError(f"{ch!r} has no CCIR 476 code")
    return out


@dataclass(frozen=True)
class Navtex:
    """A NAVTEX message (ZCZC B1B2B3B4, text, NNNN) sent in SITOR-B: characters on the
    four-of-seven code, DX and RX slots alternating with each character repeated five slots after
    its first transmission, behind a phasing run and followed by idle signals. The transmission is
    repeated to fill a recording of any length."""

    station: str = "E"
    subject: str = "A"
    serial: int = 12
    text: str = "GALE WARNING. SEA AREA FORTH: WIND 7/8 FROM 270."
    corrupt: float = 0.0

    def message(self) -> str:
        head = f"ZCZC {self.station}{self.subject}{self.serial:02d}"
        return head + "\r\n" + self.text + "\r\nNNNN\r\n"

    def transmission(self) -> Bits:
        from dsp.systems.ccir476 import SIA, SIB

        chars = _encode_text(self.message())
        dx = [SIB] * 10 + chars + [SIB] * 6  # phasing first, then the message, then idle
        slots: list[int] = []
        for n, c in enumerate(dx):
            slots.append(c)  # DX slot 2n
            earlier = dx[n - 2] if n >= 2 else SIA
            slots.append(earlier if earlier not in (SIB,) else SIA)  # RX slot 2n + 1
        return np.concatenate([int_bits(w, 7) for w in slots])

    def truth(self) -> dict[str, object]:
        return {
            "system": "NAVTEX",
            "station": self.station,
            "subject": self.subject,
            "serial": f"{self.serial:02d}",
            "text": self.text,
            "repeatSlots": 5,
            "corrupt": self.corrupt,
        }

    def stream(self, needed: int, rng: np.random.Generator) -> tuple[NDArray[np.uint8], Bits, Bits]:
        one = self.transmission()
        clean = np.tile(one, -(-needed // len(one)))
        sent = clean.copy()
        if self.corrupt:
            sent ^= (rng.random(len(sent)) < self.corrupt).astype(np.uint8)
        return np.zeros((0, 0), np.uint8), clean, sent


def dsc_symbol_bits(symbol: int) -> Bits:
    """A DSC character (ITU-R M.493 Annex 1 section 1.1): seven information bits least
    significant first, then the count of B (0) elements among them as three bits, most
    significant first."""
    info = [(symbol >> i) & 1 for i in range(7)]
    zeros = 7 - sum(info)
    return np.array([*info, zeros >> 2 & 1, zeros >> 1 & 1, zeros & 1], np.uint8)


@dataclass(frozen=True)
class Dsc:
    """An MF/HF DSC call (ITU-R M.493 Annex 1): a 200-bit dot pattern, the phasing sequence, the
    format specifier twice, the content, the EOS three times and the ECC, each information
    character repeated five slots after its first transmission. Field meanings are not claimed:
    the content is an address of five two-digit symbols, a category and a self-identity, then
    two telecommands and filler. Simplified at the ends: every information character is repeated
    alike (the Recommendation sends the EOS once in RX), and two filler symbols flush the last
    repetitions. The call repeats to fill a recording of any length."""

    format: int = 120
    address: str = "2010203040"
    category: int = 100
    self_id: str = "9988776650"
    eos: int = 127
    corrupt: float = 0.0

    def symbols(self) -> list[int]:
        """The information characters in DX order, ECC last."""

        def digits(s: str) -> list[int]:
            return [int(s[i : i + 2]) for i in range(0, 10, 2)]

        content = [*digits(self.address), self.category, *digits(self.self_id), 100, 126]
        parity = self.format ^ self.eos
        for s in content:
            parity ^= s
        return [self.format, self.format, *content, self.eos, self.eos, self.eos, parity]

    def transmission(self) -> Bits:
        slots = [125, 111, 125, 110, 125, 109, 125, 108, 125, 107, 125, 106, 105, 104]
        dx = [*self.symbols(), 126, 126]  # the filler flushes the last two repetitions
        for n, d in enumerate(dx):
            slots.append(d)
            slots.append(dx[n - 2] if n >= 2 else 104)
        dots = np.tile(np.array([1, 0], np.uint8), 100)
        return np.concatenate([dots, *(dsc_symbol_bits(s) for s in slots)])

    def truth(self) -> dict[str, object]:
        return {
            "system": "DSC",
            "format": self.format,
            "address": self.address,
            "category": self.category,
            "selfId": self.self_id,
            "eos": self.eos,
            "symbols": self.symbols(),
            "repeatSlots": 5,
            "corrupt": self.corrupt,
        }

    def stream(self, needed: int, rng: np.random.Generator) -> tuple[NDArray[np.uint8], Bits, Bits]:
        one = self.transmission()
        clean = np.tile(one, -(-needed // len(one)))
        sent = clean.copy()
        if self.corrupt:
            sent ^= (rng.random(len(sent)) < self.corrupt).astype(np.uint8)
        return np.zeros((0, 0), np.uint8), clean, sent


def _crc16_x25(data: bytes) -> int:
    register = 0xFFFF
    for byte in data:
        register ^= byte
        for _ in range(8):
            register = (register >> 1) ^ 0x8408 if register & 1 else register >> 1
    return register ^ 0xFFFF


def _stuffed(bits: list[int]) -> list[int]:
    out: list[int] = []
    run = 0
    for bit in bits:
        out.append(bit)
        run = run + 1 if bit else 0
        if run == 5:
            out.append(0)
            run = 0
    return out


@dataclass(frozen=True)
class Ais:
    """AIS position reports (message type 1, 168 bits) from the given MMSIs, in turn, repeated to
    fill a recording. The other 130 message bits are drawn at random: nothing in the check
    depends on them. `corrupt` flips that fraction of the transmitted bits."""

    mmsis: tuple[int, ...] = (227006760, 366999712, 235099999)
    corrupt: float = 0.0
    seed: int = 1

    def packets(self, count: int) -> list[Bits]:
        """`count` packets' message bits (field order, MSB first), type 1 and the MMSI set."""
        rng = np.random.default_rng(self.seed)
        out: list[Bits] = []
        for i in range(count):
            mmsi = self.mmsis[i % len(self.mmsis)]
            fixed = np.concatenate([int_bits(1, 6), int_bits(0, 2), int_bits(mmsi, 30)])
            out.append(np.concatenate([fixed, rng.integers(0, 2, 130, dtype=np.uint8)]))
        return out

    def packet_bits(self, message: Bits) -> Bits:
        """Training sequence, flag, stuffed message and FCS, flag, before NRZI coding."""
        data = bytes(
            int(sum(int(b) << k for k, b in enumerate(message[i : i + 8])))
            for i in range(0, len(message), 8)
        )
        fcs = _crc16_x25(data)
        fcs_bytes = fcs.to_bytes(2, "little")
        fcs_bits = [(byte >> k) & 1 for byte in fcs_bytes for k in range(8)]
        body = _stuffed([int(b) for b in message] + fcs_bits)
        flag = [0, 1, 1, 1, 1, 1, 1, 0]
        return np.array([0, 1] * 12 + flag + body + flag, np.uint8)

    def transmission(self, count: int = 8) -> Bits:
        stream = np.concatenate([self.packet_bits(m) for m in self.packets(count)])
        # NRZI: a 0 toggles the level, a 1 holds it.
        level = np.cumsum(1 - stream) % 2
        return level.astype(np.uint8)

    def truth(self) -> dict[str, object]:
        return {
            "system": "AIS",
            "messageType": 1,
            "mmsis": list(self.mmsis),
            "messageBits": 168,
            "corrupt": self.corrupt,
        }

    def stream(self, needed: int, rng: np.random.Generator) -> tuple[NDArray[np.uint8], Bits, Bits]:
        one = self.transmission()
        # Each repetition restarts from level 0 at a packet boundary: `one` ends at some level,
        # so successive repeats are NRZI-continuous only if the level is carried: re-encode the
        # whole run from the packet bits instead.
        reps = -(-needed // len(one))
        raw = np.concatenate([self.packet_bits(m) for m in self.packets(8 * reps)])
        clean = (np.cumsum(1 - raw) % 2).astype(np.uint8)
        sent = clean.copy()
        if self.corrupt:
            sent ^= (rng.random(len(sent)) < self.corrupt).astype(np.uint8)
        return np.zeros((0, 0), np.uint8), clean, sent


CCSDS_ASM = 0x1ACFFC1D
CCSDS_SPACECRAFT = 0x1A5  # the primary header the synthetic transfer frames carry
CCSDS_VIRTUAL_CHANNEL = 2


def _recurrence(taps: tuple[int, ...], seed_bits: int, n: int) -> Bits:
    """The sequence a[k] = XOR of a[k - t] for t in `taps`, from `seed_bits` ones."""
    a = [1] * seed_bits
    while len(a) < n:
        value = 0
        for t in taps:
            value ^= a[len(a) - t]
        a.append(value)
    return np.array(a[:n], np.uint8)


def ccsds_randomiser(n: int) -> Bits:
    """The first `n` bits of the CCSDS 131.0-B pseudo-random sequence, h(x) = x^8 + x^7 + x^5 +
    x^3 + 1 from the all-ones register (period 255): a[k] = a[k-1] ^ a[k-3] ^ a[k-5] ^ a[k-8],
    which begins FF 48 0E C0 9A 0D 70 BC as the standard lists it."""
    one = _recurrence((1, 3, 5, 8), 8, 255)
    return np.tile(one, -(-n // 255))[:n]


def _wrong_randomiser(n: int) -> Bits:
    """Another scrambler's sequence (IEEE 802.11's x^7 + x^4 + 1, all ones): not the CCSDS one."""
    one = _recurrence((3, 7), 7, 127)
    return np.tile(one, -(-n // 127))[:n]


@dataclass(frozen=True)
class CcsdsLdpc:
    """A CCSDS TM LDPC transmission: marker, randomised code word, marker, ... of one catalogued
    AR4JA code (`code` is its name in `dsp.fec.ldpc`), repeated to fill a recording. Each message
    is a TM transfer frame: a 6-byte primary header (version 0, spacecraft 0x1A5, virtual channel 2,
    frame counts) and random data.

    Defects, each a stream the check must not verify: `randomiser="wrong"` (another LFSR) or
    "none" (the code words not randomised, which the check treats as its own hypothesis and
    names); `asm=False` (no marker: code words back to back); `fault` "shuffle" (the code word's
    bits permuted), "parity" (the message right, the parity bits random) or "other-code" (the
    code word of the other rate of the same k, padded or cut to this code's length); `flips`
    flips that many bits of every transmitted code word, which is a channel error, not a defect:
    a few of them are corrected."""

    code: str = "CCSDS TM k=1024 r1/2"
    randomiser: Literal["ccsds", "wrong", "none"] = "ccsds"
    asm: bool = True
    fault: Literal["none", "shuffle", "parity", "other-code"] = "none"
    flips: int = 0
    seed: int = 1

    def messages(self, count: int) -> Bits:
        """The transfer frames' bits, `count` rows of k."""
        k = by_name(self.code).k
        rng = np.random.default_rng([self.seed, 1])
        out = rng.integers(0, 2, (count, k), dtype=np.uint8)
        for i in range(count):
            header = bytes(
                [
                    CCSDS_SPACECRAFT >> 4,
                    (CCSDS_SPACECRAFT & 0xF) << 4 | CCSDS_VIRTUAL_CHANNEL << 1,
                    i & 0xFF,
                    i & 0xFF,
                    0,
                    0,
                ]
            )
            out[i, :48] = to_bits(header)
        return out

    def _other(self) -> str:
        return (
            self.code.replace("r1/2", "r2/3")
            if "r1/2" in self.code
            else (self.code.replace("r2/3", "r1/2").replace("r4/5", "r1/2"))
        )

    def codewords(self, messages: Bits) -> Bits:
        """The transmitted bits of each message, before randomising: rows of `transmitted`."""
        code = by_name(self.code)
        rng = np.random.default_rng([self.seed, 2])
        tx = code.transmitted
        if self.fault == "other-code":
            other = by_name(self._other())
            words = standard_ldpc(other).encode(messages.ravel()).reshape(len(messages), -1)
            filler = rng.integers(0, 2, (len(messages), max(0, tx - words.shape[1])), np.uint8)
            return np.hstack([words, filler])[:, :tx]
        words = standard_ldpc(code).encode(messages.ravel()).reshape(len(messages), tx)
        if self.fault == "parity":
            words[:, code.k :] = rng.integers(0, 2, (len(messages), tx - code.k), np.uint8)
        elif self.fault == "shuffle":
            words = words[:, rng.permutation(tx)]
        return words

    def transmission(self, count: int) -> tuple[Bits, Bits]:
        """(message rows, the stream of `count` marker + code word blocks)."""
        code = by_name(self.code)
        tx = code.transmitted
        messages = self.messages(count)
        words = self.codewords(messages)
        mask = {
            "ccsds": ccsds_randomiser(tx),
            "wrong": _wrong_randomiser(tx),
            "none": np.zeros(tx, np.uint8),
        }[self.randomiser]
        marker = int_bits(CCSDS_ASM, 32) if self.asm else np.zeros(0, np.uint8)
        blocks = [np.concatenate([marker, w ^ mask]) for w in words]
        return messages, np.concatenate(blocks)

    def truth(self) -> dict[str, object]:
        code = by_name(self.code)
        return {
            "system": "CCSDS TM LDPC",
            "code": self.code,
            "k": code.k,
            "n": code.n,
            "transmittedBits": code.transmitted,
            "punctured": code.punctured,
            "asm": f"0x{CCSDS_ASM:08X}" if self.asm else None,
            "periodBits": code.transmitted + (32 if self.asm else 0),
            "randomiser": self.randomiser,
            "fault": self.fault,
            "flips": self.flips,
            "spacecraft": CCSDS_SPACECRAFT,
            "virtualChannel": CCSDS_VIRTUAL_CHANNEL,
        }

    def stream(self, needed: int, rng: np.random.Generator) -> tuple[NDArray[np.uint8], Bits, Bits]:
        """(message rows packed to bytes, the bits before channel errors, the transmitted bits), at
        least `needed` bits."""
        code = by_name(self.code)
        period = code.transmitted + (32 if self.asm else 0)
        count = -(-needed // period) + 1
        messages, clean = self.transmission(count)
        sent = clean.copy()
        if self.flips:
            flip_rng = np.random.default_rng([self.seed, 3])
            for i in range(count):
                at = flip_rng.choice(code.transmitted, self.flips, replace=False)
                sent[i * period + period - code.transmitted + at] ^= 1
        return np.packbits(messages, axis=1), clean, sent
