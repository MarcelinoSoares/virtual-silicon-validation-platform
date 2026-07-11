"""Fault injector: applies configured faults to chip components."""

from __future__ import annotations

import logging
import random
from typing import Protocol

from virtual_silicon.faults.fault_models import (
    FaultConfig,
    FaultInjectionError,
    FaultModel,
    FaultType,
)

logger = logging.getLogger(__name__)


class _BusWithFaultProbabilities(Protocol):
    def set_fault_probabilities(self, **kwargs: float) -> None: ...


class FaultInjector:
    """Applies fault configurations to virtual chip components.

    Supports SRAM stuck bits, memory corruption, register faults,
    voltage/current/temperature faults, and protocol faults.
    Respects cycle-based triggers and probabilistic injection.
    """

    def __init__(self, configs: list[FaultConfig], seed: int | None = None) -> None:
        """Initialize the fault injector with a list of configurations.

        Args:
            configs: List of fault configurations.
            seed: Random seed for probabilistic faults.
        """
        self._models: list[FaultModel] = [FaultModel(config=c) for c in configs]
        self._rng = random.Random(seed)
        self._active_faults: dict[str, FaultConfig] = {}
        logger.info("FaultInjector initialized with %d fault(s).", len(self._models))

    @property
    def models(self) -> list[FaultModel]:
        """List of all fault models."""
        return list(self._models)

    @property
    def active_faults(self) -> dict[str, FaultConfig]:
        """Currently active faults by fault_id."""
        return dict(self._active_faults)

    def apply_to_chip(self, chip: object, cycle: int = 0) -> list[str]:
        """Apply all applicable faults to the chip and its components.

        Args:
            chip: VirtualChip instance.
            cycle: Current execution cycle count.

        Returns:
            List of fault IDs that were applied this call.
        """
        applied: list[str] = []
        for model in self._models:
            cfg = model.config
            if not cfg.enabled:
                continue
            if cfg.trigger_after_cycles is not None and cycle < cfg.trigger_after_cycles:
                continue
            if self._rng.random() > cfg.probability:
                continue
            try:
                self._apply_fault(cfg, chip)
                model.active = True
                model.trigger_count += 1
                model.last_triggered_cycle = cycle
                self._active_faults[cfg.fault_id] = cfg
                applied.append(cfg.fault_id)
                logger.info("Fault applied: %s (%s).", cfg.fault_id, cfg.fault_type.value)
            except Exception as exc:
                logger.warning("Failed to apply fault %s: %s", cfg.fault_id, exc)
        return applied

    def apply_to_i2c(self, i2c: _BusWithFaultProbabilities, cycle: int = 0) -> list[str]:
        """Apply I2C-specific faults (timeout, NACK).

        Args:
            i2c: I2CBus instance.
            cycle: Current execution cycle.

        Returns:
            List of applied fault IDs.
        """
        applied: list[str] = []
        for model in self._models:
            cfg = model.config
            if not cfg.enabled:
                continue
            if cfg.fault_type not in (FaultType.I2C_TIMEOUT, FaultType.I2C_NACK):
                continue
            if cfg.trigger_after_cycles is not None and cycle < cfg.trigger_after_cycles:
                continue
            if self._rng.random() > cfg.probability:
                continue
            try:
                if cfg.fault_type == FaultType.I2C_TIMEOUT:
                    i2c.set_fault_probabilities(timeout=1.0)
                elif cfg.fault_type == FaultType.I2C_NACK:
                    i2c.set_fault_probabilities(nack=1.0)
                model.active = True
                model.trigger_count += 1
                model.last_triggered_cycle = cycle
                self._active_faults[cfg.fault_id] = cfg
                applied.append(cfg.fault_id)
                logger.info("I2C fault applied: %s.", cfg.fault_id)
            except Exception as exc:
                logger.warning("Failed to apply I2C fault %s: %s", cfg.fault_id, exc)
        return applied

    def apply_to_spi(self, spi: _BusWithFaultProbabilities, cycle: int = 0) -> list[str]:
        """Apply SPI-specific faults (timeout, corruption).

        Args:
            spi: SPIBus instance.
            cycle: Current execution cycle.

        Returns:
            List of applied fault IDs.
        """
        applied: list[str] = []
        for model in self._models:
            cfg = model.config
            if not cfg.enabled:
                continue
            if cfg.fault_type not in (FaultType.SPI_TIMEOUT, FaultType.SPI_CORRUPTION):
                continue
            if cfg.trigger_after_cycles is not None and cycle < cfg.trigger_after_cycles:
                continue
            if self._rng.random() > cfg.probability:
                continue
            try:
                if cfg.fault_type == FaultType.SPI_TIMEOUT:
                    spi.set_fault_probabilities(timeout=1.0)
                elif cfg.fault_type == FaultType.SPI_CORRUPTION:
                    spi.set_fault_probabilities(corruption=1.0)
                model.active = True
                model.trigger_count += 1
                model.last_triggered_cycle = cycle
                self._active_faults[cfg.fault_id] = cfg
                applied.append(cfg.fault_id)
                logger.info("SPI fault applied: %s.", cfg.fault_id)
            except Exception as exc:
                logger.warning("Failed to apply SPI fault %s: %s", cfg.fault_id, exc)
        return applied

    def clear_all(self) -> None:
        """Deactivate all faults and clear active fault registry."""
        for model in self._models:
            model.active = False
        self._active_faults.clear()
        logger.info("All faults cleared.")

    def _apply_fault(self, cfg: FaultConfig, chip: object) -> None:
        """Dispatch fault application based on fault type."""
        from virtual_silicon.device.virtual_chip import VirtualChip  # avoid circular import

        if not isinstance(chip, VirtualChip):
            raise FaultInjectionError(f"Expected VirtualChip, got {type(chip).__name__}.")

        if cfg.fault_type == FaultType.STUCK_BIT:
            if cfg.address is None or cfg.bit is None or cfg.value is None:
                raise FaultInjectionError("STUCK_BIT requires address, bit, and value.")
            chip.sram.inject_stuck_bit(cfg.address, cfg.bit, cfg.value)

        elif cfg.fault_type == FaultType.MEMORY_CORRUPTION:
            if cfg.address is None:
                raise FaultInjectionError("MEMORY_CORRUPTION requires address.")
            corrupted = self._rng.randint(0, 0xFF)
            chip.sram.write(cfg.address, corrupted)

        elif cfg.fault_type == FaultType.REGISTER_WRITE_FAILURE:

            def write_fault_callback(event: str, address: int, cycle_count: int) -> None:
                if event == "register_write" and cfg.address is not None and address == cfg.address:
                    raise FaultInjectionError(
                        f"Register write failure injected at 0x{address:04X}."
                    )

            chip.add_fault_callback(write_fault_callback)

        elif cfg.fault_type == FaultType.REGISTER_VALUE_CORRUPTION:
            if cfg.address is not None:
                reg = chip.register_map._get_register(cfg.address)
                if reg.access.value != "ro":
                    reg._value = self._rng.randint(0, reg._max_bits)

        elif cfg.fault_type == FaultType.VOLTAGE_DROP:
            voltage = cfg.voltage if cfg.voltage is not None else 0.5
            # VOLTAGE_LEVEL (0x04) is READ_ONLY — bypass access control to simulate
            # the hardware dropping voltage (analogous to OVERHEAT injecting temperature)
            chip.register_map._registers[0x04]._value = max(0, int(voltage * 1000)) & 0xFFFF

        elif cfg.fault_type == FaultType.OVERCURRENT:
            # Simulate overcurrent protection: latch the chip into FAULT state
            chip.fault_shutdown()

        elif cfg.fault_type == FaultType.OVERHEAT:
            temp = cfg.temperature if cfg.temperature is not None else 90
            chip.register_map._registers[0x03]._value = min(255, int(temp))

        else:
            logger.debug("Fault type %s has no chip-level action.", cfg.fault_type.value)
