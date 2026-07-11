"""Unit tests for configuration settings."""

import pytest

from virtual_silicon.configuration.settings import Settings, get_settings


@pytest.mark.unit
class TestSettings:
    def test_default_settings(self) -> None:
        s = Settings()
        assert s.sram_size_bytes == 256
        assert s.random_seed == 42
        assert s.supply_voltage == 3.3

    def test_database_url_default(self) -> None:
        s = Settings()
        assert "sqlite" in s.database_url

    def test_reports_path(self) -> None:
        s = Settings()
        assert s.reports_path.name == "reports"

    def test_charts_path(self) -> None:
        s = Settings()
        assert "charts" in str(s.charts_path)

    def test_get_settings_cached(self) -> None:
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_api_defaults(self) -> None:
        s = Settings()
        assert s.api_port == 8000
        assert s.api_host == "0.0.0.0"
