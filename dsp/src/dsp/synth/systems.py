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
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from dsp.synth.bits import Bits, int_bits

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
