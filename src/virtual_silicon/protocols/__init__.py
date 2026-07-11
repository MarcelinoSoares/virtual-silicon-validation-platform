"""Communication protocol simulations: I2C and SPI."""

from virtual_silicon.protocols.base import ProtocolTimeoutError, TransactionLog
from virtual_silicon.protocols.i2c import I2CBus, I2CTransaction
from virtual_silicon.protocols.spi import SPIBus, SPITransaction

__all__ = [
    "ProtocolTimeoutError",
    "TransactionLog",
    "I2CBus",
    "I2CTransaction",
    "SPIBus",
    "SPITransaction",
]
