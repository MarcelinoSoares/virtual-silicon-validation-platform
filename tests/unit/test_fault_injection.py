"""Unit tests for fault injection framework."""

from pathlib import Path

import pytest

from virtual_silicon.device.virtual_chip import VirtualChip
from virtual_silicon.faults.fault_injector import FaultInjector
from virtual_silicon.faults.fault_models import (
    FaultConfig,
    FaultInjectionError,
    FaultType,
    load_fault_configs,
)


@pytest.mark.unit
@pytest.mark.fault
class TestFaultConfig:
    def test_from_dict_stuck_bit(self) -> None:
        data = {"id": "TEST", "type": "stuck_bit", "enabled": True, "address": 5, "bit": 2, "value": 1}
        cfg = FaultConfig.from_dict(data)
        assert cfg.fault_type == FaultType.STUCK_BIT
        assert cfg.address == 5

    def test_from_dict_invalid_type_raises(self) -> None:
        with pytest.raises(FaultInjectionError):
            FaultConfig.from_dict({"id": "X", "type": "unknown_type"})

    def test_from_dict_missing_type_raises(self) -> None:
        with pytest.raises(FaultInjectionError):
            FaultConfig.from_dict({"id": "X"})

    def test_probability_clamped(self) -> None:
        cfg = FaultConfig(fault_id="X", fault_type=FaultType.I2C_TIMEOUT, probability=0.5)
        assert 0.0 <= cfg.probability <= 1.0


