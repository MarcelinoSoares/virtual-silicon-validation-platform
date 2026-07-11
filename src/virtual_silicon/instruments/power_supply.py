"""Virtual power supply simulation with overcurrent and voltage-drop fault injection."""

from __future__ import annotations

import logging
import random

logger = logging.getLogger(__name__)


class InstrumentMeasurementError(Exception):
    """Raised when an instrument measurement fails."""


class PowerSupply:
    """Virtual power supply with configurable voltage, current limiting, and fault simulation.

    Supports voltage/current configuration, power on/off, overcurrent protection,
    voltage drop simulation, and unstable power simulation.
    """

    def __init__(
        self,
        voltage: float = 3.3,
        current_limit: float = 1.0,
        seed: int | None = None,
    ) -> None:
        """Initialize the virtual power supply.

        Args:
            voltage: Target voltage in volts.
            current_limit: Current limit in amperes.
            seed: Random seed for noise simulation.
        """
        self._target_voltage = voltage
        self._current_limit = current_limit
        self._powered = False
        self._voltage_drop: float = 0.0
        self._unstable: bool = False
        self._noise_amplitude: float = 0.01
        self._rng = random.Random(seed)
        self._overcurrent_threshold: float = current_limit
        logger.info("PowerSupply initialized: %.2fV / %.2fA limit.", voltage, current_limit)

    @property
    def target_voltage(self) -> float:
        """Configured target voltage."""
        return self._target_voltage

    @property
    def powered(self) -> bool:
        """True if the supply is outputting power."""
        return self._powered

    def set_voltage(self, voltage: float) -> None:
        """Configure the supply voltage.

        Args:
            voltage: New target voltage in volts.
        """
        if voltage < 0:
            raise InstrumentMeasurementError(f"Voltage must be non-negative, got {voltage}V.")
        self._target_voltage = voltage
        logger.debug("Power supply voltage set to %.3fV.", voltage)

    def set_current_limit(self, limit: float) -> None:
        """Configure the current limit.

        Args:
            limit: Current limit in amperes.
        """
        if limit <= 0:
            raise InstrumentMeasurementError(f"Current limit must be positive, got {limit}A.")
        self._current_limit = limit
        self._overcurrent_threshold = limit

    def power_on(self) -> None:
        """Enable power output."""
        self._powered = True
        logger.info("Power supply ON: %.3fV.", self._target_voltage)

    def power_off(self) -> None:
        """Disable power output."""
        self._powered = False
        logger.info("Power supply OFF.")

    def inject_voltage_drop(self, drop: float) -> None:
        """Inject a persistent voltage drop.

        Args:
            drop: Voltage drop in volts.
        """
        self._voltage_drop = drop
        logger.warning("Voltage drop injected: %.3fV.", drop)

    def inject_unstable_power(self, amplitude: float = 0.1) -> None:
        """Enable unstable power simulation with random noise.

        Args:
            amplitude: Peak noise amplitude in volts.
        """
        self._unstable = True
        self._noise_amplitude = amplitude
        logger.warning("Unstable power injected (amplitude=%.3fV).", amplitude)

    def clear_faults(self) -> None:
        """Clear all injected faults."""
        self._voltage_drop = 0.0
        self._unstable = False
        self._noise_amplitude = 0.01

    def measure_voltage(self) -> float:
        """Measure the current output voltage.

        Returns:
            Measured voltage in volts.

        Raises:
            InstrumentMeasurementError: If supply is not powered.
        """
        if not self._powered:
            raise InstrumentMeasurementError("Cannot measure voltage: power supply is OFF.")
        voltage = self._target_voltage - self._voltage_drop
        if self._unstable:
            voltage += self._rng.uniform(-self._noise_amplitude, self._noise_amplitude)
        return round(max(0.0, voltage), 4)

    def measure_current(self) -> float:
        """Measure the output current with tolerance simulation.

        Returns:
            Measured current in amperes.

        Raises:
            InstrumentMeasurementError: If supply is not powered.
        """
        if not self._powered:
            raise InstrumentMeasurementError("Cannot measure current: power supply is OFF.")
        nominal = self._current_limit * 0.5
        noise = self._rng.uniform(-0.005, 0.005)
        current = max(0.0, nominal + noise)
        if current > self._overcurrent_threshold:
            logger.error(
                "Overcurrent detected! %.3fA > %.3fA limit.", current, self._overcurrent_threshold
            )
            raise InstrumentMeasurementError(
                f"Overcurrent: {current:.3f}A exceeds limit {self._overcurrent_threshold:.3f}A."
            )
        return round(current, 4)
