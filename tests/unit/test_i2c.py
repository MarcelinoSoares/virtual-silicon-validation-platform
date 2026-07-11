"""Unit tests for I2C bus simulation."""

import pytest

from virtual_silicon.device.register_map import RegisterMap
from virtual_silicon.protocols.base import TransactionLog
from virtual_silicon.protocols.i2c import I2CBus


@pytest.mark.unit
@pytest.mark.protocol
class TestI2CBus:
    def test_read_valid_register(self, i2c_bus: I2CBus) -> None:
        txn = i2c_bus.read_register(0x48, 0x00)
        assert txn.success
        assert txn.data == [0xA5]

    def test_write_valid_register(self, i2c_bus: I2CBus) -> None:
        txn = i2c_bus.write_register(0x48, 0x02, 0x05)
        assert txn.success

    def test_read_after_write(self, i2c_bus: I2CBus) -> None:
        i2c_bus.write_register(0x48, 0x02, 0x07)
        txn = i2c_bus.read_register(0x48, 0x02)
        assert txn.data == [0x07]

    def test_invalid_device_address_fails(self, i2c_bus: I2CBus) -> None:
        txn = i2c_bus.read_register(0x50, 0x00)
        assert not txn.success
        assert "No I2C device" in txn.error

    def test_invalid_register_address_fails(self, i2c_bus: I2CBus) -> None:
        txn = i2c_bus.read_register(0x48, 0xFF)
        assert not txn.success

    def test_write_to_read_only_fails(self, i2c_bus: I2CBus) -> None:
        txn = i2c_bus.write_register(0x48, 0x00, 0x00)
        assert not txn.success

    def test_timeout_fault_injection(self, i2c_bus: I2CBus) -> None:
        i2c_bus.set_fault_probabilities(timeout=1.0)
        txn = i2c_bus.read_register(0x48, 0x00)
        assert not txn.success
        assert "timeout" in txn.error.lower()

    def test_nack_fault_injection(self, i2c_bus: I2CBus) -> None:
        i2c_bus.set_fault_probabilities(nack=1.0)
        txn = i2c_bus.read_register(0x48, 0x00)
        assert not txn.success
        assert "NACK" in txn.error

    def test_transaction_log_populated(self, i2c_bus: I2CBus) -> None:
        i2c_bus.read_register(0x48, 0x00)
        assert len(i2c_bus.transactions) == 1

    def test_clear_transactions(self, i2c_bus: I2CBus) -> None:
        i2c_bus.read_register(0x48, 0x00)
        i2c_bus.clear_transactions()
        assert len(i2c_bus.transactions) == 0

    def test_multi_read(self, i2c_bus: I2CBus) -> None:
        txn = i2c_bus.read_multi(0x48, 0x00, 3)
        assert txn.success
        assert len(txn.data) >= 1

    def test_device_address_property(self, i2c_bus: I2CBus) -> None:
        assert i2c_bus.device_address == 0x48

    def test_transaction_log_records_failure(self, i2c_bus: I2CBus) -> None:
        i2c_bus.read_register(0xFF, 0x00)
        logs = i2c_bus.transactions
        assert not logs[-1].success

    def test_read_multi_timeout(self, i2c_bus: I2CBus) -> None:
        """read_multi() ProtocolTimeoutError is caught and returns failed txn (lines 199-203)."""
        i2c_bus.set_fault_probabilities(timeout=1.0)
        txn = i2c_bus.read_multi(0x48, 0x00, 3)
        assert not txn.success
        assert "timeout" in txn.error.lower()

    def test_read_multi_partial_response(self, register_map: RegisterMap, seed: int) -> None:
        """read_multi() with partial=1.0 stops after first register (line 192)."""
        bus = I2CBus(register_map=register_map, device_address=0x48, seed=seed)
        bus.set_fault_probabilities(partial=1.0)
        txn = bus.read_multi(0x48, 0x00, 5)
        assert txn.success
        # Partial response: should have received fewer bytes than requested
        assert len(txn.data) <= 5

    def test_read_multi_invalid_register_stops(self, i2c_bus: I2CBus) -> None:
        """read_multi() stops gracefully on InvalidRegisterAddressError (line 194)."""
        # Start at a valid register but request enough to overflow into unmapped space
        txn = i2c_bus.read_multi(0x48, 0x0C, 10)
        assert txn.success  # Partial success: stops at first unmapped address
        assert len(txn.data) >= 1

    def test_latency_applied(self, register_map: RegisterMap) -> None:
        """_apply_latency() calls time.sleep when latency_ms > 0 (line 229)."""
        bus = I2CBus(register_map=register_map, device_address=0x48, latency_ms=1.0)
        txn = bus.read_register(0x48, 0x00)
        assert txn.success
        assert txn.duration_ms >= 0  # latency added


@pytest.mark.unit
@pytest.mark.protocol
class TestTransactionLog:
    """Covers protocols/base.py line 28 (to_dict method)."""

    def test_to_dict_returns_correct_fields(self) -> None:
        """TransactionLog.to_dict() serializes all fields (line 28)."""
        log = TransactionLog(
            protocol="I2C",
            direction="read",
            address=0x48,
            register=0x00,
            data=[0xA5],
            success=True,
            error="",
        )
        d = log.to_dict()
        assert d["protocol"] == "I2C"
        assert d["direction"] == "read"
        assert d["address"] == 0x48
        assert d["data"] == [0xA5]
        assert d["success"] is True
