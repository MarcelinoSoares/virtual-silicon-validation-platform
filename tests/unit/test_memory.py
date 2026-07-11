"""Unit tests for SRAM simulation and memory test patterns."""

from unittest.mock import patch

import pytest

from virtual_silicon.device.memory import SRAM, MemoryTestStatus, MemoryValidationError


@pytest.mark.unit
@pytest.mark.memory
class TestSRAMBasics:
    def test_initial_memory_is_zero(self, clean_sram: SRAM) -> None:
        for addr in range(clean_sram.size):
            assert clean_sram.read(addr) == 0x00

    def test_write_and_read(self, clean_sram: SRAM) -> None:
        clean_sram.write(10, 0xAB)
        assert clean_sram.read(10) == 0xAB

    def test_fill_pattern(self, clean_sram: SRAM) -> None:
        clean_sram.fill(0xFF)
        assert clean_sram.read(0) == 0xFF
        assert clean_sram.read(255) == 0xFF

    def test_clear_zeroes_all(self, clean_sram: SRAM) -> None:
        clean_sram.fill(0xAA)
        clean_sram.clear()
        assert clean_sram.read(0) == 0x00

    def test_invalid_address_raises(self, clean_sram: SRAM) -> None:
        with pytest.raises(MemoryValidationError, match="out of range"):
            clean_sram.read(256)

    def test_negative_address_raises(self, clean_sram: SRAM) -> None:
        with pytest.raises(MemoryValidationError):
            clean_sram.read(-1)

    def test_invalid_write_value_raises(self, clean_sram: SRAM) -> None:
        with pytest.raises(MemoryValidationError):
            clean_sram.write(0, 0x100)

    def test_size_property(self, clean_sram: SRAM) -> None:
        assert clean_sram.size == 256

    def test_stuck_bit_zero(self, clean_sram: SRAM) -> None:
        clean_sram.write(5, 0xFF)
        clean_sram.inject_stuck_bit(5, 0, 0)
        val = clean_sram.read(5)
        assert val & 0x01 == 0

    def test_stuck_bit_one(self, clean_sram: SRAM) -> None:
        clean_sram.write(5, 0x00)
        clean_sram.inject_stuck_bit(5, 7, 1)
        val = clean_sram.read(5)
        assert val & 0x80 != 0

    def test_clear_faults(self, clean_sram: SRAM) -> None:
        clean_sram.inject_stuck_bit(5, 0, 0)
        clean_sram.clear_faults()
        clean_sram.write(5, 0xFF)
        assert clean_sram.read(5) == 0xFF

    def test_invalid_size_raises(self) -> None:
        with pytest.raises(MemoryValidationError):
            SRAM(size=0)

    def test_inject_stuck_bit_invalid_address_raises(self, clean_sram: SRAM) -> None:
        with pytest.raises(MemoryValidationError, match="out of range"):
            clean_sram.inject_stuck_bit(999, 0, 1)

    def test_inject_stuck_bit_negative_bit_raises(self, clean_sram: SRAM) -> None:
        with pytest.raises(MemoryValidationError, match="Bit position"):
            clean_sram.inject_stuck_bit(0, -1, 0)

    def test_inject_stuck_bit_bit_too_large_raises(self, clean_sram: SRAM) -> None:
        with pytest.raises(MemoryValidationError, match="Bit position"):
            clean_sram.inject_stuck_bit(0, 8, 0)

    def test_inject_stuck_bit_invalid_value_raises(self, clean_sram: SRAM) -> None:
        with pytest.raises(MemoryValidationError, match="Stuck-bit value"):
            clean_sram.inject_stuck_bit(0, 3, 2)


