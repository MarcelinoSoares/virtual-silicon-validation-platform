"""Unit tests for register side-effect behaviors (W1C, R2C)."""

import pytest

from virtual_silicon.device.register import AccessType, Register, RegisterBehavior
from virtual_silicon.device.register_map import RegisterMap
from virtual_silicon.device.virtual_chip import VirtualChip
from virtual_silicon.exceptions import RegisterAccessError


@pytest.mark.unit
class TestNormalBehavior:
    def test_normal_write_stores_value(self) -> None:
        reg = Register("NORM", 0x00, reset_value=0x00)
        reg.write(0xAB)
        assert reg.read() == 0xAB

    def test_normal_read_does_not_clear(self) -> None:
        reg = Register("NORM", 0x00, reset_value=0x55)
        reg.read()
        assert reg.value == 0x55

    def test_normal_is_default_behavior(self) -> None:
        reg = Register("NORM", 0x00)
        assert reg.behavior == RegisterBehavior.NORMAL


@pytest.mark.unit
class TestW1CBehavior:
    def test_write_ones_clears_corresponding_bits(self) -> None:
        reg = Register(
            "FLAGS", 0x09, reset_value=0x00, behavior=RegisterBehavior.WRITE_ONE_TO_CLEAR
        )
        reg.force_value(0xFF)  # simulate all bits set by hardware
        reg.write(0x0F)  # write 1 to lower nibble → clears bits 0-3
        assert reg.read() == 0xF0

    def test_write_zeros_does_not_change_bits(self) -> None:
        reg = Register(
            "FLAGS", 0x09, reset_value=0x00, behavior=RegisterBehavior.WRITE_ONE_TO_CLEAR
        )
        reg.force_value(0xFF)
        reg.write(0x00)  # write 0 to all bits → nothing changes
        assert reg.read() == 0xFF

    def test_write_all_ones_clears_register(self) -> None:
        reg = Register(
            "FLAGS", 0x09, reset_value=0x00, behavior=RegisterBehavior.WRITE_ONE_TO_CLEAR
        )
        reg.force_value(0xAB)
        reg.write(0xFF)
        assert reg.read() == 0x00

    def test_w1c_with_bit_mask(self) -> None:
        reg = Register(
            "FLAGS",
            0x09,
            reset_value=0x00,
            bit_mask=0x0F,
            behavior=RegisterBehavior.WRITE_ONE_TO_CLEAR,
        )
        reg.force_value(0x0F)
        reg.write(0x03)  # clear bits 0-1
        assert reg.read() == 0x0C

    def test_w1c_increments_write_count(self) -> None:
        reg = Register(
            "FLAGS", 0x09, reset_value=0x00, behavior=RegisterBehavior.WRITE_ONE_TO_CLEAR
        )
        reg.force_value(0xFF)
        reg.write(0xFF)
        assert reg.write_count == 1

    def test_read_only_still_rejected_for_w1c(self) -> None:
        reg = Register(
            "RO_W1C",
            0x00,
            access=AccessType.READ_ONLY,
            behavior=RegisterBehavior.WRITE_ONE_TO_CLEAR,
        )
        with pytest.raises(RegisterAccessError, match="read-only"):
            reg.write(0xFF)


@pytest.mark.unit
class TestR2CBehavior:
    def test_read_returns_value_then_clears(self) -> None:
        reg = Register("IRQ", 0x0C, reset_value=0x00, behavior=RegisterBehavior.READ_TO_CLEAR)
        reg.force_value(0xAA)
        val = reg.read()
        assert val == 0xAA
        assert reg.value == 0x00  # cleared to reset_value

    def test_second_read_returns_reset_value(self) -> None:
        reg = Register("IRQ", 0x0C, reset_value=0x00, behavior=RegisterBehavior.READ_TO_CLEAR)
        reg.force_value(0x55)
        reg.read()  # first read returns 0x55 and clears
        assert reg.read() == 0x00

    def test_r2c_clears_to_reset_value_not_zero(self) -> None:
        reg = Register(
            "IRQ",
            0x0C,
            reset_value=0xAB,
            behavior=RegisterBehavior.READ_TO_CLEAR,
        )
        reg.force_value(0xFF)
        reg.read()
        assert reg.value == 0xAB

    def test_r2c_increments_read_count(self) -> None:
        reg = Register("IRQ", 0x0C, reset_value=0x00, behavior=RegisterBehavior.READ_TO_CLEAR)
        reg.read()
        assert reg.read_count == 1


