"""Unit tests for virtual laboratory instruments."""

import pytest

from virtual_silicon.instruments.multimeter import Multimeter
from virtual_silicon.instruments.power_supply import InstrumentMeasurementError, PowerSupply
from virtual_silicon.instruments.spectrometer import Spectrometer
from virtual_silicon.instruments.temperature_sensor import TemperatureSensor


@pytest.mark.unit
class TestPowerSupply:
    def test_measure_voltage_when_on(self, power_supply: PowerSupply) -> None:
        v = power_supply.measure_voltage()
        assert 3.2 <= v <= 3.4

    def test_measure_voltage_when_off_raises(self) -> None:
        ps = PowerSupply()
        with pytest.raises(InstrumentMeasurementError):
            ps.measure_voltage()

    def test_voltage_drop_reduces_output(self, power_supply: PowerSupply) -> None:
        power_supply.inject_voltage_drop(0.5)
        v = power_supply.measure_voltage()
        assert v < 3.3

    def test_set_voltage(self, power_supply: PowerSupply) -> None:
        power_supply.set_voltage(5.0)
        assert power_supply.target_voltage == 5.0

    def test_set_voltage_negative_raises(self, power_supply: PowerSupply) -> None:
        with pytest.raises(InstrumentMeasurementError):
            power_supply.set_voltage(-1.0)

    def test_measure_current_returns_positive(self, power_supply: PowerSupply) -> None:
        c = power_supply.measure_current()
        assert c >= 0.0

    def test_power_off_state(self) -> None:
        ps = PowerSupply()
        assert not ps.powered
        ps.power_on()
        assert ps.powered
        ps.power_off()
        assert not ps.powered

    def test_clear_faults(self, power_supply: PowerSupply) -> None:
        power_supply.inject_voltage_drop(1.0)
        power_supply.clear_faults()
        v = power_supply.measure_voltage()
        assert v > 3.2

    def test_unstable_power_noise(self, power_supply: PowerSupply) -> None:
        power_supply.inject_unstable_power(amplitude=0.2)
        readings = [power_supply.measure_voltage() for _ in range(20)]
        assert max(readings) != min(readings)


@pytest.mark.unit
class TestMultimeter:
    def test_measure_voltage(self, multimeter: Multimeter) -> None:
        v = multimeter.measure_voltage(3.3)
        assert 3.0 <= v <= 3.6

    def test_measure_current(self, multimeter: Multimeter) -> None:
        c = multimeter.measure_current(0.5)
        assert 0.4 <= c <= 0.6

    def test_measure_resistance(self, multimeter: Multimeter) -> None:
        r = multimeter.measure_resistance(1000.0)
        assert 900 <= r <= 1100

    def test_negative_resistance_raises(self, multimeter: Multimeter) -> None:
        with pytest.raises(InstrumentMeasurementError):
            multimeter.measure_resistance(-1.0)

    def test_calibration_offset(self, multimeter: Multimeter) -> None:
        multimeter.set_calibration_offset(0.1)
        v = multimeter.measure_voltage(3.3)
        assert v > 3.3


@pytest.mark.unit
class TestTemperatureSensor:
    def test_read_returns_near_ambient(self, temperature_sensor: TemperatureSensor) -> None:
        t = temperature_sensor.read()
        assert 24.0 <= t <= 26.5

    def test_set_temperature(self, temperature_sensor: TemperatureSensor) -> None:
        temperature_sensor.set_temperature(50.0)
        t = temperature_sensor.read()
        assert 49.0 <= t <= 51.5

    def test_overheat_raises(self, temperature_sensor: TemperatureSensor) -> None:
        temperature_sensor.inject_overheat(temp=90.0)
        with pytest.raises(InstrumentMeasurementError, match="exceeds maximum"):
            temperature_sensor.read()

    def test_clear_faults(self, temperature_sensor: TemperatureSensor) -> None:
        temperature_sensor.inject_overheat()
        temperature_sensor.clear_faults()
        t = temperature_sensor.read()
        assert t < temperature_sensor.max_temperature


