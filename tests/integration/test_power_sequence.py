"""Integration tests for power supply sequencing with chip."""

import pytest

from virtual_silicon.device.virtual_chip import VirtualChip
from virtual_silicon.instruments.power_supply import InstrumentMeasurementError, PowerSupply


@pytest.mark.integration
class TestPowerSequence:
    def test_nominal_power_up_sequence(self, virtual_chip: VirtualChip, power_supply: PowerSupply) -> None:
        assert virtual_chip.powered
        v = power_supply.measure_voltage()
        assert 3.0 <= v <= 3.6

    def test_voltage_within_tolerance(self, power_supply: PowerSupply) -> None:
        v = power_supply.measure_voltage()
        assert abs(v - 3.3) < 0.2

    def test_voltage_drop_detected(self, power_supply: PowerSupply) -> None:
        power_supply.inject_voltage_drop(0.8)
        v = power_supply.measure_voltage()
        assert v < 3.0

    def test_power_off_prevents_measurement(self, power_supply: PowerSupply) -> None:
        power_supply.power_off()
        with pytest.raises(InstrumentMeasurementError):
            power_supply.measure_voltage()

    def test_current_measurement_nominal(self, power_supply: PowerSupply) -> None:
        c = power_supply.measure_current()
        assert 0.0 < c < power_supply._current_limit

    def test_chip_registers_accessible_at_nominal_power(self, virtual_chip: VirtualChip, power_supply: PowerSupply) -> None:
        v = power_supply.measure_voltage()
        device_id = virtual_chip.read_register(0x00)
        assert device_id == 0xA5
        assert v > 2.5

    def test_power_cycle_resets_chip(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        chip.write_register(0x02, 0x05)
        chip.power_off()
        chip.power_on()
        assert chip.read_register(0x02) == 0x00

    def test_multiple_voltage_readings_consistent(self, power_supply: PowerSupply) -> None:
        readings = [power_supply.measure_voltage() for _ in range(10)]
        assert all(2.9 <= r <= 3.7 for r in readings)
