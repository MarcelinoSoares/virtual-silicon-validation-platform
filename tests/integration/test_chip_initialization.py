"""Integration tests for chip initialization and power sequencing."""

import pytest

from virtual_silicon.device.virtual_chip import DeviceNotPoweredError, VirtualChip


@pytest.mark.integration
class TestChipInitialization:
    def test_chip_powers_on_and_has_correct_device_id(self, virtual_chip: VirtualChip) -> None:
        assert virtual_chip.powered
        assert virtual_chip.get_device_id() == 0xA5

    def test_register_reset_values_on_power_on(self, virtual_chip: VirtualChip) -> None:
        snap = virtual_chip.get_register_snapshot()
        assert snap["DEVICE_ID"] == 0xA5
        assert snap["POWER_CONTROL"] == 0x00
        assert snap["ERROR_FLAGS"] == 0x00

    def test_firmware_version_readable(self, virtual_chip: VirtualChip) -> None:
        assert virtual_chip.get_firmware_version() == "1.0"

    def test_sram_clear_on_power_on(self, virtual_chip: VirtualChip) -> None:
        for addr in range(10):
            assert virtual_chip.read_memory(addr) == 0x00

    def test_cycle_count_starts_at_zero(self, unpowered_chip: VirtualChip) -> None:
        unpowered_chip.power_on()
        assert unpowered_chip.cycle_count == 0

    def test_power_on_twice_is_idempotent(self, virtual_chip: VirtualChip) -> None:
        virtual_chip.power_on()
        assert virtual_chip.powered

    def test_operations_fail_when_unpowered(self, unpowered_chip: VirtualChip) -> None:
        with pytest.raises(DeviceNotPoweredError):
            unpowered_chip.read_register(0x00)

    def test_health_status_structure(self, virtual_chip: VirtualChip) -> None:
        health = virtual_chip.get_health_status()
        assert "powered" in health
        assert "cycle_count" in health
        assert "chip_version" in health
        assert "firmware_version" in health

    def test_reset_after_writes(self, virtual_chip: VirtualChip) -> None:
        virtual_chip.write_register(0x02, 0x0F)
        virtual_chip.reset()
        assert virtual_chip.read_register(0x02) == 0x00

    def test_power_off_then_on_clears_state(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        chip.write_register(0x02, 0x0F)
        chip.power_off()
        chip.power_on()
        assert chip.read_register(0x02) == 0x00

    def test_chip_version_string(self, virtual_chip: VirtualChip) -> None:
        assert virtual_chip.CHIP_VERSION == "VS-1000-A"

    def test_sram_size_default(self, virtual_chip: VirtualChip) -> None:
        assert virtual_chip.sram.size == 256

    def test_power_off_already_off_is_harmless(self, unpowered_chip: VirtualChip) -> None:
        """power_off() on an already-powered-off chip logs a warning and returns (lines 79-80)."""
        assert not unpowered_chip.powered
        unpowered_chip.power_off()  # Should not raise
        assert not unpowered_chip.powered

    def test_write_memory_powered(self, virtual_chip: VirtualChip) -> None:
        """write_memory() on a powered chip writes and reads back correctly (lines 153-155)."""
        virtual_chip.write_memory(0, 0x42)
        assert virtual_chip.read_memory(0) == 0x42

    def test_write_memory_increments_cycle(self, virtual_chip: VirtualChip) -> None:
        """write_memory() increments cycle_count (line 154)."""
        before = virtual_chip.cycle_count
        virtual_chip.write_memory(1, 0xAB)
        assert virtual_chip.cycle_count == before + 1

    def test_add_fault_callback_registered(self, virtual_chip: VirtualChip) -> None:
        """add_fault_callback() appends callback to the list (line 199)."""
        calls = []

        def my_callback(event: str, address: int, cycle: int) -> None:
            calls.append((event, address, cycle))

        virtual_chip.add_fault_callback(my_callback)
        virtual_chip.read_register(0x00)
        assert len(calls) == 1
        assert calls[0][0] == "register_read"

    def test_fault_callback_exception_propagates(self, virtual_chip: VirtualChip) -> None:
        """A fault callback that raises causes _trigger_fault_callbacks to re-raise (lines 207-211)."""
        from virtual_silicon.faults.fault_models import FaultInjectionError

        def bad_callback(event: str, address: int, cycle: int) -> None:
            raise FaultInjectionError("Simulated fault callback failure")

        virtual_chip.add_fault_callback(bad_callback)
        with pytest.raises(FaultInjectionError, match="Simulated fault callback failure"):
            virtual_chip.read_register(0x00)

    def test_run_memory_tests_not_powered_raises(self, unpowered_chip: VirtualChip) -> None:
        """run_memory_tests() on an unpowered chip raises DeviceNotPoweredError (lines 153-155)."""
        with pytest.raises(DeviceNotPoweredError):
            unpowered_chip.run_memory_tests()
