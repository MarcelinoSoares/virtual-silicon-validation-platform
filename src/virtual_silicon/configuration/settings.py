"""Platform-wide settings loaded from environment variables or defaults."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global platform configuration via environment variables or defaults."""

    # Project
    project_name: str = "Virtual Silicon Validation Platform"
    version: str = "1.0.0"
    environment: str = Field(default="development", alias="VSVP_ENV")

    # Database
    database_url: str = Field(
        default="sqlite:///./virtual_silicon.db",
        alias="VSVP_DATABASE_URL",
    )

    # SRAM
    sram_size_bytes: int = Field(default=256, alias="VSVP_SRAM_SIZE")
    random_seed: int = Field(default=42, alias="VSVP_RANDOM_SEED")

    # Logging
    log_level: str = Field(default="INFO", alias="VSVP_LOG_LEVEL")
    log_file: str = Field(default="logs/virtual-silicon.log", alias="VSVP_LOG_FILE")

    # Reporting
    reports_dir: str = Field(default="reports", alias="VSVP_REPORTS_DIR")
    charts_dir: str = Field(default="reports/charts", alias="VSVP_CHARTS_DIR")

    # API
    api_host: str = Field(default="0.0.0.0", alias="VSVP_API_HOST")
    api_port: int = Field(default=8000, alias="VSVP_API_PORT")
    api_debug: bool = Field(default=False, alias="VSVP_API_DEBUG")

    # Device
    i2c_device_address: int = Field(default=0x48, alias="VSVP_I2C_ADDR")
    spi_clock_hz: int = Field(default=1_000_000, alias="VSVP_SPI_CLOCK")

    # Instruments
    supply_voltage: float = Field(default=3.3, alias="VSVP_SUPPLY_VOLTAGE")
    supply_current_limit: float = Field(default=1.0, alias="VSVP_SUPPLY_CURRENT")
    ambient_temperature: float = Field(default=25.0, alias="VSVP_AMBIENT_TEMP")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def reports_path(self) -> Path:
        """Reports directory as a Path object."""
        return Path(self.reports_dir)

    @property
    def charts_path(self) -> Path:
        """Charts directory as a Path object."""
        return Path(self.charts_dir)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached global settings instance."""
    return Settings()
