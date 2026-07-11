"""Virtual multimeter simulation with voltage, current, and resistance measurements."""

from __future__ import annotations

import logging
import random

from virtual_silicon.instruments.power_supply import InstrumentMeasurementError

logger = logging.getLogger(__name__)


class Multimeter:
    """Virtual multimeter with configurable noise, tolerance, and calibration offset.

    Supports voltage, current, and resistance measurement simulation.
    """

    def __init__(
        self,
        tolerance: float = 0.02,
        calibration_offset: float = 0.0,
        seed: int | None = None,
    ) -> None:
        """Initialize the multimeter.

        Args:
            tolerance: Relative measurement tolerance (e.g. 0.02 = ±2%).
            calibration_offset: Fixed calibration offset added to measurements.
            seed: Random seed for noise.
        """
        self._tolerance = tolerance
        self._calibration_offset = calibration_offset
        self._rng = random.Random(seed)
        logger.debug("Multimeter initialized. Tolerance=±%.1f%%.", tolerance * 100)

    def measure_voltage(self, true_voltage: float) -> float:
        """Measure voltage with noise and calibration offset applied.

        Args:
            true_voltage: True voltage value in volts.

        Returns:
            Measured voltage with simulated error.
        """
        noise = self._rng.uniform(-self._tolerance, self._tolerance) * abs(true_voltage)
        return round(true_voltage + noise + self._calibration_offset, 4)

    def measure_current(self, true_current: float) -> float:
        """Measure current with noise and calibration offset applied.

        Args:
            true_current: True current value in amperes.

        Returns:
            Measured current with simulated error.
        """
        noise = self._rng.uniform(-self._tolerance, self._tolerance) * abs(true_current)
        return round(max(0.0, true_current + noise + self._calibration_offset), 4)

    def measure_resistance(self, true_resistance: float) -> float:
        """Simulate resistance measurement.

        Args:
            true_resistance: True resistance in ohms.

        Returns:
            Measured resistance with simulated error.

        Raises:
            InstrumentMeasurementError: If true_resistance is negative.
        """
        if true_resistance < 0:
            raise InstrumentMeasurementError(f"Resistance cannot be negative: {true_resistance}Ω.")
        noise = self._rng.uniform(-self._tolerance, self._tolerance) * true_resistance
        return round(max(0.0, true_resistance + noise), 4)

    def set_calibration_offset(self, offset: float) -> None:
        """Set the calibration offset.

        Args:
            offset: New calibration offset.
        """
        self._calibration_offset = offset
        logger.debug("Multimeter calibration offset set to %.4f.", offset)
