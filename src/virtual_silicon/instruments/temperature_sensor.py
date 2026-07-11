"""Virtual temperature sensor with thermal drift and overheating simulation."""

from __future__ import annotations

import logging
import random
import time

from virtual_silicon.instruments.power_supply import InstrumentMeasurementError

logger = logging.getLogger(__name__)


class TemperatureSensor:
    """Virtual temperature sensor with configurable limits, thermal rise, and noise.

    Simulates current temperature, gradual thermal increase, overheating injection,
    and configurable min/max thresholds.
    """

    def __init__(
        self,
        ambient_celsius: float = 25.0,
        max_celsius: float = 85.0,
        noise_amplitude: float = 0.5,
        seed: int | None = None,
    ) -> None:
        """Initialize the temperature sensor.

        Args:
            ambient_celsius: Starting ambient temperature in °C.
            max_celsius: Maximum safe operating temperature.
            noise_amplitude: Random noise amplitude in °C.
            seed: Random seed for noise.
        """
        self._ambient = ambient_celsius
        self._current = ambient_celsius
        self._max_celsius = max_celsius
        self._noise_amplitude = noise_amplitude
        self._rng = random.Random(seed)
        self._overheating: bool = False
        self._overheat_temp: float = max_celsius + 10.0
        self._start_time: float = time.monotonic()
        self._rise_rate: float = 0.0
        logger.debug("TemperatureSensor initialized at %.1f°C.", ambient_celsius)

    @property
    def max_temperature(self) -> float:
        """Maximum safe temperature threshold."""
        return self._max_celsius

    def read(self) -> float:
        """Read the current temperature.

        Returns:
            Temperature in degrees Celsius with simulated noise.

        Raises:
            InstrumentMeasurementError: If temperature exceeds maximum safe limit.
        """
        elapsed = time.monotonic() - self._start_time
        temp = self._current + (self._rise_rate * elapsed)
        if self._overheating:
            temp = self._overheat_temp
        noise = self._rng.uniform(-self._noise_amplitude, self._noise_amplitude)
        measured = round(temp + noise, 2)
        if measured > self._max_celsius:
            logger.error("Overheating: %.2f°C > %.2f°C limit.", measured, self._max_celsius)
            raise InstrumentMeasurementError(
                f"Temperature {measured:.2f}°C exceeds maximum {self._max_celsius:.2f}°C."
            )
        return measured

    def set_temperature(self, celsius: float) -> None:
        """Manually set the current base temperature.

        Args:
            celsius: Temperature in degrees Celsius.
        """
        self._current = celsius
        self._start_time = time.monotonic()

    def set_rise_rate(self, degrees_per_second: float) -> None:
        """Configure thermal rise rate.

        Args:
            degrees_per_second: Temperature increase per second.
        """
        self._rise_rate = degrees_per_second
        self._start_time = time.monotonic()
        self._current = self._current

    def inject_overheat(self, temp: float | None = None) -> None:
        """Inject an overheating condition.

        Args:
            temp: Temperature to inject (default: max + 10°C).
        """
        self._overheating = True
        if temp is not None:
            self._overheat_temp = temp
        logger.warning("Overheating injected: %.1f°C.", self._overheat_temp)

    def clear_faults(self) -> None:
        """Clear all injected faults and reset to ambient."""
        self._overheating = False
        self._rise_rate = 0.0
        self._current = self._ambient
        self._start_time = time.monotonic()
