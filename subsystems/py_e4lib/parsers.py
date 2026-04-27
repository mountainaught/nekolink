# py_e4lib/parsers.py

import struct
from .constants import TEMP_CALIBRATION


def parse_bvp(data: bytes):
    """Decode 7-bit packed delta encoding from a BVP notification."""
    decoded = []
    carry = 0

    for i in range(0x14):
        byte = data[i]
        mod = i % 7
        shift = mod + 1

        val = ((byte >> shift) | carry) & 0x7F
        if val & 0x40:
            val |= 0x80
        if val > 127:
            val -= 256
        decoded.append(val)

        carry = ((byte & ((1 << shift) - 1)) << (6 - mod)) & 0xFF

        if shift == 7:
            val = carry & 0x7F
            if val & 0x40:
                val |= 0x80
            if val > 127:
                val -= 256
            decoded.append(val)
            carry = 0

    tail = data[0x13] & 0x3F
    if tail & 0x20:
        tail |= 0xC0
    if tail > 127:
        tail -= 256
    decoded.append(tail)

    return decoded or None


def parse_gsr(data: bytes):
    """Parse GSR/EDA packet — 24-bit BE samples → microsiemens."""
    if len(data) < 20:
        return None
    readings = []
    for i in range(0, len(data) - 2, 3):
        raw = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2]
        readings.append(1_000_000.0 / raw if raw else 0.0)
    return readings or None


def parse_temp(data: bytes):
    """Parse temperature packet — u16 LE samples → °C."""
    if len(data) < 12:
        return None
    readings = []
    for i in range(0, 8, 2):
        raw = struct.unpack_from("<H", data, i)[0]
        readings.append(raw * 0.02 - 276.0 + TEMP_CALIBRATION)
    return readings or None


def parse_acc(data: bytes):
    """Parse accelerometer packet — signed byte triplets (raw; /64 for g)."""
    readings = []
    for i in range(0, len(data) - 2, 3):
        try:
            readings.append(struct.unpack_from("<bbb", data, i))
        except struct.error:
            break
    return readings or None