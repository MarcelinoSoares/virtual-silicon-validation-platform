"""SPI bus simulation with full-duplex transactions, fault injection, and logging."""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass

from virtual_silicon.device.register import InvalidRegisterAddressError, RegisterAccessError
from virtual_silicon.device.register_map import RegisterMap
from virtual_silicon.protocols.base import ProtocolTimeoutError, TransactionLog

logger = logging.getLogger(__name__)

SPI_CMD_READ = 0x80
SPI_CMD_WRITE = 0x00


@dataclass
class SPITransaction:
    """Result of a single SPI transaction."""

    command: int
    register: int
    tx_data: list[int]
    rx_data: list[int]
    success: bool
    error: str = ""
    duration_ms: float = 0.0
    clock_hz: int = 1_000_000


class SPIBus:
    """Virtual SPI bus with full-duplex simulation, command/payload structure, and fault injection.

    Configurable clock frequency, transfer size, invalid command handling,
    timeout and corrupted response simulation, and transaction logging.
    """

    def __init__(
        self,
        register_map: RegisterMap,
        clock_hz: int = 1_000_000,
        latency_ms: float = 0.0,
        seed: int | None = None,
    ) -> None:
        """Initialize the SPI bus.

        Args:
            register_map: The chip's register map.
            clock_hz: Simulated SPI clock frequency in Hz.
            latency_ms: Simulated transaction latency in milliseconds.
            seed: Random seed for fault injection.
        """
        self._register_map = register_map
        self._clock_hz = clock_hz
        self._latency_ms = latency_ms
        self._rng = random.Random(seed)
        self._transactions: list[TransactionLog] = []
        self._timeout_probability: float = 0.0
        self._corruption_probability: float = 0.0
        logger.info("SPIBus initialized. Clock=%dHz.", clock_hz)

    @property
    def clock_hz(self) -> int:
        """Configured SPI clock frequency."""
        return self._clock_hz

    @property
    def transactions(self) -> list[TransactionLog]:
        """List of logged transactions."""
        return list(self._transactions)

    def set_fault_probabilities(self, timeout: float = 0.0, corruption: float = 0.0) -> None:
        """Configure fault injection probabilities.

        Args:
            timeout: Probability of timeout fault (0.0–1.0).
            corruption: Probability of response corruption (0.0–1.0).
        """
        self._timeout_probability = max(0.0, min(1.0, timeout))
        self._corruption_probability = max(0.0, min(1.0, corruption))

    def transfer(self, command: int, register_address: int, data: int = 0x00) -> SPITransaction:
        """Perform a full-duplex SPI transfer.

        Args:
            command: SPI_CMD_READ (0x80) or SPI_CMD_WRITE (0x00).
            register_address: Target register address.
            data: Data byte for write operations (ignored for reads).

        Returns:
            SPITransaction result.
        """
        start = time.monotonic()
        direction = "read" if command == SPI_CMD_READ else "write"
        log = TransactionLog(
            protocol="SPI",
            direction=direction,
            address=self._clock_hz,
            register=register_address,
            data=[data],
        )
        try:
            self._validate_command(command)
            self._simulate_faults(direction)
            self._apply_latency()

            if command == SPI_CMD_READ:
                value = self._register_map.read(register_address)
                if self._rng.random() < self._corruption_probability:
                    value = self._rng.randint(0, 0xFF)
                    log.success = False
                    log.error = "Corrupted SPI response (simulated)."
                    duration = (time.monotonic() - start) * 1000
                    return SPITransaction(
                        command,
                        register_address,
                        [0x00],
                        [value],
                        False,
                        log.error,
                        duration,
                        self._clock_hz,
                    )
                log.data = [value]
                log.success = True
                duration = (time.monotonic() - start) * 1000
                logger.debug("SPI read reg=0x%02X → 0x%02X", register_address, value)
                return SPITransaction(
                    command,
                    register_address,
                    [0x00],
                    [value],
                    True,
                    duration_ms=duration,
                    clock_hz=self._clock_hz,
                )
            else:
                self._register_map.write(register_address, data)
                log.success = True
                duration = (time.monotonic() - start) * 1000
                logger.debug("SPI write reg=0x%02X ← 0x%02X", register_address, data)
                return SPITransaction(
                    command,
                    register_address,
                    [data],
                    [0x00],
                    True,
                    duration_ms=duration,
                    clock_hz=self._clock_hz,
                )

        except (ProtocolTimeoutError, InvalidRegisterAddressError, RegisterAccessError) as exc:
            log.success = False
            log.error = str(exc)
            duration = (time.monotonic() - start) * 1000
            logger.warning("SPI transfer failed: %s", exc)
            return SPITransaction(
                command, register_address, [data], [], False, str(exc), duration, self._clock_hz
            )
        finally:
            self._transactions.append(log)

    def read_register(self, register_address: int) -> SPITransaction:
        """Convenience method: SPI register read."""
        return self.transfer(SPI_CMD_READ, register_address)

    def write_register(self, register_address: int, data: int) -> SPITransaction:
        """Convenience method: SPI register write."""
        return self.transfer(SPI_CMD_WRITE, register_address, data)

    def bulk_read(self, start_register: int, count: int) -> list[SPITransaction]:
        """Read multiple registers sequentially via SPI.

        Args:
            start_register: First register address.
            count: Number of registers to read.

        Returns:
            List of SPITransaction results.
        """
        results = []
        for offset in range(count):
            txn = self.read_register(start_register + offset)
            results.append(txn)
            if not txn.success:
                break
        return results

    def clear_transactions(self) -> None:
        """Clear the transaction log."""
        self._transactions.clear()

    def _validate_command(self, command: int) -> None:
        if command not in (SPI_CMD_READ, SPI_CMD_WRITE):
            raise RegisterAccessError(
                f"Invalid SPI command: 0x{command:02X}. Expected 0x80 (read) or 0x00 (write)."
            )

    def _simulate_faults(self, operation: str) -> None:
        if self._rng.random() < self._timeout_probability:
            raise ProtocolTimeoutError(
                f"SPI {operation} timeout (simulated, probability={self._timeout_probability:.2f})."
            )

    def _apply_latency(self) -> None:
        if self._latency_ms > 0:
            time.sleep(self._latency_ms / 1000.0)
