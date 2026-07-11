#!/usr/bin/env python3
"""Seed the database with sample test run data for development and demos."""

from __future__ import annotations

import sys
import uuid
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from virtual_silicon.configuration.settings import get_settings
from virtual_silicon.database.repository import TestRepository
from virtual_silicon.database.session import get_session


def main() -> int:
    settings = get_settings()
    db = get_session(settings.database_url)
    repo = TestRepository(db)

    rng = random.Random(42)
    test_names = [
        "device_id_check", "register_reset_validation", "walking_ones",
        "walking_zeros", "checkerboard", "inverse_checkerboard",
        "address_pattern", "random_readwrite", "march_c_minus",
        "boundary_addresses", "data_retention", "i2c_register_write",
        "spi_register_read", "power_config",
    ]
    categories = {
        "device_id_check": "register", "register_reset_validation": "register",
        "walking_ones": "memory", "walking_zeros": "memory", "checkerboard": "memory",
        "inverse_checkerboard": "memory", "address_pattern": "memory",
        "random_readwrite": "memory", "march_c_minus": "memory",
        "boundary_addresses": "memory", "data_retention": "memory",
        "i2c_register_write": "protocol", "spi_register_read": "protocol",
        "power_config": "register",
    }

    for run_num in range(3):
        eid = f"seed-run-{run_num:03d}-{str(uuid.uuid4())[:4]}"
        repo.create_test_run(eid, firmware_version="1.0", chip_version="VS-1000-A")
        passed = failed = 0
        for test_name in test_names:
            ok = rng.random() > 0.1
            status = "PASS" if ok else "FAIL"
            repo.save_test_result(
                eid, test_name, categories[test_name], status,
                duration_ms=rng.uniform(0.5, 50.0),
                error_message="" if ok else "Simulated failure.",
            )
            if ok:
                passed += 1
            else:
                failed += 1
        for _ in range(10):
            repo.save_measurement(
                eid,
                voltage=rng.uniform(3.1, 3.5),
                current=rng.uniform(0.4, 0.6),
                temperature=rng.uniform(24.0, 30.0),
                brightness=rng.uniform(90, 110),
            )
        repo.finish_test_run(eid, passed, failed)
        print(f"Seeded run {eid}: {passed} passed, {failed} failed.")

    print("Database seeded successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
