"""Byte order definitions for protocol-level register serialization."""

from __future__ import annotations

from enum import StrEnum, auto


class ByteOrder(StrEnum):
    """Byte order for serializing multi-byte register values over serial buses.

    Attributes:
        BIG: Most-significant byte first (bus-standard default for I2C/SPI).
        LITTLE: Least-significant byte first (common in x86-connected peripherals).
    """

    BIG = auto()
    LITTLE = auto()


def serialize_register(value: int, byte_order: ByteOrder) -> list[int]:
    """Split a register value into a byte list using the specified byte order.

    8-bit values (≤ 0xFF) are returned as a single-element list.
    16-bit values (≤ 0xFFFF) are split into two bytes.

    Args:
        value: Integer register value (8-bit or 16-bit).
        byte_order: Byte order for serialization.

    Returns:
        List of bytes representing the value.
    """
    if value <= 0xFF:
        return [value]
    high = (value >> 8) & 0xFF
    low = value & 0xFF
    return [high, low] if byte_order == ByteOrder.BIG else [low, high]
