"""Unit tests for the FastAPI REST endpoints."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import virtual_silicon.api.main as _api_mod
from virtual_silicon.api.main import app
from virtual_silicon.device.virtual_chip import VirtualChip

client = TestClient(app)


@pytest.mark.unit
class TestAPIHealth:
    def test_health_endpoint(self) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_chip_status_endpoint(self) -> None:
        resp = client.get("/chip/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "powered" in data
        assert "chip_version" in data

    def test_power_on_chip(self) -> None:
        resp = client.post("/chip/power")
        assert resp.status_code == 200
        assert resp.json()["status"] == "powered_on"

    def test_list_registers_after_power_on(self) -> None:
        client.post("/chip/power")
        resp = client.get("/chip/registers")
        assert resp.status_code == 200
        data = resp.json()
        assert "DEVICE_ID" in data

    def test_read_register_by_address(self) -> None:
        client.post("/chip/power")
        resp = client.get("/chip/registers/0")
        assert resp.status_code == 200
        assert resp.json()["value"] == 0xA5

    def test_write_register(self) -> None:
        client.post("/chip/power")
        resp = client.post("/chip/registers/2", json={"value": 5})
        assert resp.status_code == 200
        assert resp.json()["written"] == 5

    def test_write_read_only_register_fails(self) -> None:
        client.post("/chip/power")
        resp = client.post("/chip/registers/0", json={"value": 0})
        assert resp.status_code == 400

    def test_read_invalid_register(self) -> None:
        client.post("/chip/power")
        resp = client.get("/chip/registers/255")
        assert resp.status_code == 404

    def test_reset_chip(self) -> None:
        client.post("/chip/power")
        resp = client.post("/chip/reset")
        assert resp.status_code == 200
        assert resp.json()["status"] == "reset"

    def test_run_tests_endpoint(self) -> None:
        client.post("/chip/power")
        resp = client.post("/tests/run", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert data["total"] > 0

    def test_inject_fault_stuck_bit(self) -> None:
        client.post("/chip/power")
        resp = client.post(
            "/faults/inject", json={"fault_type": "stuck_bit", "address": 5, "bit": 0, "value": 1}
        )
        assert resp.status_code == 200

    def test_inject_unknown_fault_fails(self) -> None:
        resp = client.post("/faults/inject", json={"fault_type": "bad_type"})
        assert resp.status_code == 400

    def test_get_results_empty(self) -> None:
        resp = client.get("/results")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_latest_report_no_runs(self) -> None:
        resp = client.get("/reports/latest")
        # either 200 (if there are runs from earlier test) or 404
        assert resp.status_code in (200, 404)


@pytest.mark.unit
class TestAPIChipNotPowered:
    """Covers API lines hit only when chip is not powered: 90, 102, 115, 141."""

    def _make_unpowered_chip(self) -> VirtualChip:
        return VirtualChip(sram_size=256, seed=42)  # not powered on

    def test_list_registers_chip_not_powered(self) -> None:
        """GET /chip/registers returns 409 when chip is not powered (line 90)."""
        saved = _api_mod._chip
        _api_mod._chip = self._make_unpowered_chip()
        try:
            resp = client.get("/chip/registers")
            assert resp.status_code == 409
        finally:
            _api_mod._chip = saved

    def test_read_register_chip_not_powered(self) -> None:
        """GET /chip/registers/{addr} returns 409 on DeviceNotPoweredError (line 102)."""
        saved = _api_mod._chip
        _api_mod._chip = self._make_unpowered_chip()
        try:
            resp = client.get("/chip/registers/0")
            assert resp.status_code == 409
        finally:
            _api_mod._chip = saved

    def test_write_register_chip_not_powered(self) -> None:
        """POST /chip/registers/{addr} returns 409 on DeviceNotPoweredError (line 115)."""
        saved = _api_mod._chip
        _api_mod._chip = self._make_unpowered_chip()
        try:
            resp = client.post("/chip/registers/2", json={"value": 5})
            assert resp.status_code == 409
        finally:
            _api_mod._chip = saved

    def test_run_tests_chip_not_powered(self) -> None:
        """POST /tests/run returns 409 when chip is not powered (line 141)."""
        saved = _api_mod._chip
        _api_mod._chip = self._make_unpowered_chip()
        try:
            resp = client.post("/tests/run", json={})
            assert resp.status_code == 409
        finally:
            _api_mod._chip = saved


@pytest.mark.unit
class TestAPIFaultAndReport:
    """Covers API lines 174 (no_action) and 200 (no runs 404)."""

    def test_inject_fault_no_chip_action(self) -> None:
        """Fault type without chip-level action returns no_action (line 174)."""
        # I2C_TIMEOUT has no chip-level action via this endpoint
        resp = client.post("/faults/inject", json={"fault_type": "i2c_timeout"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "no_action"

    def test_inject_stuck_bit_no_address_no_action(self) -> None:
        """STUCK_BIT without address/bit returns no_action (line 174)."""
        resp = client.post("/faults/inject", json={"fault_type": "stuck_bit"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "no_action"

    def test_get_latest_report_no_runs_404(self) -> None:
        """GET /reports/latest returns 404 when the repo has no runs (line 200)."""
        saved = _api_mod._repo
        mock_repo = MagicMock()
        mock_repo.list_test_runs.return_value = []
        _api_mod._repo = mock_repo
        try:
            resp = client.get("/reports/latest")
            assert resp.status_code == 404
        finally:
            _api_mod._repo = saved
