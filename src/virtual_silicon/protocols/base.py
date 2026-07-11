"""Base protocol abstractions and shared data types."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


class ProtocolTimeoutError(Exception):
    """Raised when a protocol transaction times out."""


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
