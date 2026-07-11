"""Fault model definitions and YAML configuration loading."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class FaultInjectionError(Exception):
    """Raised when a fault injection operation fails."""


class FaultType(StrEnum):
    """Enumeration of supported fault types."""

    STUCK_BIT = "stuck_bit"
    MEMORY_CORRUPTION = "memory_corruption"
    REGISTER_WRITE_FAILURE = "register_write_failure"
    REGISTER_VALUE_CORRUPTION = "register_value_corruption"
    VOLTAGE_DROP = "voltage_drop"
    OVERCURRENT = "overcurrent"
    OVERHEAT = "overheat"
    I2C_TIMEOUT = "i2c_timeout"
    I2C_NACK = "i2c_nack"
    SPI_TIMEOUT = "spi_timeout"
    SPI_CORRUPTION = "spi_corruption"


@dataclass
class FaultConfig:
    """Configuration for a single fault injection scenario."""

    fault_id: str
    fault_type: FaultType
    enabled: bool = True
    address: int | None = None
    bit: int | None = None
    value: int | None = None
    voltage: float | None = None
    temperature: float | None = None
    probability: float = 1.0
    trigger_after_cycles: int | None = None
    description: str = ""
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FaultConfig:
        """Build a FaultConfig from a YAML-parsed dictionary.

        Args:
            data: Dictionary with fault configuration fields.

        Returns:
            FaultConfig instance.

        Raises:
            FaultInjectionError: If required fields are missing or invalid.
        """
        try:
            fault_type = FaultType(data["type"])
        except (KeyError, ValueError) as exc:
            raise FaultInjectionError(f"Invalid fault config: {exc}") from exc

        return cls(
            fault_id=data.get("id", "UNKNOWN"),
            fault_type=fault_type,
            enabled=bool(data.get("enabled", True)),
            address=data.get("address"),
            bit=data.get("bit"),
            value=data.get("value"),
            voltage=data.get("voltage"),
            temperature=data.get("temperature"),
            probability=float(data.get("probability", 1.0)),
            trigger_after_cycles=data.get("trigger_after_cycles"),
            description=data.get("description", ""),
            metadata={
                k: v
                for k, v in data.items()
                if k
                not in (
                    "id",
                    "type",
                    "enabled",
                    "address",
                    "bit",
                    "value",
                    "voltage",
                    "temperature",
                    "probability",
                    "trigger_after_cycles",
                    "description",
                )
            },
        )


@dataclass
class FaultModel:
    """Runtime state of an active fault injection."""

    config: FaultConfig
    active: bool = False
    trigger_count: int = 0
    last_triggered_cycle: int | None = None


def load_fault_configs(yaml_path: str | Path) -> list[FaultConfig]:
    """Load fault configurations from a YAML file.

    Args:
        yaml_path: Path to the faults YAML file.

    Returns:
        List of FaultConfig instances (only enabled faults).

    Raises:
        FaultInjectionError: If the file is invalid or cannot be parsed.
    """
    path = Path(yaml_path)
    if not path.exists():
        raise FaultInjectionError(f"Fault config file not found: {path}")
    try:
        with path.open() as f:
            data = yaml.safe_load(f)
        faults_data = data.get("faults", [])
        configs = [FaultConfig.from_dict(fd) for fd in faults_data]
        enabled = [c for c in configs if c.enabled]
        logger.info(
            "Loaded %d fault configs (%d enabled) from %s.", len(configs), len(enabled), path
        )
        return enabled
    except yaml.YAMLError as exc:
        raise FaultInjectionError(f"Failed to parse fault config: {exc}") from exc
