"""Integration tests for the full validation flow combining chip, protocols, and instruments."""

import pytest

from virtual_silicon.database.repository import TestRepository
from virtual_silicon.device.virtual_chip import VirtualChip
from virtual_silicon.faults.fault_injector import FaultInjector
from virtual_silicon.faults.fault_models import FaultConfig, FaultType
from virtual_silicon.instruments.power_supply import PowerSupply
from virtual_silicon.protocols.i2c import I2CBus
from virtual_silicon.protocols.spi import SPIBus


@pytest.mark.integration
class TestFullValidationFlow:
    def test_i2c_writes_reflected_in_chip(self, virtual_chip: VirtualChip) -> None:
        i2c = I2CBus(virtual_chip.register_map, device_address=0x48, seed=42)
        txn = i2c.write_register(0x48, 0x02, 0x03)
        assert txn.success
        assert virtual_chip.read_register(0x02) == 0x03

    def test_spi_reads_chip_registers(self, virtual_chip: VirtualChip) -> None:
        spi = SPIBus(virtual_chip.register_map, seed=42)
        txn = spi.read_register(0x00)
        assert txn.success
        assert txn.rx_data == [0xA5]

    def test_i2c_and_spi_interoperability(self, virtual_chip: VirtualChip) -> None:
        i2c = I2CBus(virtual_chip.register_map, device_address=0x48, seed=42)
        spi = SPIBus(virtual_chip.register_map, seed=42)
        i2c.write_register(0x48, 0x08, 0x40)
        txn = spi.read_register(0x08)
        assert txn.success
        assert txn.rx_data == [0x40]

    def test_memory_test_results_saved_to_db(
        self, virtual_chip: VirtualChip, temp_db: TestRepository
    ) -> None:
        eid = "test-flow-001"
        temp_db.create_test_run(eid)
        results = virtual_chip.run_memory_tests()
        for r in results:
            temp_db.save_test_result(
                eid,
                r.test_name,
                "memory",
                "PASS" if r.passed else "FAIL",
                duration_ms=r.duration * 1000,
            )
        temp_db.finish_test_run(
            eid, sum(1 for r in results if r.passed), sum(1 for r in results if not r.passed)
        )
        saved = temp_db.get_all_results(eid)
        assert len(saved) == len(results)

    def test_fault_injection_causes_memory_test_failure(self, virtual_chip: VirtualChip) -> None:
        cfg = FaultConfig(
            fault_id="SRAM_FAULT",
            fault_type=FaultType.STUCK_BIT,
            enabled=True,
            address=0,
            bit=0,
            value=1,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        injector.apply_to_chip(virtual_chip, cycle=0)
        results = virtual_chip.run_memory_tests()
        assert any(not r.passed for r in results)

    def test_measurements_stored_in_db(
        self, virtual_chip: VirtualChip, temp_db: TestRepository, power_supply: PowerSupply
    ) -> None:
        eid = "test-meas-001"
        temp_db.create_test_run(eid)
        v = power_supply.measure_voltage()
        c = power_supply.measure_current()
        temp_db.save_measurement(eid, voltage=v, current=c, temperature=25.0)
        measurements = temp_db.get_measurements(eid)
        assert len(measurements) == 1
        assert measurements[0].voltage is not None

    def test_protocol_transaction_logged_to_db(
        self, virtual_chip: VirtualChip, temp_db: TestRepository
    ) -> None:
        eid = "test-proto-001"
        temp_db.create_test_run(eid)
        temp_db.save_protocol_transaction(eid, "I2C", "read", 0x48, 0x00, [0xA5], True)
        # Just verify no exception — transaction logging is fire-and-forget

    def test_i2c_timeout_logged_and_detected(self, virtual_chip: VirtualChip) -> None:
        i2c = I2CBus(virtual_chip.register_map, device_address=0x48, seed=42)
        i2c.set_fault_probabilities(timeout=1.0)
        txn = i2c.read_register(0x48, 0x00)
        assert not txn.success
        logs = [log for log in i2c.transactions if not log.success]
        assert len(logs) == 1

    def test_chip_cycles_increment_with_operations(self, virtual_chip: VirtualChip) -> None:
        initial = virtual_chip.cycle_count
        virtual_chip.read_register(0x00)
        virtual_chip.write_register(0x02, 0x01)
        assert virtual_chip.cycle_count == initial + 2
