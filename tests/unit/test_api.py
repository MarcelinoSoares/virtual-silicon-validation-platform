"""Unit tests for the FastAPI REST endpoints."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import virtual_silicon.api.main as _api_mod
from virtual_silicon.api.main import app
from virtual_silicon.database.repository import TestRepository
from virtual_silicon.database.session import get_session
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


@pytest.mark.unit
class TestAPIBugFixes:
    """Regression tests for P0/P1 bug fixes."""

    def _make_fresh_chip(self) -> VirtualChip:
        chip = VirtualChip(sram_size=256, seed=42)
        chip.power_on()
        return chip

    def _make_in_memory_repo(self) -> TestRepository:
        db = get_session("sqlite:///:memory:")
        return TestRepository(db)

    def test_inject_stuck_at_zero_not_replaced_by_one(self) -> None:
        """POST /faults/inject with value=0 must inject stuck-at-zero, not stuck-at-one."""
        saved_chip = _api_mod._chip
        chip = self._make_fresh_chip()
        _api_mod._chip = chip
        try:
            resp = client.post(
                "/faults/inject",
                json={"fault_type": "stuck_bit", "address": 10, "bit": 2, "value": 0},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "injected"
            assert chip.sram._stuck_bits.get(10, {}).get(2) == 0
        finally:
            _api_mod._chip = saved_chip

    def test_inject_stuck_bit_invalid_value_returns_422(self) -> None:
        """POST /faults/inject with value outside {0,1} must return 422."""
        resp = client.post(
            "/faults/inject",
            json={"fault_type": "stuck_bit", "address": 10, "bit": 2, "value": 5},
        )
        assert resp.status_code == 422

    def test_run_tests_persists_results_to_database(self) -> None:
        """POST /tests/run must write results so GET /results returns them."""
        saved_chip = _api_mod._chip
        saved_repo = _api_mod._repo
        chip = self._make_fresh_chip()
        repo = self._make_in_memory_repo()
        _api_mod._chip = chip
        _api_mod._repo = repo
        try:
            run_resp = client.post("/tests/run", json={})
            assert run_resp.status_code == 200
            execution_id = run_resp.json()["execution_id"]
            total = run_resp.json()["total"]

            results_resp = client.get(f"/results?execution_id={execution_id}")
            assert results_resp.status_code == 200
            saved = results_resp.json()
            assert len(saved) == total
            assert all(r["status"] in ("PASS", "FAIL") for r in saved)
        finally:
            _api_mod._chip = saved_chip
            _api_mod._repo = saved_repo

    def test_run_tests_appears_in_latest_report(self) -> None:
        """GET /reports/latest must reflect the run created by POST /tests/run."""
        saved_chip = _api_mod._chip
        saved_repo = _api_mod._repo
        chip = self._make_fresh_chip()
        repo = self._make_in_memory_repo()
        _api_mod._chip = chip
        _api_mod._repo = repo
        try:
            run_resp = client.post("/tests/run", json={})
            assert run_resp.status_code == 200
            execution_id = run_resp.json()["execution_id"]

            report_resp = client.get("/reports/latest")
            assert report_resp.status_code == 200
            assert report_resp.json()["execution_id"] == execution_id
        finally:
            _api_mod._chip = saved_chip
            _api_mod._repo = saved_repo
