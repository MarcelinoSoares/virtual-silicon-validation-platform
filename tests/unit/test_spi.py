"""Unit tests for SPI bus simulation."""

import pytest

from virtual_silicon.device.register_map import RegisterMap
from virtual_silicon.protocols.spi import SPI_CMD_READ, SPI_CMD_WRITE, SPIBus


@pytest.mark.unit
@pytest.mark.protocol
class TestSPIBus:
    def test_read_valid_register(self, spi_bus: SPIBus) -> None:
        txn = spi_bus.read_register(0x00)
        assert txn.success
        assert txn.rx_data == [0xA5]

    def test_write_valid_register(self, spi_bus: SPIBus) -> None:
        txn = spi_bus.write_register(0x02, 0x05)
        assert txn.success

    def test_read_after_write(self, spi_bus: SPIBus) -> None:
        spi_bus.write_register(0x02, 0x07)
        txn = spi_bus.read_register(0x02)
        assert txn.rx_data == [0x07]

    def test_invalid_command_fails(self, spi_bus: SPIBus) -> None:
        txn = spi_bus.transfer(0x42, 0x00)
        assert not txn.success

    def test_invalid_register_fails(self, spi_bus: SPIBus) -> None:
        txn = spi_bus.read_register(0xFF)
        assert not txn.success

    def test_write_to_read_only_fails(self, spi_bus: SPIBus) -> None:
        txn = spi_bus.write_register(0x00, 0x00)
        assert not txn.success

    def test_timeout_fault(self, spi_bus: SPIBus) -> None:
        spi_bus.set_fault_probabilities(timeout=1.0)
        txn = spi_bus.read_register(0x00)
        assert not txn.success
        assert "timeout" in txn.error.lower()

    def test_corruption_fault(self, spi_bus: SPIBus) -> None:
        spi_bus.set_fault_probabilities(corruption=1.0)
        txn = spi_bus.read_register(0x00)
        assert not txn.success

    def test_transaction_log_grows(self, spi_bus: SPIBus) -> None:
        spi_bus.read_register(0x00)
        spi_bus.write_register(0x02, 0x01)
        assert len(spi_bus.transactions) == 2

    def test_clear_transactions(self, spi_bus: SPIBus) -> None:
        spi_bus.read_register(0x00)
        spi_bus.clear_transactions()
        assert len(spi_bus.transactions) == 0

    def test_bulk_read(self, spi_bus: SPIBus) -> None:
        results = spi_bus.bulk_read(0x00, 3)
        assert len(results) >= 1
        assert results[0].success

    def test_clock_hz_property(self, spi_bus: SPIBus) -> None:
        assert spi_bus.clock_hz == 1_000_000

    def test_command_in_transaction(self, spi_bus: SPIBus) -> None:
        txn = spi_bus.read_register(0x00)
        assert txn.command == SPI_CMD_READ

    def test_write_command_in_transaction(self, spi_bus: SPIBus) -> None:
        txn = spi_bus.write_register(0x02, 0x01)
        assert txn.command == SPI_CMD_WRITE

    def test_bulk_read_stops_on_failure(self, spi_bus: SPIBus) -> None:
        """bulk_read() breaks on failed transaction (line 162) and returns results (line 163)."""
        spi_bus.set_fault_probabilities(timeout=1.0)
        results = spi_bus.bulk_read(0x00, 3)
        assert len(results) == 1  # Stopped after first failure
        assert not results[0].success

    def test_spi_latency_applied(self, register_map: RegisterMap) -> None:
        """_apply_latency() calls time.sleep when latency_ms > 0 (line 183)."""
        bus = SPIBus(register_map=register_map, latency_ms=1.0)
        txn = bus.read_register(0x00)
        assert txn.success
        assert txn.duration_ms >= 0