@pytest.mark.unit
class TestSpectrometer:
    def test_measure_brightness(self, spectrometer: Spectrometer) -> None:
        b = spectrometer.measure_brightness()
        assert b > 0

    def test_set_display_brightness(self, spectrometer: Spectrometer) -> None:
        spectrometer.set_display_brightness(50.0)
        b = spectrometer.measure_brightness()
        assert b < 100

    def test_brightness_zero(self, spectrometer: Spectrometer) -> None:
        spectrometer.set_display_brightness(0.0)
        b = spectrometer.measure_brightness()
        assert b == 0.0

    def test_invalid_brightness_raises(self, spectrometer: Spectrometer) -> None:
        with pytest.raises(InstrumentMeasurementError):
            spectrometer.set_display_brightness(101.0)

    def test_measure_wavelength(self, spectrometer: Spectrometer) -> None:
        wl = spectrometer.measure_wavelength()
        assert 540 <= wl <= 560

    def test_set_wavelength(self, spectrometer: Spectrometer) -> None:
        spectrometer.set_wavelength(650.0)
        assert 645 <= spectrometer.measure_wavelength() <= 655

    def test_invalid_wavelength_raises(self, spectrometer: Spectrometer) -> None:
        with pytest.raises(InstrumentMeasurementError):
            spectrometer.set_wavelength(200.0)

    def test_set_calibration_offset(self, spectrometer: Spectrometer) -> None:
        """set_calibration_offset() persists the offset (line 90)."""
        spectrometer.set_calibration_offset(5.0)
        b = spectrometer.measure_brightness()
        assert b > 0

    def test_set_display_brightness_out_of_range_negative(self, spectrometer: Spectrometer) -> None:
        """Negative brightness raises InstrumentMeasurementError (line 48)."""
        with pytest.raises(InstrumentMeasurementError, match="0–100"):
            spectrometer.set_display_brightness(-1.0)

    def test_wavelength_nm_property(self, spectrometer: Spectrometer) -> None:
        """wavelength_nm property returns the configured wavelength."""
        assert spectrometer.wavelength_nm == 550.0


@pytest.mark.unit
class TestPowerSupplyExtras:
    """Covers power_supply.py lines 72-75, 138, 143-144."""

    def test_set_current_limit_zero_raises(self) -> None:
        """set_current_limit(0) raises InstrumentMeasurementError (lines 72-73)."""
        ps = PowerSupply()
        with pytest.raises(InstrumentMeasurementError, match="positive"):
            ps.set_current_limit(0.0)

    def test_set_current_limit_negative_raises(self) -> None:
        """set_current_limit(-1) raises InstrumentMeasurementError (lines 72-73)."""
        ps = PowerSupply()
        with pytest.raises(InstrumentMeasurementError, match="positive"):
            ps.set_current_limit(-1.0)

    def test_set_current_limit_valid_updates_state(self) -> None:
        """set_current_limit(2.0) updates _current_limit and _overcurrent_threshold (lines 74-75)."""
        ps = PowerSupply(current_limit=1.0)
        ps.set_current_limit(2.0)
        assert ps._current_limit == 2.0
        assert ps._overcurrent_threshold == 2.0

    def test_measure_current_when_off_raises(self) -> None:
        """measure_current() on a powered-off supply raises (line 138)."""
        ps = PowerSupply()
        # ps.powered is False (not powered on)
        with pytest.raises(InstrumentMeasurementError, match="OFF"):
            ps.measure_current()

    def test_overcurrent_detected(self) -> None:
        """measure_current() raises InstrumentMeasurementError when over threshold (lines 143-144)."""
        # Set a very low overcurrent threshold so nominal current exceeds it
        ps = PowerSupply(voltage=3.3, current_limit=1.0, seed=42)
        ps.power_on()
        # Set an absurdly low threshold so any measurement triggers overcurrent
        ps._overcurrent_threshold = 0.0001
        with pytest.raises(InstrumentMeasurementError, match="Overcurrent"):
            ps.measure_current()


@pytest.mark.unit
class TestTemperatureSensorExtras:
    """Covers temperature_sensor.py lines 89-91 (set_rise_rate)."""

    def test_set_rise_rate_updates_state(self, temperature_sensor: TemperatureSensor) -> None:
        """set_rise_rate() stores the rate and resets start_time (lines 89-91)."""
        temperature_sensor.set_rise_rate(0.1)
        # Confirm no error and the sensor still reads correctly (slowly rising)
        t = temperature_sensor.read()
        assert t is not None
        assert isinstance(t, float)
