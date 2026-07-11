"""Unit tests for the CLI commands via Typer's test runner."""

import pytest
from typer.testing import CliRunner

import virtual_silicon.cli as _cli_mod
from virtual_silicon.cli import app
from virtual_silicon.database.repository import TestRepository
from virtual_silicon.database.session import DatabaseSession
from virtual_silicon.device.virtual_chip import VirtualChip

runner = CliRunner()


@pytest.mark.unit
class TestCLI:
    def test_initialize_command(self) -> None:
        result = runner.invoke(app, ["initialize"])
        assert result.exit_code == 0
        assert "Platform ready" in result.output or "Firmware" in result.output

    def test_show_registers_command(self) -> None:
        result = runner.invoke(app, ["show-registers"])
        assert result.exit_code == 0
        assert "DEVICE_ID" in result.output

    def test_run_memory_tests_command(self) -> None:
        result = runner.invoke(app, ["run-memory-tests"])
        assert result.exit_code == 0
        assert "walking_ones" in result.output or "PASS" in result.output

    def test_reset_chip_command(self) -> None:
        result = runner.invoke(app, ["reset-chip"])
        assert result.exit_code == 0
        assert "reset" in result.output.lower()

    def test_run_tests_command(self) -> None:
        result = runner.invoke(app, ["run-tests"])
        assert result.exit_code == 0
        assert "passed" in result.output.lower() or "Results" in result.output

    def test_inject_fault_missing_file(self) -> None:
        result = runner.invoke(app, ["inject-fault", "--config", "nonexistent.yaml"])
        assert result.exit_code == 1

    def test_inject_fault_from_config(self) -> None:
        result = runner.invoke(app, ["inject-fault", "--config", "configs/faults.yaml"])
        assert result.exit_code == 0

    def test_generate_report_command(self, tmp_path) -> None:
        # First run tests to have data in db
        runner.invoke(app, ["run-tests"])
        result = runner.invoke(app, ["generate-report", "--output", str(tmp_path)])
        assert result.exit_code == 0


@pytest.mark.unit
class TestCLIUnpoweredChip:
    """Covers CLI lines where chip is powered on mid-command: 83, 135, 163, 232."""

    def _save_and_clear(self):
        saved_chip = _cli_mod._chip
        saved_repo = _cli_mod._repo
        _cli_mod._chip = None
        _cli_mod._repo = None
        return saved_chip, saved_repo

    def _restore(self, saved_chip, saved_repo):
        _cli_mod._chip = saved_chip
        _cli_mod._repo = saved_repo

    def test_run_tests_powers_on_if_not_powered(self) -> None:
        """run-tests powers on the chip if it is not powered (line 83)."""
        saved_chip, saved_repo = self._save_and_clear()
        try:
            result = runner.invoke(app, ["run-tests"])
            # Should succeed — chip is powered on inside the command
            assert result.exit_code == 0
        finally:
            self._restore(saved_chip, saved_repo)

    def test_run_memory_tests_powers_on_if_not_powered(self) -> None:
        """run-memory-tests powers on the chip if not powered (line 135)."""
        saved_chip, saved_repo = self._save_and_clear()
        try:
            result = runner.invoke(app, ["run-memory-tests"])
            assert result.exit_code == 0
        finally:
            self._restore(saved_chip, saved_repo)

    def test_inject_fault_powers_on_if_not_powered(self) -> None:
        """inject-fault powers on the chip if not powered (line 163)."""
        saved_chip, saved_repo = self._save_and_clear()
        try:
            result = runner.invoke(app, ["inject-fault", "--config", "configs/faults.yaml"])
            assert result.exit_code == 0
        finally:
            self._restore(saved_chip, saved_repo)

    def test_show_registers_powers_on_if_not_powered(self) -> None:
        """show-registers powers on the chip if not powered (line 232)."""
        saved_chip, saved_repo = self._save_and_clear()
        try:
            result = runner.invoke(app, ["show-registers"])
            assert result.exit_code == 0
            assert "DEVICE_ID" in result.output
        finally:
            self._restore(saved_chip, saved_repo)


@pytest.mark.unit
class TestCLIReportNoRuns:
    """Covers CLI line 197-198: generate-report when no test runs in DB."""

    def test_generate_report_no_runs_exits_with_error(self, tmp_path) -> None:
        """generate-report exits with code 1 when no runs exist (lines 197-198)."""
        saved_chip = _cli_mod._chip
        saved_repo = _cli_mod._repo
        # Install an empty in-memory repo so list_test_runs() returns []
        db = DatabaseSession("sqlite:///:memory:")
        db.create_tables()
        _cli_mod._repo = TestRepository(db)
        _cli_mod._chip = VirtualChip(sram_size=256, seed=42)
        _cli_mod._chip.power_on()
        try:
            result = runner.invoke(app, ["generate-report", "--output", str(tmp_path)])
            assert result.exit_code == 1
            assert "No test runs found" in result.output
        finally:
            _cli_mod._chip = saved_chip
            _cli_mod._repo = saved_repo


@pytest.mark.unit
class TestCLIRegisterFail:
    """Covers CLI line 100: register check fails (failed += 1)."""

    def test_run_tests_register_check_fail(self) -> None:
        """run-tests counts a FAIL when device_id check fails (line 100)."""
        saved_chip = _cli_mod._chip
        saved_repo = _cli_mod._repo
        _cli_mod._chip = None
        _cli_mod._repo = None
        try:
            # Invoke once to create the chip singleton
            runner.invoke(app, ["initialize"])
            # Now corrupt the DEVICE_ID register value in the existing chip
            chip = _cli_mod._chip
            if chip is not None:
                chip.register_map._registers[0x00]._value = 0xFF  # wrong device ID
            result = runner.invoke(app, ["run-tests"])
            assert result.exit_code == 0
            assert "FAIL" in result.output
        finally:
            _cli_mod._chip = saved_chip
            _cli_mod._repo = saved_repo


@pytest.mark.unit
class TestCLINoFaultsTriggered:
    """Covers CLI line 179: no faults triggered in inject-fault."""

    def test_inject_fault_no_faults_triggered(self, tmp_path) -> None:
        """inject-fault prints 'No faults triggered' when all faults have probability=0 (line 179)."""
        import yaml
        config_file = tmp_path / "zero_prob_faults.yaml"
        config_data = {
            "faults": [
                {
                    "id": "ZERO_PROB",
                    "type": "stuck_bit",
                    "enabled": True,
                    "address": 0,
                    "bit": 0,
                    "value": 1,
                    "probability": 0.0,
                }
            ]
        }
        config_file.write_text(yaml.dump(config_data))

        saved_chip = _cli_mod._chip
        saved_repo = _cli_mod._repo
        try:
            result = runner.invoke(app, ["inject-fault", "--config", str(config_file)])
            assert result.exit_code == 0
            assert "No faults triggered" in result.output
        finally:
            _cli_mod._chip = saved_chip
            _cli_mod._repo = saved_repo
