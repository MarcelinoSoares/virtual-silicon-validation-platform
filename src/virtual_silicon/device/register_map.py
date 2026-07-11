"""Register map containing all chip registers with addresses and defaults."""

from __future__ import annotations

import logging
from collections.abc import Iterator

from virtual_silicon.device.register import (
    AccessType,
    InvalidRegisterAddressError,
    Register,
    RegisterBehavior,
    RegisterSize,
)

logger = logging.getLogger(__name__)


class RegisterMap:
    """Container for all virtual chip registers.

    Provides address-based and name-based access to virtual registers
    that represent the register space of a virtual silicon device.
    """

    def __init__(self) -> None:
        """Initialize the register map with default chip registers."""
        self._registers: dict[int, Register] = {}
        self._name_index: dict[str, Register] = {}
        self._initialize_registers()

    def _initialize_registers(self) -> None:
        """Create all virtual chip registers with their configurations."""
        registers = [
            Register(
                name="DEVICE_ID",
                address=0x00,
                size=RegisterSize.BITS_8,
                access=AccessType.READ_ONLY,
                reset_value=0xA5,
                description="Unique device identifier (read-only).",
            ),
            Register(
                name="DEVICE_STATUS",
                address=0x01,
                size=RegisterSize.BITS_8,
                access=AccessType.READ_ONLY,
                reset_value=0x00,
                description="Device status flags (read-only).",
            ),
            Register(
                name="POWER_CONTROL",
                address=0x02,
                size=RegisterSize.BITS_8,
                access=AccessType.READ_WRITE,
                reset_value=0x00,
                bit_mask=0x0F,
                description="Power management control register.",
            ),
            Register(
                name="TEMPERATURE",
                address=0x03,
                size=RegisterSize.BITS_8,
                access=AccessType.READ_ONLY,
                reset_value=0x19,
                description="Temperature reading in Celsius (read-only).",
            ),
            Register(
                name="VOLTAGE_LEVEL",
                address=0x04,
                size=RegisterSize.BITS_16,
                access=AccessType.READ_ONLY,
                reset_value=0x0C80,
                description="Voltage level in millivolts (read-only).",
            ),
            Register(
                name="CURRENT_LEVEL",
                address=0x06,
                size=RegisterSize.BITS_16,
                access=AccessType.READ_ONLY,
                reset_value=0x0064,
                description="Current level in milliamps (read-only).",
            ),
            Register(
                name="DISPLAY_CONFIG",
                address=0x08,
                size=RegisterSize.BITS_8,
                access=AccessType.READ_WRITE,
                reset_value=0x80,
                description="Display configuration and brightness.",
            ),
            Register(
                name="ERROR_FLAGS",
                address=0x09,
                size=RegisterSize.BITS_8,
                access=AccessType.READ_WRITE,
                reset_value=0x00,
                behavior=RegisterBehavior.WRITE_ONE_TO_CLEAR,
                description="Error flag register. Write 1 to clear each bit (W1C).",
            ),
            Register(
                name="FIRMWARE_VERSION",
                address=0x0A,
                size=RegisterSize.BITS_16,
                access=AccessType.READ_ONLY,
                reset_value=0x0100,
                description="Firmware version (major.minor).",
            ),
            Register(
                name="INTERRUPT_STATUS",
                address=0x0C,
                size=RegisterSize.BITS_8,
                access=AccessType.READ_WRITE,
                reset_value=0x00,
                behavior=RegisterBehavior.WRITE_ONE_TO_CLEAR,
                description="Interrupt status flags. Write 1 to clear each bit (W1C).",
            ),
        ]
        for reg in registers:
            self._registers[reg.address] = reg
            self._name_index[reg.name] = reg
        logger.debug("Initialized register map with %d registers.", len(registers))

    def read(self, address: int) -> int:
        """Read a register value by address.

        Args:
            address: Register address.

        Returns:
            Register value.

        Raises:
            InvalidRegisterAddressError: If address is not mapped.
        """
        reg = self._get_register(address)
        return reg.read()

    def write(self, address: int, value: int) -> None:
        """Write a value to a register by address.

        Args:
            address: Register address.
            value: Value to write.

        Raises:
            InvalidRegisterAddressError: If address is not mapped.
        """
        reg = self._get_register(address)
        reg.write(value)

    def read_register(self, address: int) -> int:
        """Alias for read() — satisfies the RegisterDevice protocol."""
        return self.read(address)

    def write_register(self, address: int, value: int) -> None:
        """Alias for write() — satisfies the RegisterDevice protocol."""
        self.write(address, value)

    def get_by_name(self, name: str) -> Register:
        """Get register by name.

        Args:
            name: Register name.

        Returns:
            Register instance.

        Raises:
            InvalidRegisterAddressError: If name is not found.
        """
        if name not in self._name_index:
            raise InvalidRegisterAddressError(f"Register '{name}' not found in map.")
        return self._name_index[name]

    def _get_register(self, address: int) -> Register:
        """Internal helper to get register by address."""
        if address not in self._registers:
            raise InvalidRegisterAddressError(f"No register at address 0x{address:04X}.")
        return self._registers[address]

    def reset_all(self) -> None:
        """Reset all registers to their default reset values."""
        for reg in self._registers.values():
            reg.reset()
        logger.info("All registers reset to default values.")

    def get_snapshot(self) -> dict[str, int]:
        """Return a dict snapshot of all register values by name."""
        snapshot: dict[str, int] = {}
        for name, reg in self._name_index.items():
            try:
                snapshot[name] = reg.read()
            except Exception:
                snapshot[name] = reg.value
        return snapshot

    def __iter__(self) -> Iterator[Register]:
        """Iterate over all registers."""
        return iter(self._registers.values())

    def __len__(self) -> int:
        """Number of registers in the map."""
        return len(self._registers)

    def __contains__(self, address: object) -> bool:
        """Check if address is in the map."""
        return address in self._registers
