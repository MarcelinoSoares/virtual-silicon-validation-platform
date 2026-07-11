"""Base protocol abstractions and shared data types."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Protocol

from virtual_silicon.exceptions import ProtocolTimeoutError

__all__ = ["ProtocolTimeoutError", "RegisterDevice", "TransactionLog"]


class RegisterDevice(Protocol):
    """Structural interface satisfied by VirtualChip and RegisterMap.

    Any object exposing read_register/write_register can be used as the
    backing device for I2CBus and SPIBus, enabling power-state checks,
    cycle counting, and fault callbacks when a VirtualChip is passed.
    """

    def read_register(self, address: int) -> int: ...

    def write_register(self, address: int, value: int) -> None: ...


@dataclass
class TransactionLog:
    """Record of a single protocol transaction."""

    protocol: str
    timestamp: float = field(default_factory=time.monotonic)
    direction: str = ""
    address: int = 0
    register: int = 0
    data: list[int] = field(default_factory=list)
    success: bool = True
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        """Serialize to dictionary."""
        return {
            "protocol": self.protocol,
            "timestamp": self.timestamp,
            "direction": self.direction,
            "address": self.address,
            "register": self.register,
            "data": self.data,
            "success": self.success,
            "error": self.error,
        }
