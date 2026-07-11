"""I2C bus simulation with addressing, faults, and transaction logging."""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field

from virtual_silicon.device.byte_order import ByteOrder, serialize_register
from virtual_silicon.device.register import InvalidRegisterAddressError, RegisterAccessError
from virtual_silicon.exceptions import I2CDeviceAddressError
from virtual_silicon.protocols.base import ProtocolTimeoutError, RegisterDevice, TransactionLog

logger = logging.getLogger(__name__)


@dataclass
class I2CTransaction:
    """Result of a single I2C transaction."""

    address: int
    register: int
    data: list[int]
    direction: str
    success: bool
    error: str = ""
    duration_ms: float = 0.0
    requested_count: int = 0
    transferred_count: int = field(init=False)

    def __post_init__(self) -> None:
        self.transferred_count = len(self.data)


class I2CBus:
    """Virtual I2C bus supporting device addressing, multi-byte ops, and fault injection.

    Simulates a real I2C bus with configurable device address, latency,
    NACK injection, timeout injection, and partial-response simulation.
    """

    DEFAULT_DEVICE_ADDRESS = 0x48

    def __init__(
        self,
        register_map: RegisterDevice,
        device_address: int = DEFAULT_DEVICE_ADDRESS,
        latency_ms: float = 0.0,
        seed: int | None = None,
        byte_order: ByteOrder = ByteOrder.BIG,
    ) -> None:
        """Initialize the I2C bus.

        Args:
            register_map: Device backing the register space (VirtualChip or RegisterMap).
            device_address: 7-bit I2C device address.
            latency_ms: Simulated transaction latency in milliseconds.
            seed: Random seed for fault probability.
            byte_order: Byte order for serializing 16-bit register values (default: BIG).
        """
        self._device = register_map
        self._device_address = device_address
        self._latency_ms = latency_ms
        self._rng = random.Random(seed)
        self._byte_order = byte_order
        self._transactions: list[TransactionLog] = []
        self._timeout_probability: float = 0.0
        self._nack_probability: float = 0.0
        self._partial_probability: float = 0.0
        logger.info("I2CBus initialized at address 0x%02X.", device_address)

    @property
    def device_address(self) -> int:
        """The device I2C address."""
        return self._device_address

    @property
    def transactions(self) -> list[TransactionLog]:
        """List of all logged transactions."""
        return list(self._transactions)

    def set_fault_probabilities(
        self,
        timeout: float = 0.0,
        nack: float = 0.0,
        partial: float = 0.0,
    ) -> None:
        """Configure fault injection probabilities.

        Args:
            timeout: Probability of timeout (0.0–1.0).
            nack: Probability of NACK (0.0–1.0).
            partial: Probability of partial response (0.0–1.0).
        """
        self._timeout_probability = max(0.0, min(1.0, timeout))
        self._nack_probability = max(0.0, min(1.0, nack))
        self._partial_probability = max(0.0, min(1.0, partial))

    def read_register(self, device_address: int, register_address: int) -> I2CTransaction:
        """Perform an I2C register read transaction.

        Args:
            device_address: Target device address.
            register_address: Register to read.

        Returns:
            I2CTransaction result.
        """
        start = time.monotonic()
        log = TransactionLog(
            protocol="I2C",
            direction="read",
            address=device_address,
            register=register_address,
        )
        try:
            self._validate_address(device_address)
            self._simulate_faults("read")
            self._apply_latency()
            value = self._device.read_register(register_address)
            data = serialize_register(value, self._byte_order)
            log.data = data
            log.success = True
            duration = (time.monotonic() - start) * 1000
            logger.debug(
                "I2C read 0x%02X[0x%02X] = 0x%04X", device_address, register_address, value
            )
            return I2CTransaction(
                device_address, register_address, data, "read", True, duration_ms=duration
            )
        except (
            ProtocolTimeoutError,
            I2CDeviceAddressError,
            InvalidRegisterAddressError,
            RegisterAccessError,
        ) as exc:
            log.success = False
            log.error = str(exc)
            duration = (time.monotonic() - start) * 1000
            logger.warning("I2C read failed: %s", exc)
            return I2CTransaction(
                device_address, register_address, [], "read", False, str(exc), duration
            )
        finally:
            self._transactions.append(log)

    def write_register(
        self, device_address: int, register_address: int, value: int
    ) -> I2CTransaction:
        """Perform an I2C register write transaction.

        Args:
            device_address: Target device address.
            register_address: Register to write.
            value: Value to write.

        Returns:
            I2CTransaction result.
        """
        start = time.monotonic()
        log = TransactionLog(
            protocol="I2C",
            direction="write",
            address=device_address,
            register=register_address,
            data=[value],
        )
        try:
            self._validate_address(device_address)
            self._simulate_faults("write")
            self._apply_latency()
            self._device.write_register(register_address, value)
            log.success = True
            duration = (time.monotonic() - start) * 1000
            logger.debug(
                "I2C write 0x%02X[0x%02X] = 0x%02X", device_address, register_address, value
            )
            return I2CTransaction(
                device_address, register_address, [value], "write", True, duration_ms=duration
            )
        except (
            ProtocolTimeoutError,
            I2CDeviceAddressError,
            InvalidRegisterAddressError,
            RegisterAccessError,
        ) as exc:
            log.success = False
            log.error = str(exc)
            duration = (time.monotonic() - start) * 1000
            logger.warning("I2C write failed: %s", exc)
            return I2CTransaction(
                device_address, register_address, [], "write", False, str(exc), duration
            )
        finally:
            self._transactions.append(log)

    def read_multi(self, device_address: int, start_register: int, count: int) -> I2CTransaction:
        """Read multiple consecutive registers via I2C.

        Args:
            device_address: Target device address.
            start_register: First register address.
            count: Number of registers to read.

        Returns:
            I2CTransaction with multi-byte data.
        """
        start = time.monotonic()
        log = TransactionLog(
            protocol="I2C",
            direction="read_multi",
            address=device_address,
            register=start_register,
        )
        try:
            self._validate_address(device_address)
            self._simulate_faults("read_multi")
            self._apply_latency()
            data: list[int] = []
            registers_read = 0
            for offset in range(count):
                try:
                    val = self._device.read_register(start_register + offset)
                    data.extend(serialize_register(val, self._byte_order))
                    registers_read += 1
                    if self._rng.random() < self._partial_probability:
                        break
                except InvalidRegisterAddressError:
                    break
            success = registers_read == count
            log.data = data
            log.success = success
            duration = (time.monotonic() - start) * 1000
            return I2CTransaction(
                device_address,
                start_register,
                data,
                "read_multi",
                success,
                duration_ms=duration,
                requested_count=count,
            )
        except (ProtocolTimeoutError, RegisterAccessError) as exc:
            log.success = False
            log.error = str(exc)
            duration = (time.monotonic() - start) * 1000
            return I2CTransaction(
                device_address,
                start_register,
                [],
                "read_multi",
                False,
                str(exc),
                duration,
                requested_count=count,
            )
        finally:
            self._transactions.append(log)

    def clear_transactions(self) -> None:
        """Clear the transaction log."""
        self._transactions.clear()

    def _validate_address(self, address: int) -> None:
        if address != self._device_address:
            raise I2CDeviceAddressError(
                f"No I2C device at address 0x{address:02X}. Expected 0x{self._device_address:02X}."
            )

    def _simulate_faults(self, operation: str) -> None:
        if self._rng.random() < self._timeout_probability:
            raise ProtocolTimeoutError(
                f"I2C {operation} timeout (simulated, probability={self._timeout_probability:.2f})."
            )
        if self._rng.random() < self._nack_probability:
            raise RegisterAccessError(f"I2C NACK received during {operation} (simulated).")

    def _apply_latency(self) -> None:
        if self._latency_ms > 0:
            time.sleep(self._latency_ms / 1000.0)
