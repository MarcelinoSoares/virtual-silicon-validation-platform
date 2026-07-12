"""Fault injector: applies configured faults to chip components."""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from virtual_silicon.faults.fault_models import (
    FaultConfig,
    FaultInjectionError,
    FaultModel,
    FaultType,
)

logger = logging.getLogger(__name__)


class FaultApplicationStatus(StrEnum):
    """Outcome category for a single fault application attempt."""

    APPLIED = "applied"
    SKIPPED_DISABLED = "skipped_disabled"
    SKIPPED_CYCLE = "skipped_cycle"
    SKIPPED_PROBABILITY = "skipped_probability"
    SKIPPED_TARGET = "skipped_target"
    FAILED = "failed"


@dataclass
class FaultApplicationResult:
    """Outcome of a single fault application attempt."""

    fault_id: str
    status: FaultApplicationStatus = field(default=FaultApplicationStatus.APPLIED)
    error: str | None = None

    @property
    def applied(self) -> bool:
        """True if and only if the fault was successfully applied."""
        return self.status == FaultApplicationStatus.APPLIED


CHIP_FAULT_TYPES: frozenset[FaultType] = frozenset({
    FaultType.STUCK_BIT,
    FaultType.MEMORY_CORRUPTION,
    FaultType.REGISTER_WRITE_FAILURE,
    FaultType.REGISTER_VALUE_CORRUPTION,
    FaultType.VOLTAGE_DROP,
    FaultType.OVERCURRENT,
    FaultType.OVERHEAT,
})
I2C_FAULT_TYPES: frozenset[FaultType] = frozenset({FaultType.I2C_TIMEOUT, FaultType.I2C_NACK})
SPI_FAULT_TYPES: frozenset[FaultType] = frozenset({FaultType.SPI_TIMEOUT, FaultType.SPI_CORRUPTION})


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

    def _evaluate_trigger(self, model: FaultModel, cycle: int) -> FaultApplicationResult | None:
        """Return a skip result if this fault should not fire this cycle; else None."""
        cfg = model.config
        if not cfg.enabled:
            return FaultApplicationResult(
                fault_id=cfg.fault_id, status=FaultApplicationStatus.SKIPPED_DISABLED
            )
        if cfg.trigger_after_cycles is not None and cycle < cfg.trigger_after_cycles:
            return FaultApplicationResult(
                fault_id=cfg.fault_id, status=FaultApplicationStatus.SKIPPED_CYCLE
            )
        if self._rng.random() > cfg.probability:
            return FaultApplicationResult(
                fault_id=cfg.fault_id, status=FaultApplicationStatus.SKIPPED_PROBABILITY
            )
        return None

    def apply_to_chip(
        self, chip: object, cycle: int = 0, strict: bool = False
    ) -> list[FaultApplicationResult]:
        """Apply all applicable faults to the chip and its components.

        Fault types not in CHIP_FAULT_TYPES (e.g. I2C, SPI) are returned as
        SKIPPED_TARGET so callers know they were seen but not applied.

        Args:
            chip: VirtualChip instance.
            cycle: Current execution cycle count.
            strict: If True, re-raise fault application errors instead of logging warnings.

        Returns:
            List of FaultApplicationResult for each fault configuration.

        Raises:
            FaultInjectionError: If strict=True and a fault fails to apply.
        """
        results: list[FaultApplicationResult] = []
        for model in self._models:
            cfg = model.config
            if cfg.fault_type not in CHIP_FAULT_TYPES:
                results.append(
                    FaultApplicationResult(
                        fault_id=cfg.fault_id,
                        status=FaultApplicationStatus.SKIPPED_TARGET,
                        error="Fault type is not applicable to VirtualChip.",
                    )
                )
                continue
            skip = self._evaluate_trigger(model, cycle)
            if skip is not None:
                results.append(skip)
                continue
            try:
                self._apply_fault(cfg, chip)
                model.active = True
                model.trigger_count += 1
                model.last_triggered_cycle = cycle
                self._active_faults[cfg.fault_id] = cfg
                results.append(
                    FaultApplicationResult(
                        fault_id=cfg.fault_id,
                        status=FaultApplicationStatus.APPLIED,
                    )
                )
                logger.info("Fault applied: %s (%s).", cfg.fault_id, cfg.fault_type.value)
            except Exception as exc:
                error_msg = str(exc)
                results.append(
                    FaultApplicationResult(
                        fault_id=cfg.fault_id,
                        status=FaultApplicationStatus.FAILED,
                        error=error_msg,
                    )
                )
                if strict:
                    raise FaultInjectionError(
                        f"Failed to apply fault '{cfg.fault_id}': {error_msg}"
                    ) from exc
                logger.warning("Failed to apply fault %s: %s", cfg.fault_id, exc)
        return results

    def apply_to_i2c(
        self, i2c: _BusWithFaultProbabilities, cycle: int = 0, strict: bool = False
    ) -> list[FaultApplicationResult]:
        """Apply I2C-specific faults (timeout, NACK).

        Only I2C fault types appear in the result list; chip and SPI faults are
        silently ignored so that a mixed-configuration injector does not pollute
        I2C results with unrelated faults.

        Args:
            i2c: I2CBus instance.
            cycle: Current execution cycle.
            strict: If True, re-raise fault application errors instead of logging warnings.

        Returns:
            List of FaultApplicationResult for each attempted I2C fault.

        Raises:
            FaultInjectionError: If strict=True and a fault fails to apply.
        """
        results: list[FaultApplicationResult] = []
        for model in self._models:
            cfg = model.config
            if cfg.fault_type not in I2C_FAULT_TYPES:
                continue
            skip = self._evaluate_trigger(model, cycle)
            if skip is not None:
                results.append(skip)
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
                results.append(
                    FaultApplicationResult(
                        fault_id=cfg.fault_id,
                        status=FaultApplicationStatus.APPLIED,
                    )
                )
                logger.info("I2C fault applied: %s.", cfg.fault_id)
            except Exception as exc:
                error_msg = str(exc)
                results.append(
                    FaultApplicationResult(
                        fault_id=cfg.fault_id,
                        status=FaultApplicationStatus.FAILED,
                        error=error_msg,
                    )
                )
                if strict:
                    raise FaultInjectionError(
                        f"Failed to apply I2C fault '{cfg.fault_id}': {error_msg}"
                    ) from exc
                logger.warning("Failed to apply I2C fault %s: %s", cfg.fault_id, exc)
        return results

    def apply_to_spi(
        self, spi: _BusWithFaultProbabilities, cycle: int = 0, strict: bool = False
    ) -> list[FaultApplicationResult]:
        """Apply SPI-specific faults (timeout, corruption).

        Only SPI fault types appear in the result list; chip and I2C faults are
        silently ignored so that a mixed-configuration injector does not pollute
        SPI results with unrelated faults.

        Args:
            spi: SPIBus instance.
            cycle: Current execution cycle.
            strict: If True, re-raise fault application errors instead of logging warnings.

        Returns:
            List of FaultApplicationResult for each attempted SPI fault.

        Raises:
            FaultInjectionError: If strict=True and a fault fails to apply.
        """
        results: list[FaultApplicationResult] = []
        for model in self._models:
            cfg = model.config
            if cfg.fault_type not in SPI_FAULT_TYPES:
                continue
            skip = self._evaluate_trigger(model, cycle)
            if skip is not None:
                results.append(skip)
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
                results.append(
                    FaultApplicationResult(
                        fault_id=cfg.fault_id,
                        status=FaultApplicationStatus.APPLIED,
                    )
                )
                logger.info("SPI fault applied: %s.", cfg.fault_id)
            except Exception as exc:
                error_msg = str(exc)
                results.append(
                    FaultApplicationResult(
                        fault_id=cfg.fault_id,
                        status=FaultApplicationStatus.FAILED,
                        error=error_msg,
                    )
                )
                if strict:
                    raise FaultInjectionError(
                        f"Failed to apply SPI fault '{cfg.fault_id}': {error_msg}"
                    ) from exc
                logger.warning("Failed to apply SPI fault %s: %s", cfg.fault_id, exc)
        return results

    def clear_fault_registry(self) -> None:
        """Deactivate all faults and clear active fault registry.

        This clears the administrative state only — it does not undo hardware effects
        (stuck bits, register value changes, fault callbacks, protocol probabilities).
        Use reset_chip_faults(), reset_i2c_faults(), or reset_spi_faults() to reverse effects.
        """
        for model in self._models:
            model.active = False
        self._active_faults.clear()
        logger.info("Fault registry cleared.")

    def reset_chip_faults(self, chip: object) -> None:
        """Remove fault callbacks, clear SRAM stuck bits, and restore all registers to reset values.

        Memory corruption (bytes written directly to SRAM) is not reversed — those writes persist,
        mirroring physical behaviour. To clear the FAULT power state, call recover_from_fault()
        separately.

        Args:
            chip: VirtualChip instance.
        """
        from virtual_silicon.device.virtual_chip import VirtualChip

        if not isinstance(chip, VirtualChip):
            raise FaultInjectionError(f"Expected VirtualChip, got {type(chip).__name__}.")
        chip.clear_fault_callbacks()
        chip.sram.clear_faults()
        chip.register_map.reset_all()
        logger.info(
            "Chip fault effects cleared: callbacks removed, stuck bits cleared, registers reset."
        )

    def reset_i2c_faults(self, i2c: _BusWithFaultProbabilities) -> None:
        """Reset I2C bus fault probabilities to zero.

        Args:
            i2c: I2CBus instance.
        """
        i2c.set_fault_probabilities(timeout=0.0, nack=0.0)
        logger.info("I2C fault probabilities reset.")

    def reset_spi_faults(self, spi: _BusWithFaultProbabilities) -> None:
        """Reset SPI bus fault probabilities to zero.

        Args:
            spi: SPIBus instance.
        """
        spi.set_fault_probabilities(timeout=0.0, corruption=0.0)
        logger.info("SPI fault probabilities reset.")

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
                reg = chip.register_map.get_register(cfg.address)
                if reg.access.value != "ro":
                    chip.register_map.inject_hardware_value(
                        cfg.address, self._rng.randint(0, reg.max_value_mask)
                    )

        elif cfg.fault_type == FaultType.VOLTAGE_DROP:
            voltage = cfg.voltage if cfg.voltage is not None else 0.5
            chip.register_map.inject_hardware_value(0x04, max(0, int(voltage * 1000)) & 0xFFFF)

        elif cfg.fault_type == FaultType.OVERCURRENT:
            chip.fault_shutdown()

        elif cfg.fault_type == FaultType.OVERHEAT:
            temp = cfg.temperature if cfg.temperature is not None else 90
            chip.register_map.inject_hardware_value(0x03, min(255, int(temp)))
