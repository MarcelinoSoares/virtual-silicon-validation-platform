"""Virtual register model supporting 8/16/32-bit registers with access control."""

from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class AccessType(Enum):
    """Register access type enumeration."""

    READ_WRITE = "rw"
    READ_ONLY = "ro"
    WRITE_ONLY = "wo"


class RegisterSize(Enum):
    """Register size enumeration."""

    BITS_8 = 8
    BITS_16 = 16
    BITS_32 = 32


class InvalidRegisterAddressError(Exception):
    """Raised when an invalid register address is accessed."""


class RegisterAccessError(Exception):
    """Raised when a register access violation occurs."""


class Register:
    """Virtual silicon register with configurable access, size, and bit masking.

    Supports 8-bit, 16-bit, and 32-bit registers with read-only, write-only,
    read-write access modes, reset values, bit masks, and field extraction.
    """

    def __init__(
        self,
        name: str,
        address: int,
        size: RegisterSize = RegisterSize.BITS_8,
        access: AccessType = AccessType.READ_WRITE,
        reset_value: int = 0x00,
        bit_mask: int | None = None,
        description: str = "",
        min_value: int | None = None,
        max_value: int | None = None,
    ) -> None:
        """Initialize a virtual register.

        Args:
            name: Human-readable register name.
            address: Register memory address.
            size: Register width (8, 16, or 32 bits).
            access: Access type (RW, RO, WO).
            reset_value: Default value after reset.
            bit_mask: Bitmask for valid bits (None = all bits valid).
            description: Human-readable description.
            min_value: Minimum allowed write value.
            max_value: Maximum allowed write value.
        """
        self.name = name
        self.address = address
        self.size = size
        self.access = access
        self.reset_value = reset_value
        self.description = description
        self.min_value = min_value
        self.max_value = max_value
        self._max_bits = (1 << size.value) - 1
        self.bit_mask = bit_mask if bit_mask is not None else self._max_bits
        self._value: int = reset_value & self.bit_mask
        self._write_count: int = 0
        self._read_count: int = 0

    @property
    def value(self) -> int:
        """Current register value."""
        return self._value

    def read(self) -> int:
        """Read the register value.

        Returns:
            The current register value.

        Raises:
            RegisterAccessError: If register is write-only.
        """
        if self.access == AccessType.WRITE_ONLY:
            raise RegisterAccessError(
                f"Register '{self.name}' at 0x{self.address:04X} is write-only."
            )
        self._read_count += 1
        logger.debug("Read register '%s' [0x%04X] = 0x%X", self.name, self.address, self._value)
        return self._value

    def write(self, value: int) -> None:
        """Write a value to the register.

        Args:
            value: Value to write.

        Raises:
            RegisterAccessError: If register is read-only or value is out of range.
        """
        if self.access == AccessType.READ_ONLY:
            raise RegisterAccessError(
                f"Register '{self.name}' at 0x{self.address:04X} is read-only."
            )
        if value < 0 or value > self._max_bits:
            raise RegisterAccessError(
                f"Value 0x{value:X} out of range for {self.size.value}-bit register '{self.name}'."
            )
        if self.min_value is not None and value < self.min_value:
            raise RegisterAccessError(
                f"Value {value} below minimum {self.min_value} for register '{self.name}'."
            )
        if self.max_value is not None and value > self.max_value:
            raise RegisterAccessError(
                f"Value {value} above maximum {self.max_value} for register '{self.name}'."
            )
        masked_value = value & self.bit_mask
        self._value = masked_value
        self._write_count += 1
        logger.debug("Wrote register '%s' [0x%04X] = 0x%X", self.name, self.address, masked_value)

    def reset(self) -> None:
        """Reset register to its default reset value."""
        self._value = self.reset_value & self.bit_mask
        logger.debug("Reset register '%s' [0x%04X] to 0x%X", self.name, self.address, self._value)

    def get_field(self, bit_start: int, bit_length: int) -> int:
        """Extract a bit field from the register.

        Args:
            bit_start: Starting bit position (0 = LSB).
            bit_length: Number of bits to extract.

        Returns:
            Extracted field value.
        """
        mask = (1 << bit_length) - 1
        return (self._value >> bit_start) & mask

    def set_field(self, bit_start: int, bit_length: int, field_value: int) -> None:
        """Update a bit field in the register.

        Args:
            bit_start: Starting bit position (0 = LSB).
            bit_length: Number of bits to update.
            field_value: New field value.
        """
        mask = (1 << bit_length) - 1
        cleared = self._value & ~(mask << bit_start)
        new_value = cleared | ((field_value & mask) << bit_start)
        self.write(new_value)

    @property
    def write_count(self) -> int:
        """Number of times this register has been written."""
        return self._write_count

    @property
    def read_count(self) -> int:
        """Number of times this register has been read."""
        return self._read_count

    def __repr__(self) -> str:
        """Return string representation of the register."""
        return (
            f"Register(name={self.name!r}, address=0x{self.address:04X}, "
            f"value=0x{self._value:X}, access={self.access.value})"
        )
