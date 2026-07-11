"""Unit tests for virtual register model."""

import pytest

from virtual_silicon.device.register import (
    AccessType,
    InvalidRegisterAddressError,
    Register,
    RegisterAccessError,
    RegisterSize,
)
from virtual_silicon.device.register_map import RegisterMap


@pytest.mark.unit
class TestRegisterBasics:
    def test_default_reset_value(self) -> None:
        reg = Register("TEST", 0x00, reset_value=0xAB)
        assert reg.read() == 0xAB

    def test_write_and_read_back(self) -> None:
        reg = Register("TEST", 0x00, reset_value=0x00)
        reg.write(0x42)
        assert reg.read() == 0x42

    def test_reset_restores_default(self) -> None:
        reg = Register("TEST", 0x00, reset_value=0x10)
        reg.write(0xFF)
        reg.reset()
        assert reg.read() == 0x10

    def test_read_only_raises_on_write(self) -> None:
        reg = Register("RO", 0x00, access=AccessType.READ_ONLY, reset_value=0xA5)
        with pytest.raises(RegisterAccessError, match="read-only"):
            reg.write(0x00)

    def test_write_only_raises_on_read(self) -> None:
        reg = Register("WO", 0x00, access=AccessType.WRITE_ONLY)
        with pytest.raises(RegisterAccessError, match="write-only"):
            reg.read()

    def test_bit_mask_applied_on_write(self) -> None:
        reg = Register("MASKED", 0x00, bit_mask=0x0F)
        reg.write(0xFF)
        assert reg.read() == 0x0F

    def test_out_of_range_raises(self) -> None:
        reg = Register("TEST", 0x00, size=RegisterSize.BITS_8)
        with pytest.raises(RegisterAccessError):
            reg.write(0x100)

    def test_negative_write_raises(self) -> None:
        reg = Register("TEST", 0x00)
        with pytest.raises(RegisterAccessError):
            reg.write(-1)

    def test_min_value_constraint(self) -> None:
        reg = Register("TEST", 0x00, min_value=10)
        with pytest.raises(RegisterAccessError, match="minimum"):
            reg.write(5)

    def test_max_value_constraint(self) -> None:
        reg = Register("TEST", 0x00, max_value=50)
        with pytest.raises(RegisterAccessError, match="maximum"):
            reg.write(60)

    def test_16bit_register(self) -> None:
        reg = Register("REG16", 0x00, size=RegisterSize.BITS_16)
        reg.write(0x1234)
        assert reg.read() == 0x1234

    def test_32bit_register(self) -> None:
        reg = Register("REG32", 0x00, size=RegisterSize.BITS_32)
        reg.write(0xDEADBEEF)
        assert reg.read() == 0xDEADBEEF

    def test_get_field_extraction(self) -> None:
        reg = Register("TEST", 0x00)
        reg.write(0b10110100)
        assert reg.get_field(2, 3) == 0b101

    def test_set_field_update(self) -> None:
        reg = Register("TEST", 0x00)
        reg.write(0x00)
        reg.set_field(4, 2, 0b11)
        assert reg.get_field(4, 2) == 0b11

    def test_write_count_increments(self) -> None:
        reg = Register("TEST", 0x00)
        reg.write(1)
        reg.write(2)
        assert reg.write_count == 2

    def test_read_count_increments(self) -> None:
        reg = Register("TEST", 0x00)
        reg.read()
        reg.read()
        assert reg.read_count == 2

    def test_repr(self) -> None:
        reg = Register("TEST", 0x10)
        assert "TEST" in repr(reg)
        assert "0x0010" in repr(reg)


@pytest.mark.unit
class TestRegisterMap:
    def test_read_device_id(self, register_map: RegisterMap) -> None:
        assert register_map.read(0x00) == 0xA5

    def test_write_power_control(self, register_map: RegisterMap) -> None:
        register_map.write(0x02, 0x0F)
        assert register_map.read(0x02) == 0x0F

    def test_invalid_address_raises(self, register_map: RegisterMap) -> None:
        with pytest.raises(InvalidRegisterAddressError):
            register_map.read(0xFF)

    def test_get_by_name(self, register_map: RegisterMap) -> None:
        reg = register_map.get_by_name("DEVICE_ID")
        assert reg.name == "DEVICE_ID"

    def test_get_by_name_not_found(self, register_map: RegisterMap) -> None:
        with pytest.raises(InvalidRegisterAddressError):
            register_map.get_by_name("NONEXISTENT")

    def test_reset_all(self, register_map: RegisterMap) -> None:
        register_map.write(0x02, 0x0F)
        register_map.reset_all()
        assert register_map.read(0x02) == 0x00

    def test_snapshot_contains_all_registers(self, register_map: RegisterMap) -> None:
        snap = register_map.get_snapshot()
        assert "DEVICE_ID" in snap
        assert "POWER_CONTROL" in snap

    def test_len(self, register_map: RegisterMap) -> None:
        assert len(register_map) >= 10

    def test_contains(self, register_map: RegisterMap) -> None:
        assert 0x00 in register_map
        assert 0xFF not in register_map

    def test_iteration(self, register_map: RegisterMap) -> None:
        names = [r.name for r in register_map]
        assert "DEVICE_ID" in names

    def test_read_only_register_not_writable(self, register_map: RegisterMap) -> None:
        with pytest.raises(RegisterAccessError):
            register_map.write(0x00, 0x00)

    def test_snapshot_falls_back_to_value_for_write_only_register(
        self, register_map: RegisterMap
    ) -> None:
        """get_snapshot() uses reg.value when read() raises (lines 185-186 in register_map,
        and line 84 in register.py — the value property)."""
        # Inject a write-only register into the map
        from virtual_silicon.device.register import AccessType, Register
        wo_reg = Register("WO_TEST", 0xFE, access=AccessType.WRITE_ONLY, reset_value=0xAB)
        register_map._registers[0xFE] = wo_reg
        register_map._name_index["WO_TEST"] = wo_reg

        snapshot = register_map.get_snapshot()

        # The write-only register must appear in the snapshot via reg.value fallback
        assert "WO_TEST" in snapshot
        assert snapshot["WO_TEST"] == 0xAB  # reset_value masked by bit_mask (0xFF) = 0xAB


@pytest.mark.unit
class TestRegisterValueProperty:
    """Covers register.py line 84 (value property) in isolation."""

    def test_value_property_returns_current_value(self) -> None:
        """The value property returns _value without incrementing read_count (line 84)."""
        reg = Register("TEST", 0x00, reset_value=0x77)
        assert reg.value == 0x77
        assert reg.read_count == 0  # read_count is NOT incremented by .value

    def test_value_property_after_write(self) -> None:
        reg = Register("TEST", 0x00)
        reg.write(0x42)
        assert reg.value == 0x42
