"""VirtualChip: top-level chip simulation integrating registers and SRAM."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from virtual_silicon.device.memory import SRAM, MemoryTestResult
from virtual_silicon.device.register_map import RegisterMap

logger = logging.getLogger(__name__)


class DeviceNotPoweredError(Exception):
    """Raised when an operation is attempted on an unpowered device."""


class VirtualChip:
    """Virtual silicon chip simulation integrating RegisterMap and SRAM.

    Provides a unified interface for register access, SRAM operations,
    power management, cycle tracking, fault injection, and health reporting.
    """

    FIRMWARE_MAJOR = 1
    FIRMWARE_MINOR = 0
    CHIP_VERSION = "VS-1000-A"

    def __init__(self, sram_size: int = 256, seed: int | None = None) -> None:
        """Initialize the virtual chip.

        Args:
            sram_size: SRAM size in bytes.
            seed: Random seed for deterministic SRAM tests.
        """
        self._register_map = RegisterMap()
        self._sram = SRAM(size=sram_size, seed=seed)
        self._powered: bool = False
        self._cycle_count: int = 0
        self._power_on_time: float | None = None
        self._fault_callbacks: list[Callable[[str, int, int], None]] = []
        logger.info("VirtualChip initialized. SRAM=%d bytes, seed=%s.", sram_size, seed)

    @property
    def powered(self) -> bool:
        """Return True if the chip is powered on."""
        return self._powered

    @property
    def cycle_count(self) -> int:
        """Number of read/write cycles executed."""
        return self._cycle_count

    @property
    def register_map(self) -> RegisterMap:
        """The chip's register map."""
        return self._register_map

    @property
    def sram(self) -> SRAM:
        """The chip's SRAM instance."""
        return self._sram

    def power_on(self) -> None:
        """Power on the chip and initialize registers to reset values."""
        if self._powered:
            logger.warning("Chip is already powered on.")
            return
        self._powered = True
        self._power_on_time = time.monotonic()
        self._register_map.reset_all()
        self._sram.clear()
        self._cycle_count = 0
        logger.info("Chip powered ON. Registers reset, SRAM cleared.")

    def power_off(self) -> None:
        """Power off the chip."""
        if not self._powered:
            logger.warning("Chip is already powered off.")
            return
        self._powered = False
        logger.info("Chip powered OFF after %d cycles.", self._cycle_count)

    def reset(self) -> None:
        """Reset chip without power cycle: restore register defaults and clear SRAM."""
        self._register_map.reset_all()
        self._sram.clear()
        self._cycle_count = 0
        logger.info("Chip reset.")

    def read_register(self, address: int) -> int:
        """Read a register by address.

        Args:
            address: Register address.

        Returns:
            Register value.

        Raises:
            DeviceNotPoweredError: If chip is not powered.
            InvalidRegisterAddressError: If address is not mapped.
            RegisterAccessError: If register is write-only.
        """
        self._require_power()
        self._cycle_count += 1
        self._trigger_fault_callbacks("register_read", address)
        return self._register_map.read(address)

    def write_register(self, address: int, value: int) -> None:
        """Write a value to a register by address.

        Args:
            address: Register address.
            value: Value to write.

        Raises:
            DeviceNotPoweredError: If chip is not powered.
            InvalidRegisterAddressError: If address is not mapped.
            RegisterAccessError: If register is read-only or value out of range.
        """
        self._require_power()
        self._cycle_count += 1
        self._trigger_fault_callbacks("register_write", address)
        self._register_map.write(address, value)

    def read_memory(self, address: int) -> int:
        """Read a byte from SRAM.

        Args:
            address: SRAM address.

        Returns:
            Byte value.

        Raises:
            DeviceNotPoweredError: If chip is not powered.
        """
        self._require_power()
        self._cycle_count += 1
        return self._sram.read(address)

    def write_memory(self, address: int, value: int) -> None:
        """Write a byte to SRAM.

        Args:
            address: SRAM address.
            value: Byte value.

        Raises:
            DeviceNotPoweredError: If chip is not powered.
        """
        self._require_power()
        self._cycle_count += 1
        self._sram.write(address, value)

    def run_memory_tests(self) -> list[MemoryTestResult]:
        """Execute all SRAM tests.

        Raises:
            DeviceNotPoweredError: If chip is not powered.
        """
        self._require_power()
        logger.info("Running all SRAM memory tests.")
        return self._sram.run_all_tests()

    def get_device_id(self) -> int:
        """Return the chip's device ID."""
        return self._register_map.read(0x00)

    def get_firmware_version(self) -> str:
        """Return formatted firmware version string."""
        raw = self._register_map.read(0x0A)
        major = (raw >> 8) & 0xFF
        minor = raw & 0xFF
        return f"{major}.{minor}"

    def get_health_status(self) -> dict[str, object]:
        """Return a health status dictionary for monitoring."""
        return {
            "powered": self._powered,
            "cycle_count": self._cycle_count,
            "chip_version": self.CHIP_VERSION,
            "firmware_version": self.get_firmware_version() if self._powered else "N/A",
            "uptime_seconds": (
                round(time.monotonic() - self._power_on_time, 2)
                if self._power_on_time and self._powered
                else 0.0
            ),
            "sram_size": self._sram.size,
        }

    def get_register_snapshot(self) -> dict[str, int]:
        """Return a snapshot of all register values."""
        return self._register_map.get_snapshot()

    def add_fault_callback(self, callback: Callable[[str, int, int], None]) -> None:
        """Register a fault injection callback invoked on chip operations."""
        self._fault_callbacks.append(callback)

    def _require_power(self) -> None:
        if not self._powered:
            raise DeviceNotPoweredError("Operation requires chip to be powered on.")

    def _trigger_fault_callbacks(self, event: str, address: int) -> None:
        for cb in self._fault_callbacks:
            try:
                cb(event, address, self._cycle_count)
            except Exception as exc:
                logger.debug("Fault callback raised: %s", exc)
                raise
