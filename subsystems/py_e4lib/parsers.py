# py_e4lib/parsers.py

import struct
from typing import List, Tuple, Optional
from .constants import TEMP_CALIBRATION


def parse_bvp(data: bytes) -> List[Tuple[int, int]]:
    """Decode 7-bit packed delta encoding."""
    decoded = []
    uVar28 = 0

    for uVar37 in range(0x14):
        bVar21 = data[uVar37]
        iVar31 = uVar37 % 7
        uVar36 = iVar31 + 1

        uVar28 = (bVar21 >> uVar36) | uVar28

        output_val = uVar28 & 0x7F
        if output_val & 0x40:
            output_val |= 0x80
        if output_val > 127:
            output_val -= 256
        decoded.append(output_val)

        mask = (1 << uVar36) - 1
        uVar28 = ((bVar21 & mask) << (6 - iVar31)) & 0xFF

        if uVar36 == 7:
            output_val = uVar28 & 0x7F
            if output_val & 0x40:
                output_val |= 0x80
            if output_val > 127:
                output_val -= 256
            decoded.append(output_val)
            uVar28 = 0

    final_val = data[0x13] & 0x3F
    if final_val & 0x20:
        final_val |= 0xC0
    if final_val > 127:
        final_val -= 256
    decoded.append(final_val)

    return decoded if decoded else None


def parse_gsr(data: bytes) -> Optional[List[float]]:
    """
    Parse GSR/EDA packet into list of values in microsiemens.
    Uses 24-bit big endian encoding, 6 samples per packet.
    """
    if len(data) < 20:
        return None

    readings = []
    i = 0

    while i + 3 <= len(data) - 2:
        byte1 = data[i]
        byte2 = data[i + 1]
        byte3 = data[i + 2]

        raw_value = (byte1 << 16) | (byte2 << 8) | byte3
        eda_microsiemens = 1000000.0 / raw_value if raw_value > 0 else 0

        readings.append(eda_microsiemens)
        i += 3

    return readings if readings else None


def parse_temp(data: bytes) -> Optional[List[float]]:
    """
    Parse temperature packet into list of values in Celsius.
    Uses unsigned 16-bit little endian encoding, 4 samples per packet.
    """
    if len(data) < 12:
        return None

    temp_readings = []
    i = 0

    while i < 8:
        raw = struct.unpack_from('<H', data, i)[0]
        temp = ((raw * 0.02) - 276.0) + TEMP_CALIBRATION
        temp_readings.append(temp)
        i += 2

    return temp_readings if temp_readings else None


def parse_acc(data: bytes) -> Optional[List[Tuple[int, int, int]]]:
    """
    Parse accelerometer packet into list of (x, y, z) tuples.
    Values are raw, divide by 64.0 to get g-force.
    """
    acc_readings = []
    i = 0

    while i + 3 <= len(data):
        try:
            x, y, z = struct.unpack_from('<bbb', data, i)
            acc_readings.append((x, y, z))
            i += 3
        except struct.error:
            break

    return acc_readings if acc_readings else None