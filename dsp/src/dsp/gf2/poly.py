"""Polynomials over GF(2) as Python ints: bit i is the coefficient of D**i (PLAN M5, M6).

Used where the polynomials are short and few (generator sets of convolutional codes, CRC
generators), so arbitrary-precision integers are simpler and faster than packed matrices.
"""


def pmul(a: int, b: int) -> int:
    """Carry-less product."""
    out = 0
    while b:
        if b & 1:
            out ^= a
        a <<= 1
        b >>= 1
    return out


def pdivmod(a: int, b: int) -> tuple[int, int]:
    """Quotient and remainder of a / b."""
    if b == 0:
        raise ZeroDivisionError("polynomial division by zero")
    q = 0
    while a and a.bit_length() >= b.bit_length():
        shift = a.bit_length() - b.bit_length()
        q |= 1 << shift
        a ^= b << shift
    return q, a


def pmod(a: int, b: int) -> int:
    return pdivmod(a, b)[1]


def pgcd(a: int, b: int) -> int:
    while b:
        a, b = b, pmod(a, b)
    return a


def plcm(a: int, b: int) -> int:
    return pmul(a, pdivmod(b, pgcd(a, b))[0])


def degree(a: int) -> int:
    """Degree of a non-zero polynomial (-1 for zero)."""
    return a.bit_length() - 1
