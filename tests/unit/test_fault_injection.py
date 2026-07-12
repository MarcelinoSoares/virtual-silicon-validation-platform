"""Unit tests for fault injection framework."""

from pathlib import Path

import pytest

from virtual_silicon.device.virtual_chip import VirtualChip
from virtual_silicon.faults.fault_injector import FaultApplicationResult, FaultInjector
from virtual_silicon.faults.fault_models import (
    FaultConfig,
    FaultInjectionError,
    FaultType,
    load_fault_configs,
)


def _ids(results: list[FaultApplicationResult]) -> list[str]:
    """Extract applied fault IDs from a result list."""
    return [r.fault_id for r in results if r.applied]


@pytest.mark.unit
@pytest.mark.fault
class TestFaultConfig:
    def test_from_dict_stuck_bit(self) -> None:
        data = {
            "id": "TEST",
            "type": "stuck_bit",
            "enabled": True,
            "address": 5,
            "bit": 2,
            "value": 1,
        }
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
        results = fault_injector.apply_to_chip(virtual_chip, cycle=0)
        assert "TEST_STUCK_BIT" in _ids(results)

    def test_fault_detected_by_memory_test(self, virtual_chip, fault_injector) -> None:
        fault_injector.apply_to_chip(virtual_chip, cycle=0)
        results = virtual_chip.run_memory_tests()
        failing = [r for r in results if not r.passed]
        assert len(failing) > 0

    def test_clear_fault_registry_deactivates_faults(self, fault_injector) -> None:
        fault_injector.clear_fault_registry()
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
        results = injector.apply_to_chip(virtual_chip, cycle=50)
        assert "DELAYED" not in _ids(results)

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
        results = injector.apply_to_chip(virtual_chip, cycle=150)
        assert "DELAYED" in _ids(results)

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
        results = injector.apply_to_chip(virtual_chip, cycle=0)
        assert "DISABLED" not in _ids(results)

    def test_i2c_timeout_applied(self, i2c_bus) -> None:
        cfg = FaultConfig(
            fault_id="I2C_TIMEOUT",
            fault_type=FaultType.I2C_TIMEOUT,
            enabled=True,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        results = injector.apply_to_i2c(i2c_bus, cycle=0)
        assert "I2C_TIMEOUT" in _ids(results)
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
        results = injector.apply_to_chip(virtual_chip, cycle=0)
        assert "MEM_CORRUPT" in _ids(results)

    def test_overheat_fault(self, virtual_chip) -> None:
        cfg = FaultConfig(
            fault_id="OVERHEAT",
            fault_type=FaultType.OVERHEAT,
            enabled=True,
            temperature=90.0,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        results = injector.apply_to_chip(virtual_chip, cycle=0)
        assert "OVERHEAT" in _ids(results)

    def test_spi_corruption_applied(self, spi_bus) -> None:
        cfg = FaultConfig(
            fault_id="SPI_CORRUPT",
            fault_type=FaultType.SPI_CORRUPTION,
            enabled=True,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        results = injector.apply_to_spi(spi_bus, cycle=0)
        assert "SPI_CORRUPT" in _ids(results)

    def test_spi_timeout_applied(self, spi_bus) -> None:
        cfg = FaultConfig(
            fault_id="SPI_TIMEOUT",
            fault_type=FaultType.SPI_TIMEOUT,
            enabled=True,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        results = injector.apply_to_spi(spi_bus, cycle=0)
        assert "SPI_TIMEOUT" in _ids(results)
        txn = spi_bus.read_register(0x00)
        assert not txn.success


@pytest.mark.unit
@pytest.mark.fault
class TestFaultApplicationResult:
    def test_result_has_fault_id_applied_error_fields(self, virtual_chip) -> None:
        cfg = FaultConfig(
            fault_id="STUCK",
            fault_type=FaultType.STUCK_BIT,
            enabled=True,
            address=0,
            bit=0,
            value=1,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        results = injector.apply_to_chip(virtual_chip, cycle=0)
        assert len(results) == 1
        r = results[0]
        assert r.fault_id == "STUCK"
        assert r.applied is True
        assert r.error is None

    def test_failed_result_has_applied_false_and_error(self, virtual_chip) -> None:
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
        results = injector.apply_to_chip("not_a_chip", cycle=0)
        assert len(results) == 1
        r = results[0]
        assert r.fault_id == "BAD_TARGET"
        assert r.applied is False
        assert r.error is not None

    def test_strict_mode_raises_on_failure(self) -> None:
        cfg = FaultConfig(
            fault_id="STRICT_FAIL",
            fault_type=FaultType.STUCK_BIT,
            enabled=True,
            address=0,
            bit=0,
            value=1,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        with pytest.raises(FaultInjectionError, match="STRICT_FAIL"):
            injector.apply_to_chip("not_a_chip", cycle=0, strict=True)

    def test_strict_mode_does_not_raise_on_success(self, virtual_chip) -> None:
        cfg = FaultConfig(
            fault_id="STRICT_OK",
            fault_type=FaultType.STUCK_BIT,
            enabled=True,
            address=0,
            bit=0,
            value=1,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        results = injector.apply_to_chip(virtual_chip, cycle=0, strict=True)
        assert "STRICT_OK" in _ids(results)


@pytest.mark.unit
@pytest.mark.fault
class TestFaultLifecycle:
    def test_reset_chip_faults_removes_callbacks(self, virtual_chip) -> None:
        cfg = FaultConfig(
            fault_id="WRITE_FAIL",
            fault_type=FaultType.REGISTER_WRITE_FAILURE,
            enabled=True,
            address=0x02,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        injector.apply_to_chip(virtual_chip, cycle=0)
        # Verify callback is active
        with pytest.raises(FaultInjectionError):
            virtual_chip.write_register(0x02, 0x01)
        # Reset chip faults
        injector.reset_chip_faults(virtual_chip)
        # Callback removed — write should now succeed (power_on resets registers)
        virtual_chip.warm_reset()
        virtual_chip.write_register(0x08, 0x42)  # DISPLAY_CONFIG — unaffected register

    def test_reset_chip_faults_restores_register_values(self, virtual_chip) -> None:
        cfg = FaultConfig(
            fault_id="OVERHEAT",
            fault_type=FaultType.OVERHEAT,
            enabled=True,
            temperature=200.0,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        injector.apply_to_chip(virtual_chip, cycle=0)
        assert virtual_chip.register_map.read(0x03) == 200  # injected value
        injector.reset_chip_faults(virtual_chip)
        assert virtual_chip.register_map.read(0x03) == 0x19  # reset value

    def test_reset_chip_faults_invalid_type_raises(self) -> None:
        injector = FaultInjector([], seed=42)
        with pytest.raises(FaultInjectionError, match="Expected VirtualChip"):
            injector.reset_chip_faults("not_a_chip")

    def test_reset_i2c_faults_clears_probabilities(self, i2c_bus) -> None:
        cfg = FaultConfig(
            fault_id="I2C_TIMEOUT",
            fault_type=FaultType.I2C_TIMEOUT,
            enabled=True,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        injector.apply_to_i2c(i2c_bus, cycle=0)
        # Bus should be failing
        txn_before = i2c_bus.read_register(0x48, 0x00)
        assert not txn_before.success
        # Reset faults
        injector.reset_i2c_faults(i2c_bus)
        txn_after = i2c_bus.read_register(0x48, 0x00)
        assert txn_after.success

    def test_reset_spi_faults_clears_probabilities(self, spi_bus) -> None:
        cfg = FaultConfig(
            fault_id="SPI_TIMEOUT",
            fault_type=FaultType.SPI_TIMEOUT,
            enabled=True,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        injector.apply_to_spi(spi_bus, cycle=0)
        txn_before = spi_bus.read_register(0x00)
        assert not txn_before.success
        injector.reset_spi_faults(spi_bus)
        txn_after = spi_bus.read_register(0x00)
        assert txn_after.success

    def test_clear_fault_registry_only_clears_admin_state(self, virtual_chip) -> None:
        cfg = FaultConfig(
            fault_id="OVERHEAT",
            fault_type=FaultType.OVERHEAT,
            enabled=True,
            temperature=200.0,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        injector.apply_to_chip(virtual_chip, cycle=0)
        injector.clear_fault_registry()
        assert len(injector.active_faults) == 0
        # Temperature still injected — admin cleared but hardware effect persists
        assert virtual_chip.register_map.read(0x03) == 200


@pytest.mark.unit
@pytest.mark.fault
class TestFaultInjectorExtras:
    """Extra tests to cover remaining uncovered lines in fault_injector.py."""

    # ── models property ─────────────────────────────────────────────────────

    def test_models_property(self, fault_injector: FaultInjector) -> None:
        models = fault_injector.models
        assert isinstance(models, list)
        assert len(models) == 1

    # ── apply_to_chip probability skip ──────────────────────────────────────

    def test_apply_to_chip_probability_zero_skips(self, virtual_chip: VirtualChip) -> None:
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
        results = injector.apply_to_chip(virtual_chip, cycle=0)
        assert "PROB_ZERO" not in _ids(results)

    # ── apply_to_chip exception handler ─────────────────────────────────────

    def test_apply_to_chip_non_virtual_chip_exception_caught(self) -> None:
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
        results = injector.apply_to_chip("not_a_chip", cycle=0)
        assert "BAD_TARGET" not in _ids(results)

    # ── _apply_fault internal branches ──────────────────────────────────────

    def test_apply_fault_stuck_bit_missing_fields_caught(self, virtual_chip: VirtualChip) -> None:
        cfg = FaultConfig(
            fault_id="INCOMPLETE",
            fault_type=FaultType.STUCK_BIT,
            enabled=True,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        results = injector.apply_to_chip(virtual_chip, cycle=0)
        assert "INCOMPLETE" not in _ids(results)

    def test_apply_fault_memory_corruption_missing_address_caught(
        self, virtual_chip: VirtualChip
    ) -> None:
        cfg = FaultConfig(
            fault_id="CORRUPT_NO_ADDR",
            fault_type=FaultType.MEMORY_CORRUPTION,
            enabled=True,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        results = injector.apply_to_chip(virtual_chip, cycle=0)
        assert "CORRUPT_NO_ADDR" not in _ids(results)

    def test_apply_fault_register_write_failure(self, virtual_chip: VirtualChip) -> None:
        cfg = FaultConfig(
            fault_id="REG_WRITE_FAIL",
            fault_type=FaultType.REGISTER_WRITE_FAILURE,
            enabled=True,
            address=0x02,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        results = injector.apply_to_chip(virtual_chip, cycle=0)
        assert "REG_WRITE_FAIL" in _ids(results)
        with pytest.raises(FaultInjectionError):
            virtual_chip.write_register(0x02, 0x01)

    def test_apply_fault_register_value_corruption(self, virtual_chip: VirtualChip) -> None:
        cfg = FaultConfig(
            fault_id="REG_CORRUPT",
            fault_type=FaultType.REGISTER_VALUE_CORRUPTION,
            enabled=True,
            address=0x02,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        results = injector.apply_to_chip(virtual_chip, cycle=0)
        assert "REG_CORRUPT" in _ids(results)

    def test_apply_fault_voltage_drop(self, virtual_chip: VirtualChip) -> None:
        cfg = FaultConfig(
            fault_id="VOLT_DROP",
            fault_type=FaultType.VOLTAGE_DROP,
            enabled=True,
            voltage=2.5,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        results = injector.apply_to_chip(virtual_chip, cycle=0)
        assert "VOLT_DROP" in _ids(results)
        # 2.5 V × 1000 = 2500 mV = 0x09C4
        assert virtual_chip.register_map.read(0x04) == 2500

    def test_apply_fault_overcurrent(self, virtual_chip: VirtualChip) -> None:
        from virtual_silicon.device.virtual_chip import PowerState

        cfg = FaultConfig(
            fault_id="OVERCURRENT",
            fault_type=FaultType.OVERCURRENT,
            enabled=True,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        results = injector.apply_to_chip(virtual_chip, cycle=0)
        assert "OVERCURRENT" in _ids(results)
        assert virtual_chip.power_state == PowerState.FAULT

    def test_apply_fault_else_branch_no_chip_action(self, virtual_chip: VirtualChip) -> None:
        cfg = FaultConfig(
            fault_id="I2C_NO_ACTION",
            fault_type=FaultType.I2C_TIMEOUT,
            enabled=True,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        results = injector.apply_to_chip(virtual_chip, cycle=0)
        assert "I2C_NO_ACTION" in _ids(results)

    # ── apply_to_i2c branches ────────────────────────────────────────────────

    def test_apply_to_i2c_disabled_fault_skipped(self, i2c_bus) -> None:
        cfg = FaultConfig(
            fault_id="DISABLED_I2C",
            fault_type=FaultType.I2C_TIMEOUT,
            enabled=False,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        results = injector.apply_to_i2c(i2c_bus, cycle=0)
        assert "DISABLED_I2C" not in _ids(results)

    def test_apply_to_i2c_wrong_type_skipped(self, i2c_bus) -> None:
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
        results = injector.apply_to_i2c(i2c_bus, cycle=0)
        assert "STUCK_NOT_I2C" not in _ids(results)

    def test_apply_to_i2c_cycle_trigger_skips(self, i2c_bus) -> None:
        cfg = FaultConfig(
            fault_id="DELAYED_I2C",
            fault_type=FaultType.I2C_TIMEOUT,
            enabled=True,
            probability=1.0,
            trigger_after_cycles=100,
        )
        injector = FaultInjector([cfg], seed=42)
        results = injector.apply_to_i2c(i2c_bus, cycle=50)
        assert "DELAYED_I2C" not in _ids(results)

    def test_apply_to_i2c_probability_zero_skips(self, i2c_bus) -> None:
        cfg = FaultConfig(
            fault_id="PROB_ZERO_I2C",
            fault_type=FaultType.I2C_TIMEOUT,
            enabled=True,
            probability=0.0,
        )
        injector = FaultInjector([cfg], seed=42)
        results = injector.apply_to_i2c(i2c_bus, cycle=0)
        assert "PROB_ZERO_I2C" not in _ids(results)

    def test_apply_to_i2c_nack_fault(self, i2c_bus) -> None:
        cfg = FaultConfig(
            fault_id="I2C_NACK_TEST",
            fault_type=FaultType.I2C_NACK,
            enabled=True,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        results = injector.apply_to_i2c(i2c_bus, cycle=0)
        assert "I2C_NACK_TEST" in _ids(results)
        txn = i2c_bus.read_register(0x48, 0x00)
        assert not txn.success

    def test_apply_to_i2c_exception_caught(self, i2c_bus) -> None:
        cfg = FaultConfig(
            fault_id="I2C_BAD_BUS",
            fault_type=FaultType.I2C_TIMEOUT,
            enabled=True,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        results = injector.apply_to_i2c("not_an_i2c_bus", cycle=0)
        assert "I2C_BAD_BUS" not in _ids(results)

    # ── apply_to_spi branches ────────────────────────────────────────────────

    def test_apply_to_spi_disabled_fault_skipped(self, spi_bus) -> None:
        cfg = FaultConfig(
            fault_id="DISABLED_SPI",
            fault_type=FaultType.SPI_TIMEOUT,
            enabled=False,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        results = injector.apply_to_spi(spi_bus, cycle=0)
        assert "DISABLED_SPI" not in _ids(results)

    def test_apply_to_spi_wrong_type_skipped(self, spi_bus) -> None:
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
        results = injector.apply_to_spi(spi_bus, cycle=0)
        assert "STUCK_NOT_SPI" not in _ids(results)

    def test_apply_to_spi_cycle_trigger_skips(self, spi_bus) -> None:
        cfg = FaultConfig(
            fault_id="DELAYED_SPI",
            fault_type=FaultType.SPI_TIMEOUT,
            enabled=True,
            probability=1.0,
            trigger_after_cycles=200,
        )
        injector = FaultInjector([cfg], seed=42)
        results = injector.apply_to_spi(spi_bus, cycle=100)
        assert "DELAYED_SPI" not in _ids(results)

    def test_apply_to_spi_probability_zero_skips(self, spi_bus) -> None:
        cfg = FaultConfig(
            fault_id="PROB_ZERO_SPI",
            fault_type=FaultType.SPI_TIMEOUT,
            enabled=True,
            probability=0.0,
        )
        injector = FaultInjector([cfg], seed=42)
        results = injector.apply_to_spi(spi_bus, cycle=0)
        assert "PROB_ZERO_SPI" not in _ids(results)

    def test_apply_to_spi_exception_caught(self, spi_bus) -> None:
        cfg = FaultConfig(
            fault_id="SPI_BAD_BUS",
            fault_type=FaultType.SPI_TIMEOUT,
            enabled=True,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        results = injector.apply_to_spi("not_a_spi_bus", cycle=0)
        assert "SPI_BAD_BUS" not in _ids(results)


@pytest.mark.unit
@pytest.mark.fault
class TestFaultModelsExtras:
    """Covers fault_models.py lines 123-124 (invalid YAML)."""

    def test_load_invalid_yaml_raises(self, tmp_path: Path) -> None:
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("faults: [unclosed bracket\n  - broken: {value")
        with pytest.raises(FaultInjectionError, match="Failed to parse fault config"):
            load_fault_configs(bad_yaml)
