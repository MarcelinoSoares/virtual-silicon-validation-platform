"""End-to-end system validation test covering the complete chip validation flow."""

from __future__ import annotations

import uuid

import pytest

from virtual_silicon.analytics.analyzer import TestAnalyzer
from virtual_silicon.analytics.report_generator import ReportGenerator
from virtual_silicon.database.repository import TestRepository
from virtual_silicon.device.virtual_chip import VirtualChip
from virtual_silicon.faults.fault_injector import FaultInjector
from virtual_silicon.faults.fault_models import FaultConfig, FaultType
from virtual_silicon.instruments.multimeter import Multimeter
from virtual_silicon.instruments.power_supply import PowerSupply
from virtual_silicon.instruments.spectrometer import Spectrometer
from virtual_silicon.instruments.temperature_sensor import TemperatureSensor
from virtual_silicon.protocols.i2c import I2CBus
from virtual_silicon.protocols.spi import SPIBus


@pytest.mark.system
class TestEndToEndValidation:
    """Full end-to-end silicon validation scenario."""

    def test_complete_chip_validation_flow(
        self,
        tmp_path,
        temp_db: TestRepository,
    ) -> None:
        """Execute the full validation scenario from power-on to report generation."""
        eid = str(uuid.uuid4())[:8]
        seed = 42

        # 1. Create and power on the virtual chip
        chip = VirtualChip(sram_size=256, seed=seed)
        chip.power_on()
        assert chip.powered

        # 2. Create test run in database
        temp_db.create_test_run(eid, firmware_version=chip.get_firmware_version())

        # 3. Validate register reset values
        assert chip.read_register(0x00) == 0xA5, "Device ID mismatch"
        assert chip.read_register(0x02) == 0x00, "POWER_CONTROL not reset"
        assert chip.read_register(0x09) == 0x00, "ERROR_FLAGS not cleared"
        temp_db.save_test_result(eid, "register_reset_validation", "register", "PASS")

        # 4. Verify device ID
        device_id = chip.get_device_id()
        assert device_id == 0xA5
        temp_db.save_test_result(
            eid, "device_id_check", "register", "PASS", expected="0xA5", actual=hex(device_id)
        )

        # 5. Configure power management
        chip.write_register(0x02, 0x01)
        assert chip.read_register(0x02) == 0x01
        temp_db.save_test_result(eid, "power_config", "register", "PASS")

        # 6. Execute SRAM tests
        sram_results = chip.run_memory_tests()
        sram_passed = sum(1 for r in sram_results if r.passed)
        assert sram_passed == len(sram_results), "SRAM tests failed before fault injection"
        for r in sram_results:
            status = "PASS" if r.passed else "FAIL"
            temp_db.save_test_result(
                eid, r.test_name, "memory", status, duration_ms=r.duration * 1000
            )

        # 7. Write register via I2C
        i2c = I2CBus(chip, device_address=0x48, seed=seed)
        txn_write = i2c.write_register(0x48, 0x08, 0x40)
        assert txn_write.success
        temp_db.save_protocol_transaction(
            eid, "I2C", "write", 0x48, 0x08, [0x40], txn_write.success
        )
        temp_db.save_test_result(eid, "i2c_register_write", "protocol", "PASS")

        # 8. Read register via SPI
        spi = SPIBus(chip, seed=seed)
        txn_read = spi.read_register(0x08)
        assert txn_read.success
        assert txn_read.rx_data == [0x40], "SPI read did not match I2C write"
        temp_db.save_protocol_transaction(
            eid, "SPI", "read", 0, 0x08, txn_read.rx_data, txn_read.success
        )
        temp_db.save_test_result(eid, "spi_register_read", "protocol", "PASS")

        # 9. Collect instrument measurements
        ps = PowerSupply(voltage=3.3, current_limit=1.0, seed=seed)
        ps.power_on()
        multimeter = Multimeter(seed=seed)
        ts = TemperatureSensor(seed=seed)
        sp = Spectrometer(seed=seed)

        voltage = multimeter.measure_voltage(ps.measure_voltage())
        current = multimeter.measure_current(ps.measure_current())
        temperature = ts.read()
        brightness = sp.measure_brightness()

        assert 3.0 <= voltage <= 3.6
        assert 0.0 < current < 1.0
        assert 24.0 <= temperature <= 26.5
        assert brightness > 0

        temp_db.save_measurement(
            eid, voltage=voltage, current=current, temperature=temperature, brightness=brightness
        )
        temp_db.save_test_result(eid, "instrument_measurements", "instrument", "PASS")

        # 10. Inject SRAM fault
        fault_cfg = FaultConfig(
            fault_id="SRAM_STUCK_BIT",
            fault_type=FaultType.STUCK_BIT,
            enabled=True,
            address=15,
            bit=3,
            value=1,
            probability=1.0,
        )
        injector = FaultInjector([fault_cfg], seed=seed)
        applied = injector.apply_to_chip(chip, cycle=chip.cycle_count)
        assert "SRAM_STUCK_BIT" in applied
        temp_db.save_fault_event(
            eid, "SRAM_STUCK_BIT", "stuck_bit", "Stuck bit at address 15, bit 3", chip.cycle_count
        )

        # 11. Confirm SRAM detects the fault
        post_fault_results = chip.run_memory_tests()
        failing = [r for r in post_fault_results if not r.passed]
        assert len(failing) > 0, "Fault was not detected by memory tests"
        for r in post_fault_results:
            status = "PASS" if r.passed else "FAIL"
            temp_db.save_test_result(
                eid, f"post_fault_{r.test_name}", "memory", status, error_message=r.error_message
            )
        temp_db.save_test_result(eid, "sram_fault_detection", "fault", "PASS")

        # 12. Inject I2C timeout and confirm it is logged
        i2c_fault = FaultConfig(
            fault_id="I2C_TIMEOUT",
            fault_type=FaultType.I2C_TIMEOUT,
            enabled=True,
            probability=1.0,
        )
        i2c_injector = FaultInjector([i2c_fault], seed=seed)
        i2c_injector.apply_to_i2c(i2c, cycle=chip.cycle_count)
        timeout_txn = i2c.read_register(0x48, 0x00)
        assert not timeout_txn.success, "I2C timeout was not triggered"
        temp_db.save_fault_event(
            eid, "I2C_TIMEOUT", "i2c_timeout", "I2C timeout injected", chip.cycle_count
        )
        temp_db.save_test_result(eid, "i2c_timeout_detection", "fault", "PASS")

        # 13. Finalize run in database
        all_results = temp_db.get_all_results(eid)
        passed_count = sum(1 for r in all_results if r.status == "PASS")
        failed_count = sum(1 for r in all_results if r.status == "FAIL")
        temp_db.finish_test_run(eid, passed_count, failed_count)

        # 14. Generate reports
        measurements = temp_db.get_measurements(eid)
        analyzer = TestAnalyzer(all_results, measurements, [])
        summary = analyzer.summarize(eid)
        assert summary.total_tests > 0
        assert summary.pass_rate > 0

        generator = ReportGenerator(output_dir=str(tmp_path))
        paths = generator.generate_all(summary, all_results, measurements)
        assert paths["html"].exists()
        assert paths["csv"].exists()
        assert paths["json"].exists()

        # 15. Reset the chip
        chip.reset()
        chip.power_on()
        assert chip.read_register(0x02) == 0x00

        # 16. Verify final device state
        final_device_id = chip.read_register(0x00)
        assert final_device_id == 0xA5, "Device ID mismatch after reset"
        assert chip.get_firmware_version() == "1.0"
        assert chip.cycle_count == 2  # read_register(0x02) + read_register(0x00) after power_on

        print(f"\nE2E Validation Complete: {summary.passed} passed, {summary.failed} failed")