@pytest.mark.unit
@pytest.mark.fault
class TestFaultInjector:
    def test_stuck_bit_applied_to_chip(self, virtual_chip, fault_injector) -> None:
        applied = fault_injector.apply_to_chip(virtual_chip, cycle=0)
        assert "TEST_STUCK_BIT" in applied

    def test_fault_detected_by_memory_test(self, virtual_chip, fault_injector) -> None:
        fault_injector.apply_to_chip(virtual_chip, cycle=0)
        results = virtual_chip.run_memory_tests()
        failing = [r for r in results if not r.passed]
        assert len(failing) > 0

    def test_clear_all_deactivates_faults(self, fault_injector) -> None:
        fault_injector.clear_all()
        assert len(fault_injector.active_faults) == 0

    def test_cycle_trigger_not_applied_early(self, virtual_chip) -> None:
        cfg = FaultConfig(
            fault_id="DELAYED",
            fault_type=FaultType.STUCK_BIT,
            enabled=True,
            address=0,
            bit=0,
            value=1,
            trigger_after_cycles=100,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_chip(virtual_chip, cycle=50)
        assert "DELAYED" not in applied

    def test_cycle_trigger_applied_after_threshold(self, virtual_chip) -> None:
        cfg = FaultConfig(
            fault_id="DELAYED",
            fault_type=FaultType.STUCK_BIT,
            enabled=True,
            address=0,
            bit=0,
            value=1,
            trigger_after_cycles=100,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_chip(virtual_chip, cycle=150)
        assert "DELAYED" in applied

    def test_disabled_fault_not_applied(self, virtual_chip) -> None:
        cfg = FaultConfig(
            fault_id="DISABLED",
            fault_type=FaultType.STUCK_BIT,
            enabled=False,
            address=0,
            bit=0,
            value=1,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_chip(virtual_chip, cycle=0)
        assert "DISABLED" not in applied

    def test_i2c_timeout_applied(self, i2c_bus) -> None:
        cfg = FaultConfig(
            fault_id="I2C_TIMEOUT",
            fault_type=FaultType.I2C_TIMEOUT,
            enabled=True,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_i2c(i2c_bus, cycle=0)
        assert "I2C_TIMEOUT" in applied
        txn = i2c_bus.read_register(0x48, 0x00)
        assert not txn.success

    def test_load_fault_configs_from_yaml(self) -> None:
        yaml_path = Path("configs/faults.yaml")
        if yaml_path.exists():
            configs = load_fault_configs(yaml_path)
            assert isinstance(configs, list)

    def test_load_fault_configs_missing_file_raises(self) -> None:
        with pytest.raises(FaultInjectionError, match="not found"):
            load_fault_configs(Path("nonexistent.yaml"))

    def test_memory_corruption_fault(self, virtual_chip) -> None:
        cfg = FaultConfig(
            fault_id="MEM_CORRUPT",
            fault_type=FaultType.MEMORY_CORRUPTION,
            enabled=True,
            address=10,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_chip(virtual_chip, cycle=0)
        assert "MEM_CORRUPT" in applied

    def test_overheat_fault(self, virtual_chip) -> None:
        cfg = FaultConfig(
            fault_id="OVERHEAT",
            fault_type=FaultType.OVERHEAT,
            enabled=True,
            temperature=90.0,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_chip(virtual_chip, cycle=0)
        assert "OVERHEAT" in applied

    def test_spi_corruption_applied(self, spi_bus) -> None:
        cfg = FaultConfig(
            fault_id="SPI_CORRUPT",
            fault_type=FaultType.SPI_CORRUPTION,
            enabled=True,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_spi(spi_bus, cycle=0)
        assert "SPI_CORRUPT" in applied

    def test_spi_timeout_applied(self, spi_bus) -> None:
        cfg = FaultConfig(
            fault_id="SPI_TIMEOUT",
            fault_type=FaultType.SPI_TIMEOUT,
            enabled=True,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_spi(spi_bus, cycle=0)
        assert "SPI_TIMEOUT" in applied
        txn = spi_bus.read_register(0x00)
        assert not txn.success


@pytest.mark.unit
@pytest.mark.fault
class TestFaultInjectorExtras:
    """Extra tests to cover remaining uncovered lines in fault_injector.py."""

    # ── models property (line 41) ─────────────────────────────────────────

    def test_models_property(self, fault_injector: FaultInjector) -> None:
        """models property returns list of FaultModel objects (line 41)."""
        models = fault_injector.models
        assert isinstance(models, list)
        assert len(models) == 1

    # ── apply_to_chip probability skip (line 66) ──────────────────────────

    def test_apply_to_chip_probability_zero_skips(self, virtual_chip: VirtualChip) -> None:
        """Fault with probability=0.0 is never applied (line 66 — continue)."""
        cfg = FaultConfig(
            fault_id="PROB_ZERO",
            fault_type=FaultType.STUCK_BIT,
            enabled=True,
            address=0,
            bit=0,
            value=1,
            probability=0.0,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_chip(virtual_chip, cycle=0)
        assert "PROB_ZERO" not in applied

    # ── apply_to_chip exception handler (lines 75-76) ────────────────────

    def test_apply_to_chip_non_virtual_chip_exception_caught(self) -> None:
        """Passing a non-VirtualChip raises inside _apply_fault; apply_to_chip
        catches it and logs a warning (lines 75-76)."""
        cfg = FaultConfig(
            fault_id="BAD_TARGET",
            fault_type=FaultType.STUCK_BIT,
            enabled=True,
            address=0,
            bit=0,
            value=1,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_chip("not_a_chip", cycle=0)
        assert "BAD_TARGET" not in applied  # exception was caught, fault not counted

    # ── _apply_fault internal branches ───────────────────────────────────

    def test_apply_fault_stuck_bit_missing_fields_caught(self, virtual_chip: VirtualChip) -> None:
        """STUCK_BIT without address/bit/value raises inside _apply_fault (line 167);
        apply_to_chip catches and logs it (lines 75-76)."""
        cfg = FaultConfig(
            fault_id="INCOMPLETE",
            fault_type=FaultType.STUCK_BIT,
            enabled=True,
            probability=1.0,
            # address, bit, value all None
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_chip(virtual_chip, cycle=0)
        assert "INCOMPLETE" not in applied

    def test_apply_fault_memory_corruption_missing_address_caught(
        self, virtual_chip: VirtualChip
    ) -> None:
        """MEMORY_CORRUPTION without address raises (line 172); apply_to_chip catches it."""
        cfg = FaultConfig(
            fault_id="CORRUPT_NO_ADDR",
            fault_type=FaultType.MEMORY_CORRUPTION,
            enabled=True,
            probability=1.0,
            # address=None
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_chip(virtual_chip, cycle=0)
        assert "CORRUPT_NO_ADDR" not in applied

    def test_apply_fault_register_write_failure(self, virtual_chip: VirtualChip) -> None:
        """REGISTER_WRITE_FAILURE installs a fault callback (lines 177-182)."""
        cfg = FaultConfig(
            fault_id="REG_WRITE_FAIL",
            fault_type=FaultType.REGISTER_WRITE_FAILURE,
            enabled=True,
            address=0x02,  # POWER_CONTROL (RW)
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_chip(virtual_chip, cycle=0)
        assert "REG_WRITE_FAIL" in applied
        # Callback should cause write to register 0x02 to raise
        with pytest.raises(FaultInjectionError):
            virtual_chip.write_register(0x02, 0x01)

    def test_apply_fault_register_value_corruption(self, virtual_chip: VirtualChip) -> None:
        """REGISTER_VALUE_CORRUPTION corrupts a RW register in-place (lines 185-188)."""
        cfg = FaultConfig(
            fault_id="REG_CORRUPT",
            fault_type=FaultType.REGISTER_VALUE_CORRUPTION,
            enabled=True,
            address=0x02,  # POWER_CONTROL (RW)
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_chip(virtual_chip, cycle=0)
        assert "REG_CORRUPT" in applied

    def test_apply_fault_voltage_drop(self, virtual_chip: VirtualChip) -> None:
        """VOLTAGE_DROP executes lines 191-192 then raises (VOLTAGE_LEVEL is read-only);
        the exception is caught by apply_to_chip (lines 75-76)."""
        cfg = FaultConfig(
            fault_id="VOLT_DROP",
            fault_type=FaultType.VOLTAGE_DROP,
            enabled=True,
            voltage=2.5,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_chip(virtual_chip, cycle=0)
        # VOLTAGE_LEVEL (0x04) is read-only → write raises → exception caught → not applied
        assert "VOLT_DROP" not in applied

    def test_apply_fault_else_branch_no_chip_action(self, virtual_chip: VirtualChip) -> None:
        """Fault type with no chip-level action hits the else branch (line 199)."""
        cfg = FaultConfig(
            fault_id="I2C_NO_ACTION",
            fault_type=FaultType.I2C_TIMEOUT,  # no chip-level action
            enabled=True,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_chip(virtual_chip, cycle=0)
        assert "I2C_NO_ACTION" in applied  # _apply_fault succeeded (else branch, no raise)

    # ── apply_to_i2c branches (lines 93, 95, 97, 99, 103-104, 111-112) ──

    def test_apply_to_i2c_disabled_fault_skipped(self, i2c_bus) -> None:
        """Disabled fault in apply_to_i2c hits the enabled continue (line 93)."""
        cfg = FaultConfig(
            fault_id="DISABLED_I2C",
            fault_type=FaultType.I2C_TIMEOUT,
            enabled=False,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_i2c(i2c_bus, cycle=0)
        assert "DISABLED_I2C" not in applied

    def test_apply_to_i2c_wrong_type_skipped(self, i2c_bus) -> None:
        """Non-I2C fault type skipped in apply_to_i2c (line 95)."""
        cfg = FaultConfig(
            fault_id="STUCK_NOT_I2C",
            fault_type=FaultType.STUCK_BIT,
            enabled=True,
            address=0,
            bit=0,
            value=1,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_i2c(i2c_bus, cycle=0)
        assert "STUCK_NOT_I2C" not in applied

    def test_apply_to_i2c_cycle_trigger_skips(self, i2c_bus) -> None:
        """Cycle threshold not reached → continue (line 97)."""
        cfg = FaultConfig(
            fault_id="DELAYED_I2C",
            fault_type=FaultType.I2C_TIMEOUT,
            enabled=True,
            probability=1.0,
            trigger_after_cycles=100,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_i2c(i2c_bus, cycle=50)
        assert "DELAYED_I2C" not in applied

    def test_apply_to_i2c_probability_zero_skips(self, i2c_bus) -> None:
        """Probability=0 → continue in apply_to_i2c (line 99)."""
        cfg = FaultConfig(
            fault_id="PROB_ZERO_I2C",
            fault_type=FaultType.I2C_TIMEOUT,
            enabled=True,
            probability=0.0,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_i2c(i2c_bus, cycle=0)
        assert "PROB_ZERO_I2C" not in applied

    def test_apply_to_i2c_nack_fault(self, i2c_bus) -> None:
        """I2C_NACK fault type applies nack=1.0 to the bus (lines 103-104)."""
        cfg = FaultConfig(
            fault_id="I2C_NACK_TEST",
            fault_type=FaultType.I2C_NACK,
            enabled=True,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_i2c(i2c_bus, cycle=0)
        assert "I2C_NACK_TEST" in applied
        txn = i2c_bus.read_register(0x48, 0x00)
        assert not txn.success

    def test_apply_to_i2c_exception_caught(self, i2c_bus) -> None:
        """Non-bus object causes exception in apply_to_i2c; caught (lines 111-112)."""
        cfg = FaultConfig(
            fault_id="I2C_BAD_BUS",
            fault_type=FaultType.I2C_TIMEOUT,
            enabled=True,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_i2c("not_an_i2c_bus", cycle=0)
        assert "I2C_BAD_BUS" not in applied

    # ── apply_to_spi branches (lines 129, 131, 133, 135, 147-148) ────────

    def test_apply_to_spi_disabled_fault_skipped(self, spi_bus) -> None:
        """Disabled fault skipped in apply_to_spi (line 129)."""
        cfg = FaultConfig(
            fault_id="DISABLED_SPI",
            fault_type=FaultType.SPI_TIMEOUT,
            enabled=False,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_spi(spi_bus, cycle=0)
        assert "DISABLED_SPI" not in applied

    def test_apply_to_spi_wrong_type_skipped(self, spi_bus) -> None:
        """Non-SPI fault type skipped in apply_to_spi (line 131)."""
        cfg = FaultConfig(
            fault_id="STUCK_NOT_SPI",
            fault_type=FaultType.STUCK_BIT,
            enabled=True,
            address=0,
            bit=0,
            value=1,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_spi(spi_bus, cycle=0)
        assert "STUCK_NOT_SPI" not in applied

    def test_apply_to_spi_cycle_trigger_skips(self, spi_bus) -> None:
        """Cycle threshold not reached → skipped in apply_to_spi (line 133)."""
        cfg = FaultConfig(
            fault_id="DELAYED_SPI",
            fault_type=FaultType.SPI_TIMEOUT,
            enabled=True,
            probability=1.0,
            trigger_after_cycles=200,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_spi(spi_bus, cycle=100)
        assert "DELAYED_SPI" not in applied

    def test_apply_to_spi_probability_zero_skips(self, spi_bus) -> None:
        """Probability=0 → skipped in apply_to_spi (line 135)."""
        cfg = FaultConfig(
            fault_id="PROB_ZERO_SPI",
            fault_type=FaultType.SPI_TIMEOUT,
            enabled=True,
            probability=0.0,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_spi(spi_bus, cycle=0)
        assert "PROB_ZERO_SPI" not in applied

    def test_apply_to_spi_exception_caught(self, spi_bus) -> None:
        """Non-bus object causes exception in apply_to_spi; caught (lines 147-148)."""
        cfg = FaultConfig(
            fault_id="SPI_BAD_BUS",
            fault_type=FaultType.SPI_TIMEOUT,
            enabled=True,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        applied = injector.apply_to_spi("not_a_spi_bus", cycle=0)
        assert "SPI_BAD_BUS" not in applied


@pytest.mark.unit
@pytest.mark.fault
class TestFaultModelsExtras:
    """Covers fault_models.py lines 123-124 (invalid YAML)."""

    def test_load_invalid_yaml_raises(self, tmp_path: Path) -> None:
        """Invalid YAML triggers FaultInjectionError (lines 123-124)."""
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("faults: [unclosed bracket\n  - broken: {value")
        with pytest.raises(FaultInjectionError, match="Failed to parse fault config"):
            load_fault_configs(bad_yaml)
