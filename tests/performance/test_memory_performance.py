"""Performance tests for SRAM operations and memory test patterns."""

import time

import pytest

from virtual_silicon.device.memory import SRAM


@pytest.mark.performance
class TestMemoryPerformance:
    def test_walking_ones_completes_under_1_second(self, clean_sram: SRAM) -> None:
        start = time.monotonic()
        result = clean_sram.test_walking_ones()
        duration = time.monotonic() - start
        assert result.passed
        assert duration < 1.0, f"Walking ones too slow: {duration:.3f}s"

    def test_march_c_minus_completes_under_2_seconds(self, clean_sram: SRAM) -> None:
        start = time.monotonic()
        result = clean_sram.test_march_c_minus()
        duration = time.monotonic() - start
        assert result.passed
        assert duration < 2.0, f"March C- too slow: {duration:.3f}s"

    def test_random_rw_completes_under_1_second(self, clean_sram: SRAM) -> None:
        start = time.monotonic()
        result = clean_sram.test_random_readwrite()
        duration = time.monotonic() - start
        assert result.passed
        assert duration < 1.0, f"Random RW too slow: {duration:.3f}s"

    def test_all_tests_complete_under_10_seconds(self, clean_sram: SRAM) -> None:
        start = time.monotonic()
        results = clean_sram.run_all_tests()
        duration = time.monotonic() - start
        assert duration < 10.0, f"Full suite too slow: {duration:.3f}s"
        assert all(r.passed for r in results)

    def test_sequential_write_throughput(self, clean_sram: SRAM) -> None:
        start = time.monotonic()
        for addr in range(256):
            clean_sram.write(addr, addr & 0xFF)
        duration = time.monotonic() - start
        assert duration < 0.1, f"Sequential write too slow: {duration:.6f}s"

    def test_sequential_read_throughput(self, clean_sram: SRAM) -> None:
        clean_sram.fill(0xAA)
        start = time.monotonic()
        for addr in range(256):
            _ = clean_sram.read(addr)
        duration = time.monotonic() - start
        assert duration < 0.1, f"Sequential read too slow: {duration:.6f}s"

    def test_large_sram_scales_linearly(self) -> None:
        large_sram = SRAM(size=4096, seed=42)
        start = time.monotonic()
        result = large_sram.test_checkerboard()
        duration = time.monotonic() - start
        assert result.passed
        assert duration < 5.0, f"Large SRAM checkerboard too slow: {duration:.3f}s"