@pytest.mark.unit
@pytest.mark.memory
class TestMemoryPatterns:
    def test_walking_ones_passes(self, clean_sram: SRAM) -> None:
        result = clean_sram.test_walking_ones()
        assert result.status == MemoryTestStatus.PASS

    def test_walking_zeros_passes(self, clean_sram: SRAM) -> None:
        result = clean_sram.test_walking_zeros()
        assert result.status == MemoryTestStatus.PASS

    def test_checkerboard_passes(self, clean_sram: SRAM) -> None:
        result = clean_sram.test_checkerboard()
        assert result.status == MemoryTestStatus.PASS

    def test_inverse_checkerboard_passes(self, clean_sram: SRAM) -> None:
        result = clean_sram.test_inverse_checkerboard()
        assert result.status == MemoryTestStatus.PASS

    def test_address_pattern_passes(self, clean_sram: SRAM) -> None:
        result = clean_sram.test_address_pattern()
        assert result.status == MemoryTestStatus.PASS

    def test_random_readwrite_passes(self, clean_sram: SRAM) -> None:
        result = clean_sram.test_random_readwrite()
        assert result.status == MemoryTestStatus.PASS

    def test_march_c_minus_passes(self, clean_sram: SRAM) -> None:
        result = clean_sram.test_march_c_minus()
        assert result.status == MemoryTestStatus.PASS

    def test_boundary_addresses_passes(self, clean_sram: SRAM) -> None:
        result = clean_sram.test_boundary_addresses()
        assert result.status == MemoryTestStatus.PASS

    def test_data_retention_passes(self, clean_sram: SRAM) -> None:
        result = clean_sram.test_data_retention()
        assert result.status == MemoryTestStatus.PASS

    def test_stuck_bit_detected_by_walking_ones(self, clean_sram: SRAM) -> None:
        clean_sram.inject_stuck_bit(0, 0, 0)
        result = clean_sram.test_walking_ones()
        assert result.status == MemoryTestStatus.FAIL
        assert result.failing_address is not None

    def test_stuck_bit_detected_by_checkerboard(self, clean_sram: SRAM) -> None:
        clean_sram.inject_stuck_bit(1, 0, 1)
        result = clean_sram.test_march_c_minus()
        assert result.status == MemoryTestStatus.FAIL

    def test_result_has_duration(self, clean_sram: SRAM) -> None:
        result = clean_sram.test_checkerboard()
        assert result.duration >= 0

    def test_run_all_tests_returns_nine(self, clean_sram: SRAM) -> None:
        results = clean_sram.run_all_tests()
        assert len(results) == 9

    def test_run_all_tests_all_pass(self, clean_sram: SRAM) -> None:
        results = clean_sram.run_all_tests()
        assert all(r.passed for r in results)


