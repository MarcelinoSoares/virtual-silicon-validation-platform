"""VirtualChip: top-level chip simulation integrating registers and SRAM."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from enum import StrEnum
from typing import Literal

from virtual_silicon.device.memory import SRAM, MemoryTestResult
from virtual_silicon.device.register_map import RegisterMap
from virtual_silicon.exceptions import DeviceNotPoweredError

logger = logging.getLogger(__name__)

__all__ = ["DeviceNotPoweredError", "PowerState", "VirtualChip"]


class PowerState(StrEnum):
    """Chip power state machine states.

    Transitions:
        power_on():  OFF → POWER_RAMP → BOOTING → READY
        power_off(): any → OFF
        warm_reset(): READY → BOOTING → READY
        fault_shutdown(): any → FAULT
    """

    OFF = "off"
    POWER_RAMP = "power_ramp"
    BOOTING = "booting"
    READY = "ready"
    FAULT = "fault"


# POWER_CONTROL register bit assignments (address 0x02)
_PWR_BIT_ENABLE = 0x01  # bit 0: 1 = chip enabled, 0 = software power-off
_PWR_BIT_RESET = 0x02   # bit 1: writing 1 triggers warm_reset()


class VirtualChip:
    """Virtual silicon chip simulation integrating RegisterMap and SRAM.

    Provides a unified interface for register access, SRAM operations,
    power management, cycle tracking, fault injection, and health reporting.
    """

    FIRMWARE_MAJOR = 1
    FIRMWARE_MINOR = 0
    CHIP_VERSION = "VS-1000-A"

    def __init__(
        self,
        sram_size: int = 256,
        seed: int | None = None,
        sram_power_on_pattern: Literal["zeroed", "random", "undefined"] = "zeroed",
    ) -> None:
        """Initialize the virtual chip.

        Args:
            sram_size: SRAM size in bytes.
            seed: Random seed for deterministic SRAM tests.
            sram_power_on_pattern: SRAM state after power-on ("zeroed", "random", "undefined").
        """
        self._power_state: PowerState = PowerState.OFF
        self._cycle_count: int = 0
        self._power_on_time: float | None = None
        self._fault_callbacks: list[Callable[[str, int, int], None]] = []
        self._register_map = RegisterMap()
        self._sram = SRAM(
            size=sram_size,
            seed=seed,
            power_on_pattern=sram_power_on_pattern,
            on_access=self._on_sram_access,
        )
        logger.info("VirtualChip initialized. SRAM=%d bytes, seed=%s.", sram_size, seed)

    @property
    def powered(self) -> bool:
        """Return True if the chip is in READY state (backward-compatible)."""
        return self._power_state == PowerState.READY

    @property
    def power_state(self) -> PowerState:
        """Current power state of the chip."""
        return self._power_state

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
        """Power on the chip and initialize registers and SRAM to power-on state."""
        if self._power_state == PowerState.READY:
            logger.warning("Chip is already powered on.")
            return
        self._power_state = PowerState.POWER_RAMP
        self._power_state = PowerState.BOOTING
        self._power_on_time = time.monotonic()
        self._register_map.reset_all()
        self._sram.power_on_init()
        self._cycle_count = 0
        self._power_state = PowerState.READY
        logger.info("Chip powered ON. Registers reset, SRAM initialized.")

    def power_off(self) -> None:
        """Power off the chip."""
        if self._power_state == PowerState.OFF:
            logger.warning("Chip is already powered off.")
            return
        self._power_state = PowerState.OFF
        logger.info("Chip powered OFF after %d cycles.", self._cycle_count)

    def fault_shutdown(self) -> None:
        """Transition to FAULT state (e.g., triggered by overcurrent protection)."""
        self._power_state = PowerState.FAULT
        logger.warning("Chip fault shutdown after %d cycles.", self._cycle_count)

    def warm_reset(self) -> None:
        """Warm reset: restore register defaults and clear SRAM while staying powered.

        Raises:
            DeviceNotPoweredError: If chip is not powered.
        """
        self._require_power()
        self._power_state = PowerState.BOOTING
        self._register_map.reset_all()
        self._sram.clear()
        self._cycle_count = 0
        self._power_state = PowerState.READY
        logger.info("Chip warm reset.")

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
        if address == 0x02:  # POWER_CONTROL side effects
            masked = value & 0x0F  # POWER_CONTROL bit_mask
            if masked & _PWR_BIT_RESET:
                self.warm_reset()
            elif not (masked & _PWR_BIT_ENABLE):
                self.power_off()

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
        self._trigger_fault_callbacks("sram_read", address)
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
        self._trigger_fault_callbacks("sram_write", address)
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
        """Return the chip's device ID.

        Raises:
            DeviceNotPoweredError: If chip is not powered.
        """
        self._require_power()
        self._cycle_count += 1
        self._trigger_fault_callbacks("register_read", 0x00)
        return self._register_map.read(0x00)

    def get_firmware_version(self) -> str:
        """Return formatted firmware version string.

        Raises:
            DeviceNotPoweredError: If chip is not powered.
        """
        self._require_power()
        self._cycle_count += 1
        self._trigger_fault_callbacks("register_read", 0x0A)
        raw = self._register_map.read(0x0A)
        major = (raw >> 8) & 0xFF
        minor = raw & 0xFF
        return f"{major}.{minor}"

    def get_health_status(self) -> dict[str, object]:
        """Return a health status dictionary for monitoring."""
        is_ready = self._power_state == PowerState.READY
        return {
            "powered": is_ready,
            "power_state": self._power_state.value,
            "cycle_count": self._cycle_count,
            "chip_version": self.CHIP_VERSION,
            "firmware_version": (
                f"{self.FIRMWARE_MAJOR}.{self.FIRMWARE_MINOR}" if is_ready else "N/A"
            ),
            "uptime_seconds": (
                round(time.monotonic() - self._power_on_time, 2)
                if self._power_on_time and is_ready
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

    def _on_sram_access(self) -> None:
        self._cycle_count += 1

    def _require_power(self) -> None:
        if self._power_state != PowerState.READY:
            raise DeviceNotPoweredError(
                f"Operation requires chip to be powered on (state: {self._power_state.value})."
            )

    def _trigger_fault_callbacks(self, event: str, address: int) -> None:
        for cb in self._fault_callbacks:
            try:
                cb(event, address, self._cycle_count)
            except Exception as exc:
                logger.debug("Fault callback raised: %s", exc)
                raise
