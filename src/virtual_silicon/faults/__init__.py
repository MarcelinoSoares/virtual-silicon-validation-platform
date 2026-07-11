"""Fault injection framework for simulating hardware and protocol failures."""

from virtual_silicon.faults.fault_injector import FaultInjector
from virtual_silicon.faults.fault_models import (
    FaultConfig,
    FaultInjectionError,
    FaultModel,
    FaultType,
    load_fault_configs,
)

__all__ = [
    "FaultConfig",
    "FaultInjectionError",
    "FaultModel",
    "FaultType",
    "load_fault_configs",
    "FaultInjector",
]