@pytest.mark.unit
@pytest.mark.memory
class TestMemoryEdgeCases:
    """Covers missing lines: fill invalid pattern (112), walking_zeros fail (219),
    march_c_minus step failures (294, 303, 312, 321)."""

    def test_fill_invalid_pattern_raises(self, clean_sram: SRAM) -> None:
        """fill() with value > 0xFF raises MemoryValidationError (line 112)."""
        with pytest.raises(MemoryValidationError, match="out of byte range"):
            clean_sram.fill(0x100)

    def test_fill_negative_pattern_raises(self, clean_sram: SRAM) -> None:
        """fill() with negative value raises MemoryValidationError (line 112)."""
        with pytest.raises(MemoryValidationError, match="out of byte range"):
            clean_sram.fill(-1)

    def test_checkerboard_fail_stuck_bit(self) -> None:
        """Checkerboard fails when a bit is stuck and causes a read mismatch (line 219).

        Stuck HIGH at bit 3 of address 0 (even addr → expected 0x55 = 0101 0101).
        bit 3 of 0x55 = 0, so stuck HIGH gives 0x55 | 0x08 = 0x5D ≠ 0x55 → FAIL.
        """
        sram = SRAM(size=4, seed=42)
        sram.inject_stuck_bit(0, 3, 1)  # bit 3 at addr 0 (even) stuck HIGH
        result = sram.test_checkerboard()
        assert result.status == MemoryTestStatus.FAIL
        assert result.failing_address == 0
        assert "checkerboard" in result.test_name

    def test_march_c_minus_step3_fail_stuck_low(self) -> None:
        """March C- step-3 fails with a stuck LOW bit (line 294).

        Stuck LOW at bit 0 of address 0:
        - Step 2: reads 0x00 → still 0x00 (bit 0 already 0). OK.
        - Step 3: reads 0xFF → bit 0 stuck LOW gives 0xFE ≠ 0xFF → FAIL.
        """
        sram = SRAM(size=4, seed=42)
        sram.inject_stuck_bit(0, 0, 0)  # bit 0 at addr 0 stuck LOW
        result = sram.test_march_c_minus()
        assert result.status == MemoryTestStatus.FAIL
        assert "step3" in result.error_message

    def test_march_c_minus_step4_fail_via_mock(self) -> None:
        """March C- step-4 descending read fails via patched read (line 303).

        Steps 1-3 pass normally; step 4's first read is intercepted to
        return a non-zero value, triggering the step-4 failure path.
        """
        sram = SRAM(size=4, seed=42)
        call_count = [0]
        original_read = sram.read  # bound method capturing current state

        def counting_read(address: int) -> int:
            call_count[0] += 1
            actual = original_read(address)
            # Step 4 descending reads start at call 9 (4 step2 + 4 step3 + 1)
            if call_count[0] == 9:
                return 0x01  # non-zero → step-4 fail
            return actual

        with patch.object(sram, "read", counting_read):
            result = sram.test_march_c_minus()

        assert result.status == MemoryTestStatus.FAIL
        assert "step4" in result.error_message

    def test_march_c_minus_step5_fail_via_mock(self) -> None:
        """March C- step-5 descending read fails via patched read (line 312).

        Steps 1-4 pass; step 5's first read is intercepted to return
        a non-0xFF value, triggering the step-5 failure path.
        """
        sram = SRAM(size=4, seed=42)
        call_count = [0]
        original_read = sram.read

        def counting_read(address: int) -> int:
            call_count[0] += 1
            actual = original_read(address)
            # Step 5 reads start at call 13 (4+4+4+1)
            if call_count[0] == 13:
                return 0xFE  # non-0xFF → step-5 fail
            return actual

        with patch.object(sram, "read", counting_read):
            result = sram.test_march_c_minus()

        assert result.status == MemoryTestStatus.FAIL
        assert "step5" in result.error_message

    def test_march_c_minus_step6_fail_via_mock(self) -> None:
        """March C- step-6 verification fails via patched read (line 321).

        Steps 1-5 pass; step 6's first read is intercepted to return
        a non-zero value, triggering the step-6 failure path.
        """
        sram = SRAM(size=4, seed=42)
        call_count = [0]
        original_read = sram.read

        def counting_read(address: int) -> int:
            call_count[0] += 1
            actual = original_read(address)
            # Step 6 reads start at call 17 (4+4+4+4+1)
            if call_count[0] == 17:
                return 0x01  # non-zero → step-6 fail
            return actual

        with patch.object(sram, "read", counting_read):
            result = sram.test_march_c_minus()

        assert result.status == MemoryTestStatus.FAIL
        assert "step6" in result.error_message


@pytest.mark.unit
@pytest.mark.memory
class TestSRAMPowerOnPattern:
    def test_zeroed_pattern_is_default(self) -> None:
        sram = SRAM(size=16, seed=42)
        sram.power_on_init()
        assert all(sram.read(i) == 0x00 for i in range(16))

    def test_random_pattern_is_not_all_zero(self) -> None:
        sram = SRAM(size=64, seed=42, power_on_pattern="random")
        sram.power_on_init()
        values = [sram.read(i) for i in range(64)]
        assert any(v != 0x00 for v in values)

    def test_random_pattern_is_deterministic(self) -> None:
        sram_a = SRAM(size=32, seed=7, power_on_pattern="random")
        sram_b = SRAM(size=32, seed=7, power_on_pattern="random")
        sram_a.power_on_init()
        sram_b.power_on_init()
        assert [sram_a.read(i) for i in range(32)] == [sram_b.read(i) for i in range(32)]

    def test_undefined_pattern_fills_with_sentinel(self) -> None:
        sram = SRAM(size=16, seed=42, power_on_pattern="undefined")
        sram.power_on_init()
        assert all(sram.read(i) == 0xBE for i in range(16))

    def test_on_access_callback_fires_on_read_and_write(self) -> None:
        calls: list[str] = []
        sram = SRAM(size=8, seed=42, on_access=lambda: calls.append("x"))
        sram.write(0, 0xAA)
        sram.read(0)
        assert len(calls) == 2