@pytest.mark.unit
class TestForceValue:
    def test_force_value_bypasses_read_only(self) -> None:
        reg = Register("RO", 0x00, access=AccessType.READ_ONLY, reset_value=0x00)
        reg.force_value(0xBE)
        assert reg.value == 0xBE

    def test_force_value_bypasses_w1c_semantics(self) -> None:
        reg = Register(
            "FLAGS", 0x09, reset_value=0x00, behavior=RegisterBehavior.WRITE_ONE_TO_CLEAR
        )
        reg.force_value(0xAB)
        # force_value sets absolute value, not W1C clear
        assert reg.value == 0xAB

    def test_force_value_applies_bit_mask(self) -> None:
        reg = Register("M", 0x00, bit_mask=0x0F, reset_value=0x00)
        reg.force_value(0xFF)
        assert reg.value == 0x0F  # masked to lower nibble

    def test_force_value_does_not_increment_write_count(self) -> None:
        reg = Register("RW", 0x00, reset_value=0x00)
        reg.force_value(0x42)
        assert reg.write_count == 0

    def test_max_value_mask_property(self) -> None:
        reg8 = Register("R8", 0x00, reset_value=0x00)
        assert reg8.max_value_mask == 0xFF

        from virtual_silicon.device.register import RegisterSize

        reg16 = Register("R16", 0x00, size=RegisterSize.BITS_16, reset_value=0x00)
        assert reg16.max_value_mask == 0xFFFF


@pytest.mark.unit
class TestSetFieldGuard:
    def test_set_field_raises_for_w1c(self) -> None:
        reg = Register(
            "FLAGS", 0x09, reset_value=0x00, behavior=RegisterBehavior.WRITE_ONE_TO_CLEAR
        )
        with pytest.raises(RegisterAccessError, match="set_field\\(\\) is not supported"):
            reg.set_field(0, 4, 0xF)

    def test_set_field_raises_for_r2c(self) -> None:
        reg = Register("IRQ", 0x0C, reset_value=0x00, behavior=RegisterBehavior.READ_TO_CLEAR)
        with pytest.raises(RegisterAccessError, match="set_field\\(\\) is not supported"):
            reg.set_field(0, 4, 0xF)

    def test_set_field_works_for_normal(self) -> None:
        reg = Register("RW", 0x00, reset_value=0x00)
        reg.set_field(4, 4, 0xA)
        assert reg.value == 0xA0

    def test_set_field_error_names_register(self) -> None:
        reg = Register(
            "ERROR_FLAGS", 0x09, reset_value=0x00, behavior=RegisterBehavior.WRITE_ONE_TO_CLEAR
        )
        with pytest.raises(RegisterAccessError, match="ERROR_FLAGS"):
            reg.set_field(0, 1, 1)


@pytest.mark.unit
class TestInjectHardwareValue:
    def test_inject_hardware_value_on_read_only_register(self) -> None:
        rm = RegisterMap()
        rm.inject_hardware_value(0x03, 90)  # TEMPERATURE — READ_ONLY
        assert rm.read(0x03) == 90

    def test_inject_hardware_value_on_voltage_level(self) -> None:
        rm = RegisterMap()
        rm.inject_hardware_value(0x04, 2500)  # VOLTAGE_LEVEL
        assert rm.read(0x04) == 2500

    def test_inject_hardware_value_invalid_address_raises(self) -> None:
        from virtual_silicon.exceptions import InvalidRegisterAddressError

        rm = RegisterMap()
        with pytest.raises(InvalidRegisterAddressError):
            rm.inject_hardware_value(0xFF, 0x00)


@pytest.mark.unit
class TestErrorFlagsW1CEndToEnd:
    def test_error_flags_default_behavior_is_w1c(self) -> None:
        rm = RegisterMap()
        reg = rm.get_by_name("ERROR_FLAGS")
        assert reg.behavior == RegisterBehavior.WRITE_ONE_TO_CLEAR

    def test_interrupt_status_default_behavior_is_w1c(self) -> None:
        rm = RegisterMap()
        reg = rm.get_by_name("INTERRUPT_STATUS")
        assert reg.behavior == RegisterBehavior.WRITE_ONE_TO_CLEAR

    def test_error_flags_w1c_via_register_map(self) -> None:
        rm = RegisterMap()
        rm.inject_hardware_value(0x09, 0xFF)  # simulate hardware setting all error bits
        rm.write(0x09, 0x0F)  # clear bits 0-3 via W1C
        assert rm.read(0x09) == 0xF0

    def test_error_flags_w1c_via_virtual_chip(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        chip.register_map.inject_hardware_value(0x09, 0xFF)
        chip.write_register(0x09, 0xFF)  # W1C: writing 0xFF clears all bits
        assert chip.read_register(0x09) == 0x00

    def test_interrupt_status_w1c_via_virtual_chip(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        chip.register_map.inject_hardware_value(0x0C, 0b10101010)
        chip.write_register(0x0C, 0b00001010)  # clear bits 1 and 3
        assert chip.read_register(0x0C) == 0b10100000

    def test_other_rw_registers_still_normal(self) -> None:
        chip = VirtualChip(seed=42)
        chip.power_on()
        chip.write_register(0x08, 0x55)  # DISPLAY_CONFIG — normal RW
        assert chip.read_register(0x08) == 0x55
