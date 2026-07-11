"""SRAM simulation with comprehensive memory test patterns."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from virtual_silicon.exceptions import MemoryValidationError

logger = logging.getLogger(__name__)

__all__ = ["MemoryTestResult", "MemoryTestStatus", "MemoryValidationError", "SRAM"]


class MemoryTestStatus(Enum):
    """Memory test result status."""

    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"


@dataclass
class MemoryTestResult:
    """Structured result from a memory test operation."""

    test_name: str
    status: MemoryTestStatus
    start_time: float
    duration: float
    failing_address: int | None = None
    expected_value: int | None = None
    actual_value: int | None = None
    error_message: str = ""

    @property
    def passed(self) -> bool:
        """Return True if the test passed."""
        return self.status == MemoryTestStatus.PASS


class SRAM:
    """Virtual SRAM with configurable size and full memory test suite.

    Implements Walking Ones/Zeros, Checkerboard, Address Pattern,
    Random read/write, March C-, boundary tests, and data retention simulation.
    """

    def __init__(
        self,
        size: int = 256,
        seed: int | None = None,
        power_on_pattern: Literal["zeroed", "random", "undefined"] = "zeroed",
        on_access: Callable[[], None] | None = None,
    ) -> None:
        """Initialize virtual SRAM.

        Args:
            size: Memory size in bytes (default 256).
            seed: Random seed for deterministic test execution.
            power_on_pattern: Initial SRAM state on power-on. "zeroed" fills with 0x00,
                "random" fills with pseudorandom bytes (seeded), "undefined" fills with 0xBE.
            on_access: Optional callback invoked on every read or write, used for cycle counting.
        """
        if size <= 0:
            raise MemoryValidationError(f"SRAM size must be positive, got {size}.")
        self._size = size
        self._memory: list[int] = [0x00] * size
        self._seed = seed
        self._rng = random.Random(seed)
        self._stuck_bits: dict[int, dict[int, int]] = {}
        self._power_on_pattern = power_on_pattern
        self._on_access = on_access
        logger.info("Initialized SRAM with %d bytes.", size)

    @property
    def size(self) -> int:
        """SRAM size in bytes."""
        return self._size

    def read(self, address: int) -> int:
        """Read a byte from SRAM.

        Args:
            address: Memory address (0 to size-1).

        Returns:
            Byte value at address.

        Raises:
            MemoryValidationError: If address is out of range.
        """
        self._validate_address(address)
        if self._on_access:
            self._on_access()
        value = self._memory[address]
        value = self._apply_stuck_bits(address, value)
        return value

    def write(self, address: int, value: int) -> None:
        """Write a byte to SRAM.

        Args:
            address: Memory address (0 to size-1).
            value: Byte value to write (0-255).

        Raises:
            MemoryValidationError: If address is out of range or value invalid.
        """
        self._validate_address(address)
        if value < 0 or value > 0xFF:
            raise MemoryValidationError(f"Value 0x{value:X} out of byte range.")
        if self._on_access:
            self._on_access()
        self._memory[address] = value

    def fill(self, pattern: int) -> None:
        """Fill all memory with a single byte pattern.

        Args:
            pattern: Byte value to fill (0-255).
        """
        if pattern < 0 or pattern > 0xFF:
            raise MemoryValidationError(f"Fill pattern 0x{pattern:X} out of byte range.")
        for i in range(self._size):
            self._memory[i] = pattern

    def clear(self) -> None:
        """Clear all memory to zero."""
        self._memory = [0x00] * self._size

    def power_on_init(self) -> None:
        """Initialize SRAM according to the configured power_on_pattern.

        "zeroed" fills with 0x00 (deterministic, simplifies test setup).
        "random" fills with pseudorandom bytes using the configured seed.
        "undefined" fills with 0xBE, approximating real SRAM whose state is unpredictable.
        """
        if self._power_on_pattern == "random":
            rng = random.Random(self._seed)
            self._memory = [rng.randint(0, 0xFF) for _ in range(self._size)]
        elif self._power_on_pattern == "undefined":
            self._memory = [0xBE] * self._size
        else:
            self._memory = [0x00] * self._size

    def inject_stuck_bit(self, address: int, bit: int, value: int) -> None:
        """Inject a stuck bit fault at the specified address.

        Args:
            address: Target memory address.
            bit: Bit position (0-7).
            value: Stuck value (0 or 1).

        Raises:
            MemoryValidationError: If address, bit, or value is out of range.
        """
        self._validate_address(address)
        if not 0 <= bit <= 7:
            raise MemoryValidationError(f"Bit position must be 0–7, got {bit}.")
        if value not in (0, 1):
            raise MemoryValidationError(f"Stuck-bit value must be 0 or 1, got {value}.")
        if address not in self._stuck_bits:
            self._stuck_bits[address] = {}
        self._stuck_bits[address][bit] = value
        logger.warning("Stuck bit injected at address %d, bit %d = %d.", address, bit, value)

    def clear_faults(self) -> None:
        """Clear all injected faults."""
        self._stuck_bits.clear()

    def _apply_stuck_bits(self, address: int, value: int) -> int:
        """Apply stuck bit faults to a read value."""
        if address not in self._stuck_bits:
            return value
        for bit, stuck_val in self._stuck_bits[address].items():
            if stuck_val == 0:
                value &= ~(1 << bit)
            else:
                value |= 1 << bit
        return value

    def _validate_address(self, address: int) -> None:
        if address < 0 or address >= self._size:
            raise MemoryValidationError(f"Address {address} out of range [0, {self._size - 1}].")

    def _make_result(
        self,
        test_name: str,
        start_time: float,
        status: MemoryTestStatus = MemoryTestStatus.PASS,
        failing_address: int | None = None,
        expected: int | None = None,
        actual: int | None = None,
        error_message: str = "",
    ) -> MemoryTestResult:
        return MemoryTestResult(
            test_name=test_name,
            status=status,
            start_time=start_time,
            duration=time.monotonic() - start_time,
            failing_address=failing_address,
            expected_value=expected,
            actual_value=actual,
            error_message=error_message,
        )

    def test_walking_ones(self) -> MemoryTestResult:
        """Walking ones test: write a single 1-bit walking through each bit position."""
        start = time.monotonic()
        self.clear()
        for addr in range(self._size):
            for bit in range(8):
                pattern = 1 << bit
                self.write(addr, pattern)
                read_back = self.read(addr)
                if read_back != pattern:
                    return self._make_result(
                        "walking_ones",
                        start,
                        MemoryTestStatus.FAIL,
                        addr,
                        pattern,
                        read_back,
                        f"Walking ones mismatch at 0x{addr:04X} bit {bit}.",
                    )
        return self._make_result("walking_ones", start)

    def test_walking_zeros(self) -> MemoryTestResult:
        """Walking zeros test: write a single 0-bit walking through each bit position."""
        start = time.monotonic()
        for addr in range(self._size):
            self.write(addr, 0xFF)
        for addr in range(self._size):
            for bit in range(8):
                pattern = (~(1 << bit)) & 0xFF
                self.write(addr, pattern)
                read_back = self.read(addr)
                if read_back != pattern:
                    return self._make_result(
                        "walking_zeros",
                        start,
                        MemoryTestStatus.FAIL,
                        addr,
                        pattern,
                        read_back,
                        f"Walking zeros mismatch at 0x{addr:04X} bit {bit}.",
                    )
        return self._make_result("walking_zeros", start)

    def test_checkerboard(self) -> MemoryTestResult:
        """Checkerboard test: alternating 0x55/0xAA patterns."""
        start = time.monotonic()
        for addr in range(self._size):
            self.write(addr, 0x55 if addr % 2 == 0 else 0xAA)
        for addr in range(self._size):
            expected = 0x55 if addr % 2 == 0 else 0xAA
            actual = self.read(addr)
            if actual != expected:
                return self._make_result(
                    "checkerboard",
                    start,
                    MemoryTestStatus.FAIL,
                    addr,
                    expected,
                    actual,
                    f"Checkerboard mismatch at 0x{addr:04X}.",
                )
        return self._make_result("checkerboard", start)

    def test_inverse_checkerboard(self) -> MemoryTestResult:
        """Inverse checkerboard: alternating 0xAA/0x55 patterns."""
        start = time.monotonic()
        for addr in range(self._size):
            self.write(addr, 0xAA if addr % 2 == 0 else 0x55)
        for addr in range(self._size):
            expected = 0xAA if addr % 2 == 0 else 0x55
            actual = self.read(addr)
            if actual != expected:
                return self._make_result(
                    "inverse_checkerboard",
                    start,
                    MemoryTestStatus.FAIL,
                    addr,
                    expected,
                    actual,
                    f"Inverse checkerboard mismatch at 0x{addr:04X}.",
                )
        return self._make_result("inverse_checkerboard", start)

    def test_address_pattern(self) -> MemoryTestResult:
        """Address pattern test: each cell stores its own address modulo 256."""
        start = time.monotonic()
        for addr in range(self._size):
            self.write(addr, addr & 0xFF)
        for addr in range(self._size):
            expected = addr & 0xFF
            actual = self.read(addr)
            if actual != expected:
                return self._make_result(
                    "address_pattern",
                    start,
                    MemoryTestStatus.FAIL,
                    addr,
                    expected,
                    actual,
                    f"Address pattern mismatch at 0x{addr:04X}.",
                )
        return self._make_result("address_pattern", start)

    def test_random_readwrite(self) -> MemoryTestResult:
        """Random read/write test using configured random seed."""
        start = time.monotonic()
        rng = random.Random(self._seed)
        expected_values: list[int] = [rng.randint(0, 255) for _ in range(self._size)]
        for addr, val in enumerate(expected_values):
            self.write(addr, val)
        for addr, expected in enumerate(expected_values):
            actual = self.read(addr)
            if actual != expected:
                return self._make_result(
                    "random_readwrite",
                    start,
                    MemoryTestStatus.FAIL,
                    addr,
                    expected,
                    actual,
                    f"Random RW mismatch at 0x{addr:04X}.",
                )
        return self._make_result("random_readwrite", start)

    def test_march_c_minus(self) -> MemoryTestResult:
        """Simplified March C- test for stuck-at and coupling faults."""
        start = time.monotonic()
        # Step 1: Fill 0
        for addr in range(self._size):
            self.write(addr, 0x00)
        # Step 2: ascending — read 0, write 1
        for addr in range(self._size):
            actual = self.read(addr)
            if actual != 0x00:
                return self._make_result(
                    "march_c_minus",
                    start,
                    MemoryTestStatus.FAIL,
                    addr,
                    0x00,
                    actual,
                    f"March C- step2 fail at 0x{addr:04X}.",
                )
            self.write(addr, 0xFF)
        # Step 3: ascending — read 1, write 0
        for addr in range(self._size):
            actual = self.read(addr)
            if actual != 0xFF:
                return self._make_result(
                    "march_c_minus",
                    start,
                    MemoryTestStatus.FAIL,
                    addr,
                    0xFF,
                    actual,
                    f"March C- step3 fail at 0x{addr:04X}.",
                )
            self.write(addr, 0x00)
        # Step 4: descending — read 0, write 1
        for addr in range(self._size - 1, -1, -1):
            actual = self.read(addr)
            if actual != 0x00:
                return self._make_result(
                    "march_c_minus",
                    start,
                    MemoryTestStatus.FAIL,
                    addr,
                    0x00,
                    actual,
                    f"March C- step4 fail at 0x{addr:04X}.",
                )
            self.write(addr, 0xFF)
        # Step 5: descending — read 1, write 0
        for addr in range(self._size - 1, -1, -1):
            actual = self.read(addr)
            if actual != 0xFF:
                return self._make_result(
                    "march_c_minus",
                    start,
                    MemoryTestStatus.FAIL,
                    addr,
                    0xFF,
                    actual,
                    f"March C- step5 fail at 0x{addr:04X}.",
                )
            self.write(addr, 0x00)
        # Step 6: verify all zero
        for addr in range(self._size):
            actual = self.read(addr)
            if actual != 0x00:
                return self._make_result(
                    "march_c_minus",
                    start,
                    MemoryTestStatus.FAIL,
                    addr,
                    0x00,
                    actual,
                    f"March C- step6 fail at 0x{addr:04X}.",
                )
        return self._make_result("march_c_minus", start)

    def test_boundary_addresses(self) -> MemoryTestResult:
        """Boundary test: exercises address 0, 1, size-2, and size-1."""
        start = time.monotonic()
        boundary_addrs = [0, 1, self._size - 2, self._size - 1]
        for addr in boundary_addrs:
            for pattern in [0x00, 0xFF, 0xA5, 0x5A]:
                self.write(addr, pattern)
                actual = self.read(addr)
                if actual != pattern:
                    return self._make_result(
                        "boundary_addresses",
                        start,
                        MemoryTestStatus.FAIL,
                        addr,
                        pattern,
                        actual,
                        f"Boundary test mismatch at 0x{addr:04X} pattern 0x{pattern:02X}.",
                    )
        return self._make_result("boundary_addresses", start)

    def test_data_retention(self, iterations: int = 3) -> MemoryTestResult:
        """Data retention simulation: write then repeatedly verify without re-writing."""
        start = time.monotonic()
        rng = random.Random(self._seed)
        data = [rng.randint(0, 255) for _ in range(self._size)]
        for addr, val in enumerate(data):
            self.write(addr, val)
        for _ in range(iterations):
            for addr, expected in enumerate(data):
                actual = self.read(addr)
                if actual != expected:
                    return self._make_result(
                        "data_retention",
                        start,
                        MemoryTestStatus.FAIL,
                        addr,
                        expected,
                        actual,
                        f"Data retention failure at 0x{addr:04X}.",
                    )
        return self._make_result("data_retention", start)

    def run_all_tests(self) -> list[MemoryTestResult]:
        """Run all memory tests and return list of results."""
        tests = [
            self.test_walking_ones,
            self.test_walking_zeros,
            self.test_checkerboard,
            self.test_inverse_checkerboard,
            self.test_address_pattern,
            self.test_random_readwrite,
            self.test_march_c_minus,
            self.test_boundary_addresses,
            self.test_data_retention,
        ]
        results: list[MemoryTestResult] = []
        for test_fn in tests:
            logger.info("Running memory test: %s", test_fn.__name__)
            result = test_fn()
            results.append(result)
            if not result.passed:
                logger.warning(
                    "Memory test FAILED: %s — %s", result.test_name, result.error_message
                )
        return results
