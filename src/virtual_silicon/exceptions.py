"""Unified exception hierarchy for the virtual silicon validation platform."""

from __future__ import annotations


class VirtualSiliconError(Exception):
    """Base class for all virtual-silicon exceptions."""


class DeviceError(VirtualSiliconError):
    """Errors originating from the virtual chip device layer."""


class DeviceNotPoweredError(DeviceError):
    """Raised when an operation is attempted on an unpowered device."""


class MemoryValidationError(VirtualSiliconError):
    """Raised when a memory validation operation fails."""


class InvalidRegisterAddressError(VirtualSiliconError):
    """Raised when an invalid register address is accessed."""


class RegisterAccessError(VirtualSiliconError):
    """Raised when a register access violation occurs."""


class ProtocolError(VirtualSiliconError):
    """Errors originating from the I2C or SPI protocol layer."""


class ProtocolTimeoutError(ProtocolError):
    """Raised when a protocol transaction times out."""


class InstrumentError(VirtualSiliconError):
    """Errors originating from virtual instruments."""


class InstrumentMeasurementError(InstrumentError):
    """Raised when an instrument measurement fails."""


class FaultInjectionError(VirtualSiliconError):
    """Raised when a fault injection configuration is invalid."""
