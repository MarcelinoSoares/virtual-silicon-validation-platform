#!/usr/bin/env python3
"""Run a complete validation flow and save results to the database."""

from __future__ import annotations

import logging
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from virtual_silicon.configuration.settings import get_settings
from virtual_silicon.database.repository import TestRepository
from virtual_silicon.database.session import get_session
from virtual_silicon.device.virtual_chip import VirtualChip
from virtual_silicon.faults.fault_models import load_fault_configs
from virtual_silicon.faults.fault_injector import FaultInjector
from virtual_silicon.instruments.power_supply import PowerSupply
from virtual_silicon.instruments.temperature_sensor import TemperatureSensor
from virtual_silicon.protocols.i2c import I2CBus
from virtual_silicon.protocols.spi import SPIBus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("run_validation")


def main() -> int:
    settings = get_settings()
    eid = str(uuid.uuid4())[:12]
    logger.info("Starting validation run: %s", eid)

    db = get_session(settings.database_url)
    repo = TestRepository(db)
    repo.create_test_run(eid)

    chip = VirtualChip(sram_size=settings.sram_size_bytes, seed=settings.random_seed)
    chip.power_on()

    ps = PowerSupply(voltage=settings.supply_voltage, seed=settings.random_seed)
    ps.power_on()
    ts = TemperatureSensor(ambient_celsius=settings.ambient_temperature, seed=settings.random_seed)

    i2c = I2CBus(chip.register_map, device_address=settings.i2c_device_address, seed=settings.random_seed)
    spi = SPIBus(chip.register_map, clock_hz=settings.spi_clock_hz, seed=settings.random_seed)

    passed = failed = 0

    # Register checks
    if chip.get_device_id() == 0xA5:
        repo.save_test_result(eid, "device_id_check", "register", "PASS", expected="0xA5", actual="0xA5")
        passed += 1
    else:
        repo.save_test_result(eid, "device_id_check", "register", "FAIL")
        failed += 1

    # SRAM tests
    for result in chip.run_memory_tests():
        status = "PASS" if result.passed else "FAIL"
        repo.save_test_result(eid, result.test_name, "memory", status,
                               duration_ms=result.duration * 1000,
                               error_message=result.error_message)
        if result.passed:
            passed += 1
        else:
            failed += 1

    # Measurements
    try:
        v = ps.measure_voltage()
        c = ps.measure_current()
        t = ts.read()
        repo.save_measurement(eid, voltage=v, current=c, temperature=t)
    except Exception as exc:
        logger.warning("Measurement error: %s", exc)

    # I2C write
    txn = i2c.write_register(settings.i2c_device_address, 0x08, 0x80)
    status = "PASS" if txn.success else "FAIL"
    repo.save_test_result(eid, "i2c_register_write", "protocol", status)
    repo.save_protocol_transaction(eid, "I2C", "write", settings.i2c_device_address, 0x08, [0x80], txn.success, txn.error)
    passed += txn.success
    failed += (not txn.success)

    # SPI read
    spi_txn = spi.read_register(0x08)
    status = "PASS" if spi_txn.success else "FAIL"
    repo.save_test_result(eid, "spi_register_read", "protocol", status)
    passed += spi_txn.success
    failed += (not spi_txn.success)

    # Fault injection
    fault_path = Path("configs/faults.yaml")
    if fault_path.exists():
        try:
            fault_cfgs = load_fault_configs(fault_path)
            if fault_cfgs:
                injector = FaultInjector(fault_cfgs, seed=settings.random_seed)
                applied = injector.apply_to_chip(chip, cycle=chip.cycle_count)
                for fid in applied:
                    fc = next((c for c in fault_cfgs if c.fault_id == fid), None)
                    if fc:
                        repo.save_fault_event(eid, fid, fc.fault_type.value, fc.description)
        except Exception as exc:
            logger.warning("Fault injection skipped: %s", exc)

    repo.finish_test_run(eid, passed, failed)
    logger.info("Run %s complete: %d passed, %d failed.", eid, passed, failed)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
