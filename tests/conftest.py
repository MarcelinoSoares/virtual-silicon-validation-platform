"""Shared Pytest fixtures for all test levels."""

from __future__ import annotations

import pytest

from virtual_silicon.database.repository import TestRepository
from virtual_silicon.database.session import DatabaseSession
from virtual_silicon.device.memory import SRAM
from virtual_silicon.device.register_map import RegisterMap
from virtual_silicon.device.virtual_chip import VirtualChip
from virtual_silicon.faults.fault_injector import FaultInjector
from virtual_silicon.faults.fault_models import FaultConfig, FaultType
from virtual_silicon.instruments.multimeter import Multimeter
from virtual_silicon.instruments.power_supply import PowerSupply
from virtual_silicon.instruments.spectrometer import Spectrometer
from virtual_silicon.instruments.temperature_sensor import TemperatureSensor
from virtual_silicon.protocols.i2c import I2CBus
from virtual_silicon.protocols.spi import SPIBus

SEED = 42


@pytest.fixture
def seed() -> int:
    """Deterministic random seed for all tests."""
    return SEED


@pytest.fixture
def virtual_chip(seed: int) -> VirtualChip:
    """Powered virtual chip with deterministic seed."""
    chip = VirtualChip(sram_size=256, seed=seed)
    chip.power_on()
    return chip


@pytest.fixture
def unpowered_chip(seed: int) -> VirtualChip:
    """Unpowered virtual chip for power-guard tests."""
    return VirtualChip(sram_size=256, seed=seed)


@pytest.fixture
def clean_sram(seed: int) -> SRAM:
    """Fresh SRAM with no faults injected."""
    return SRAM(size=256, seed=seed)


@pytest.fixture
def register_map() -> RegisterMap:
    """Fresh register map."""
    return RegisterMap()


@pytest.fixture
def i2c_bus(register_map: RegisterMap, seed: int) -> I2CBus:
    """I2C bus connected to a fresh register map."""
    return I2CBus(register_map=register_map, device_address=0x48, seed=seed)


@pytest.fixture
def spi_bus(register_map: RegisterMap, seed: int) -> SPIBus:
    """SPI bus connected to a fresh register map."""
    return SPIBus(register_map=register_map, seed=seed)


@pytest.fixture
def temp_db() -> TestRepository:
    """In-memory SQLite database for test isolation."""
    db = DatabaseSession("sqlite:///:memory:")
    db.create_tables()
    return TestRepository(db)


@pytest.fixture
def fault_configs_sram() -> list[FaultConfig]:
    """Stuck-bit fault config for SRAM address 15 bit 3."""
    return [
        FaultConfig(
            fault_id="TEST_STUCK_BIT",
            fault_type=FaultType.STUCK_BIT,
            enabled=True,
            address=15,
            bit=3,
            value=1,
            probability=1.0,
        )
    ]


@pytest.fixture
def fault_injector(fault_configs_sram: list[FaultConfig], seed: int) -> FaultInjector:
    """FaultInjector loaded with a SRAM stuck-bit fault."""
    return FaultInjector(fault_configs_sram, seed=seed)


@pytest.fixture
def power_supply(seed: int) -> PowerSupply:
    """Virtual power supply at 3.3V."""
    ps = PowerSupply(voltage=3.3, current_limit=1.0, seed=seed)
    ps.power_on()
    return ps


@pytest.fixture
def multimeter(seed: int) -> Multimeter:
    """Virtual multimeter with default settings."""
    return Multimeter(seed=seed)


@pytest.fixture
def temperature_sensor(seed: int) -> TemperatureSensor:
    """Virtual temperature sensor at 25°C."""
    return TemperatureSensor(ambient_celsius=25.0, seed=seed)


@pytest.fixture
def spectrometer(seed: int) -> Spectrometer:
    """Virtual spectrometer at default brightness."""
    return Spectrometer(seed=seed)
