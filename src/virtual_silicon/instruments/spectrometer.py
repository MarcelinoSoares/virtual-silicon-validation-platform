"""Virtual spectrometer / brightness sensor simulation."""

from __future__ import annotations

import logging
import random

from virtual_silicon.instruments.power_supply import InstrumentMeasurementError

logger = logging.getLogger(__name__)


class Spectrometer:
    """Virtual spectrometer and brightness sensor.

    Simulates optical brightness measurement, wavelength simulation,
    configurable display brightness level, measurement tolerance, and calibration.
    """

    def __init__(
        self,
        base_brightness: float = 100.0,
        wavelength_nm: float = 550.0,
        tolerance: float = 0.03,
        calibration_offset: float = 0.0,
        seed: int | None = None,
    ) -> None:
        """Initialize the spectrometer.

        Args:
            base_brightness: Nominal brightness in arbitrary luminance units.
            wavelength_nm: Nominal wavelength in nanometers.
            tolerance: Relative measurement tolerance.
            calibration_offset: Fixed calibration offset for brightness.
            seed: Random seed for measurement noise.
        """
        self._base_brightness = base_brightness
        self._wavelength_nm = wavelength_nm
        self._tolerance = tolerance
        self._calibration_offset = calibration_offset
        self._rng = random.Random(seed)
        self._display_brightness_pct: float = 100.0
        logger.debug("Spectrometer initialized: %.1f lu @ %.1f nm.", base_brightness, wavelength_nm)

    @property
    def wavelength_nm(self) -> float:
        """Configured peak wavelength in nanometers."""
        return self._wavelength_nm

    def set_display_brightness(self, percent: float) -> None:
        """Configure the virtual display brightness percentage.

        Args:
            percent: Brightness level 0–100%.

        Raises:
            InstrumentMeasurementError: If percent is out of range.
        """
        if not 0.0 <= percent <= 100.0:
            raise InstrumentMeasurementError(f"Brightness percentage must be 0–100, got {percent}.")
        self._display_brightness_pct = percent

    def measure_brightness(self) -> float:
        """Measure optical brightness.

        Returns:
            Measured brightness in luminance units with noise and calibration applied.
        """
        effective = self._base_brightness * (self._display_brightness_pct / 100.0)
        noise = self._rng.uniform(-self._tolerance, self._tolerance) * effective
        return round(max(0.0, effective + noise + self._calibration_offset), 3)

    def measure_wavelength(self) -> float:
        """Measure the peak wavelength with small noise.

        Returns:
            Wavelength in nanometers with simulated noise.
        """
        noise = self._rng.uniform(-2.0, 2.0)
        return round(self._wavelength_nm + noise, 2)

    def set_calibration_offset(self, offset: float) -> None:
        """Set the calibration offset.

        Args:
            offset: New calibration offset.
        """
        self._calibration_offset = offset

    def set_wavelength(self, wavelength_nm: float) -> None:
        """Set the peak wavelength.

        Args:
            wavelength_nm: Wavelength in nanometers.

        Raises:
            InstrumentMeasurementError: If wavelength is outside 300–1100 nm visible range.
        """
        if not 300.0 <= wavelength_nm <= 1100.0:
            raise InstrumentMeasurementError(
                f"Wavelength {wavelength_nm}nm outside supported range 300–1100nm."
            )
        self._wavelength_nm = wavelength_nm
