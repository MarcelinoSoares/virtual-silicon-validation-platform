"""Fault injection framework for simulating hardware and protocol failures."""

from virtual_silicon.faults.fault_injector import FaultApplicationResult, FaultInjector
from virtual_silicon.faults.fault_models import (
    FaultConfig,
    FaultInjectionError,
    FaultModel,
    FaultType,
    load_fault_configs,
)

__all__ = [
    "FaultApplicationResult",
    "FaultConfig",
    "FaultInjectionError",
    "FaultModel",
    "FaultType",
    "load_fault_configs",
    "FaultInjector",
]
