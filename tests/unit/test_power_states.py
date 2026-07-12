"""Unit tests for VirtualChip power state machine."""

import pytest

from virtual_silicon.device.virtual_chip import PowerState, VirtualChip
from virtual_silicon.exceptions import DeviceNotPoweredError, InvalidPowerTransitionError
from virtual_silicon.faults.fault_injector import FaultApplicationResult, FaultInjector
from virtual_silicon.faults.fault_models import FaultConfig, FaultType


def _ids(results: list[FaultApplicationResult]) -> list[str]:
    return [r.fault_id for r in results if r.applied]


@pytest.mark.unit
class TestPowerStateTransitions:
    def test_initial_state_is_off(self) -> None:
        chip = VirtualChip(seed=42)
        assert chip.power_state == PowerState.OFF

    def test_power_on_reaches_ready(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        assert chip.power_state == PowerState.READY

    def test_power_off_from_ready_goes_to_off(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        chip.power_off()
        assert chip.power_state == PowerState.OFF

    def test_power_on_already_on_is_idempotent(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        chip.power_on()
        assert chip.power_state == PowerState.READY

    def test_power_off_already_off_is_idempotent(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_off()
        assert chip.power_state == PowerState.OFF

    def test_warm_reset_returns_to_ready(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        chip.warm_reset()
        assert chip.power_state == PowerState.READY

    def test_warm_reset_while_off_raises(self) -> None:
        chip = VirtualChip(seed=42)
        with pytest.raises(DeviceNotPoweredError):
            chip.warm_reset()

    def test_fault_shutdown_goes_to_fault(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        chip.fault_shutdown()
        assert chip.power_state == PowerState.FAULT

    def test_fault_shutdown_from_off_goes_to_fault(self) -> None:
        chip = VirtualChip(seed=42)
        chip.fault_shutdown()
        assert chip.power_state == PowerState.FAULT

    def test_power_on_from_fault_raises(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        chip.fault_shutdown()
        assert chip.power_state == PowerState.FAULT
        with pytest.raises(InvalidPowerTransitionError, match="recover_from_fault"):
            chip.power_on()

    def test_power_off_from_fault_goes_to_off(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        chip.fault_shutdown()
        chip.power_off()
        assert chip.power_state == PowerState.OFF


@pytest.mark.unit
class TestFaultRecovery:
    def test_recover_from_fault_transitions_to_off(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        chip.fault_shutdown()
        chip.recover_from_fault()
        assert chip.power_state == PowerState.OFF

    def test_recover_from_fault_then_power_on_reaches_ready(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        chip.fault_shutdown()
        chip.recover_from_fault()
        chip.power_on()
        assert chip.power_state == PowerState.READY

    def test_recover_from_non_fault_raises(self) -> None:
        chip = VirtualChip(seed=42)
        with pytest.raises(InvalidPowerTransitionError, match="expected 'fault'"):
            chip.recover_from_fault()

    def test_recover_from_ready_raises(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        with pytest.raises(InvalidPowerTransitionError, match="expected 'fault'"):
            chip.recover_from_fault()

    def test_full_overcurrent_lifecycle(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        cfg = FaultConfig(
            fault_id="OC",
            fault_type=FaultType.OVERCURRENT,
            enabled=True,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        results = injector.apply_to_chip(chip, cycle=0)
        assert "OC" in _ids(results)
        assert chip.power_state == PowerState.FAULT
        chip.recover_from_fault()
        assert chip.power_state == PowerState.OFF
        chip.power_on()
        assert chip.power_state == PowerState.READY


@pytest.mark.unit
class TestClearFaultCallbacks:
    def test_clear_fault_callbacks_removes_all(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        events: list[str] = []
        chip.add_fault_callback(lambda e, a, c: events.append(e))
        chip.read_register(0x00)
        assert len(events) > 0
        chip.clear_fault_callbacks()
        before = len(events)
        chip.read_register(0x00)
        assert len(events) == before  # no new events after clear


@pytest.mark.unit
class TestPoweredBackwardCompat:
    def test_powered_true_when_ready(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        assert chip.powered is True

    def test_powered_false_when_off(self) -> None:
        chip = VirtualChip(seed=42)
        assert chip.powered is False

    def test_powered_false_when_fault(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        chip.fault_shutdown()
        assert chip.powered is False


@pytest.mark.unit
class TestAccessGuardByState:
    def test_read_register_requires_ready(self) -> None:
        chip = VirtualChip(seed=42)
        with pytest.raises(DeviceNotPoweredError, match="state: off"):
            chip.read_register(0x00)

    def test_write_register_requires_ready(self) -> None:
        chip = VirtualChip(seed=42)
        with pytest.raises(DeviceNotPoweredError, match="state: off"):
            chip.write_register(0x02, 0x01)

    def test_read_memory_requires_ready(self) -> None:
        chip = VirtualChip(seed=42)
        with pytest.raises(DeviceNotPoweredError):
            chip.read_memory(0x00)

    def test_write_memory_requires_ready(self) -> None:
        chip = VirtualChip(seed=42)
        with pytest.raises(DeviceNotPoweredError):
            chip.write_memory(0x00, 0xFF)

    def test_registers_inaccessible_in_fault_state(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        chip.fault_shutdown()
        with pytest.raises(DeviceNotPoweredError, match="state: fault"):
            chip.read_register(0x00)

    def test_error_message_includes_state(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        chip.fault_shutdown()
        with pytest.raises(DeviceNotPoweredError) as exc_info:
            chip.read_register(0x00)
        assert "fault" in str(exc_info.value)


@pytest.mark.unit
class TestPowerControlCoupling:
    def test_write_zero_to_power_control_powers_off(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        chip.write_register(0x02, 0x00)
        assert chip.power_state == PowerState.OFF

    def test_write_enable_bit_keeps_chip_on(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        chip.write_register(0x02, 0x01)
        assert chip.power_state == PowerState.READY

    def test_write_reset_bit_triggers_warm_reset(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        chip.write_register(0x08, 0x55)
        chip.write_register(0x02, 0x02)
        assert chip.power_state == PowerState.READY
        # DISPLAY_CONFIG should be reset to 0x80 after warm_reset
        assert chip.read_register(0x08) == 0x80

    def test_write_enable_and_reset_bits_triggers_reset(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        # Both bits set: RESET takes precedence over ENABLE
        chip.write_register(0x02, 0x03)
        assert chip.power_state == PowerState.READY


@pytest.mark.unit
class TestHealthStatusPowerState:
    def test_health_status_includes_power_state(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        status = chip.get_health_status()
        assert "power_state" in status
        assert status["power_state"] == "ready"

    def test_health_status_powered_false_when_off(self) -> None:
        chip = VirtualChip(seed=42)
        status = chip.get_health_status()
        assert status["powered"] is False
        assert status["power_state"] == "off"

    def test_health_status_powered_false_when_fault(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        chip.fault_shutdown()
        status = chip.get_health_status()
        assert status["powered"] is False
        assert status["power_state"] == "fault"


@pytest.mark.unit
@pytest.mark.fault
class TestOvercurrentFault:
    def test_overcurrent_fault_transitions_to_fault_state(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        cfg = FaultConfig(
            fault_id="OVERCURRENT",
            fault_type=FaultType.OVERCURRENT,
            enabled=True,
            probability=1.0,
        )
        injector = FaultInjector([cfg], seed=42)
        results = injector.apply_to_chip(chip, cycle=0)
        assert "OVERCURRENT" in _ids(results)
        assert chip.power_state == PowerState.FAULT

    def test_chip_inaccessible_after_overcurrent(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        cfg = FaultConfig(
            fault_id="OC",
            fault_type=FaultType.OVERCURRENT,
            enabled=True,
            probability=1.0,
        )
        FaultInjector([cfg], seed=42).apply_to_chip(chip, cycle=0)
        with pytest.raises(DeviceNotPoweredError):
            chip.read_register(0x00)
