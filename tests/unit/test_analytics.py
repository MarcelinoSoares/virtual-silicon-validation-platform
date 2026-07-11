"""Unit tests for analytics: TestAnalyzer and ReportGenerator."""

from __future__ import annotations

import types
from pathlib import Path

import pytest

from virtual_silicon.analytics.analyzer import AnalyticsSummary, TestAnalyzer
from virtual_silicon.analytics.report_generator import ReportGenerator

# ── Helpers ────────────────────────────────────────────────────────────────


def _result(eid, name, cat, status, dur=10.0, fw="1.0", err=None):
    return types.SimpleNamespace(
        execution_id=eid,
        test_name=name,
        category=cat,
        status=status,
        duration_ms=dur,
        firmware_version=fw,
        error_message=err,
    )


def _measurement(eid, voltage=None, current=None, temperature=None, brightness=None):
    return types.SimpleNamespace(
        execution_id=eid,
        voltage=voltage,
        current=current,
        temperature=temperature,
        brightness=brightness,
    )


def _fault_event(eid, fault_id, fault_type, cycle=0):
    return types.SimpleNamespace(
        execution_id=eid,
        fault_id=fault_id,
        fault_type=fault_type,
        cycle=cycle,
    )


# ── TestAnalyzer ───────────────────────────────────────────────────────────


@pytest.mark.unit
class TestAnalyzerEmptyData:
    """Covers _build_results_df with empty list (line 55) and edge cases."""

    def test_empty_results_build_df(self) -> None:
        """Empty results list returns DataFrame with correct columns (line 55)."""
        analyzer = TestAnalyzer([], [], [])
        assert analyzer._results_df.empty
        assert "execution_id" in analyzer._results_df.columns

    def test_summarize_no_results_returns_zero_summary(self) -> None:
        """summarize() on empty data returns zero-count AnalyticsSummary (line 114)."""
        analyzer = TestAnalyzer([], [], [])
        summary = analyzer.summarize("EX-001")
        assert summary.total_tests == 0
        assert summary.pass_rate == 0.0
        assert summary.fail_rate == 0.0

    def test_summarize_wrong_execution_id_returns_zero(self) -> None:
        """summarize() with execution_id not in results hits total==0 branch (line 114)."""
        results = [_result("EX-002", "test_a", "memory", "PASS")]
        analyzer = TestAnalyzer(results, [], [])
        summary = analyzer.summarize("EX-NONEXISTENT")
        assert summary.total_tests == 0


@pytest.mark.unit
class TestAnalyzerFaultEvents:
    """Covers _build_faults_df (lines 88-97) and fault summary (lines 164-166)."""

    def test_build_faults_df_with_data(self) -> None:
        """_build_faults_df with fault events populates DataFrame (lines 88-97)."""
        faults = [
            _fault_event("EX-001", "F1", "stuck_bit", cycle=10),
            _fault_event("EX-001", "F2", "memory_corruption", cycle=20),
        ]
        analyzer = TestAnalyzer([], [], faults)
        assert not analyzer._faults_df.empty
        assert len(analyzer._faults_df) == 2

    def test_summarize_includes_most_common_faults(self) -> None:
        """summarize() populates most_common_faults when fault events exist (lines 164-166)."""
        results = [_result("EX-001", "t1", "memory", "PASS")]
        faults = [
            _fault_event("EX-001", "F1", "stuck_bit"),
            _fault_event("EX-001", "F2", "stuck_bit"),
            _fault_event("EX-001", "F3", "memory_corruption"),
        ]
        analyzer = TestAnalyzer(results, [], faults)
        summary = analyzer.summarize("EX-001")
        assert len(summary.most_common_faults) >= 1
        # stuck_bit should be most common
        top = summary.most_common_faults[0]
        assert top["fault_type"] == "stuck_bit"

    def test_summarize_faults_filtered_by_execution_id(self) -> None:
        """Fault events from different executions are filtered correctly (line 164)."""
        results = [_result("EX-001", "t1", "memory", "PASS")]
        faults = [
            _fault_event("EX-001", "F1", "stuck_bit"),
            _fault_event("EX-002", "F2", "overheat"),
        ]
        analyzer = TestAnalyzer(results, [], faults)
        summary = analyzer.summarize("EX-001")
        assert len(summary.most_common_faults) == 1
        assert summary.most_common_faults[0]["fault_type"] == "stuck_bit"


@pytest.mark.unit
class TestAnalyzerCompareRuns:
    """Covers compare_runs() method (lines 200-210)."""

    def test_compare_runs_returns_dataframe(self) -> None:
        """compare_runs() returns a DataFrame with one row per execution (lines 200-210)."""
        results = [
            _result("EX-A", "t1", "memory", "PASS", dur=5.0),
            _result("EX-A", "t2", "memory", "PASS", dur=15.0),
            _result("EX-B", "t1", "memory", "FAIL", dur=20.0),
        ]
        analyzer = TestAnalyzer(results, [], [])
        df = analyzer.compare_runs(["EX-A", "EX-B"])
        assert len(df) == 2
        assert "pass_rate" in df.columns
        assert "execution_id" in df.columns

    def test_compare_runs_empty_executions(self) -> None:
        """compare_runs() with empty list returns empty DataFrame."""
        analyzer = TestAnalyzer([], [], [])
        df = analyzer.compare_runs([])
        assert len(df) == 0

    def test_compare_runs_with_measurements(self) -> None:
        """compare_runs() works with mixed execution IDs."""
        results = [
            _result("R1", "t1", "cat", "PASS"),
            _result("R2", "t1", "cat", "FAIL"),
        ]
        analyzer = TestAnalyzer(results, [], [])
        df = analyzer.compare_runs(["R1", "R2", "R3"])
        assert len(df) == 3
        # R3 has no results -> pass_rate=0
        r3_row = df[df["execution_id"] == "R3"]
        assert r3_row["pass_rate"].iloc[0] == 0.0


@pytest.mark.unit
class TestAnalyzerFullSummarize:
    """Covers all branches of summarize() with real data."""

    def test_summarize_with_failures_by_category(self) -> None:
        results = [
            _result("EX-1", "t1", "memory", "PASS"),
            _result("EX-1", "t2", "register", "FAIL"),
            _result("EX-1", "t3", "memory", "FAIL"),
        ]
        analyzer = TestAnalyzer(results, [], [])
        summary = analyzer.summarize("EX-1")
        assert summary.failed == 2
        assert "memory" in summary.failures_by_category
        assert "register" in summary.failures_by_category

    def test_summarize_with_measurements(self) -> None:
        results = [_result("EX-1", "t1", "cat", "PASS")]
        measurements = [
            _measurement("EX-1", voltage=3.3, current=0.5, temperature=25.0),
            _measurement("EX-1", voltage=3.2, current=0.4, temperature=26.0),
        ]
        analyzer = TestAnalyzer(results, measurements, [])
        summary = analyzer.summarize("EX-1")
        assert summary.avg_voltage is not None
        assert summary.avg_current is not None
        assert summary.avg_temperature is not None


# ── ReportGenerator ────────────────────────────────────────────────────────


@pytest.mark.unit
class TestReportGeneratorHTML:
    """Covers HTML generation edge cases in report_generator.py."""

    def _make_summary(
        self,
        failed: int = 0,
        failures_by_category: dict | None = None,
        slowest_tests: list | None = None,
        avg_temperature: float | None = None,
        avg_voltage: float | None = None,
        fail_rate: float = 0.0,
    ) -> AnalyticsSummary:
        total = 5
        passed = total - failed
        return AnalyticsSummary(
            execution_id="EX-TEST",
            total_tests=total,
            passed=passed,
            failed=failed,
            pass_rate=round(passed / total * 100, 2),
            fail_rate=fail_rate,
            avg_duration_ms=10.0,
            failures_by_category=failures_by_category or {},
            slowest_tests=slowest_tests or [],
            avg_temperature=avg_temperature,
            avg_voltage=avg_voltage,
        )

    def test_html_no_failures_table(self, tmp_path: Path) -> None:
        """No failures_by_category renders the 'No failures' paragraph (line 289)."""
        gen = ReportGenerator(output_dir=tmp_path)
        summary = self._make_summary(failed=0)
        gen._generate_html(summary, {}, tmp_path / "a.csv", tmp_path / "a.json")
        html_path = tmp_path / "EX-TEST_report.html"
        content = html_path.read_text()
        assert "No failures recorded." in content

    def test_html_no_slowest_tests(self, tmp_path: Path) -> None:
        """Empty slowest_tests renders 'No test duration data' paragraph (line 302)."""
        gen = ReportGenerator(output_dir=tmp_path)
        summary = self._make_summary(slowest_tests=[])
        gen._generate_html(summary, {}, tmp_path / "a.csv", tmp_path / "a.json")
        html_path = tmp_path / "EX-TEST_report.html"
        content = html_path.read_text()
        assert "No test duration data." in content

    def test_html_recommendation_high_temperature(self, tmp_path: Path) -> None:
        """avg_temperature > 70 adds thermal recommendation (line 315)."""
        gen = ReportGenerator(output_dir=tmp_path)
        summary = self._make_summary(avg_temperature=80.0)
        gen._generate_html(summary, {}, tmp_path / "a.csv", tmp_path / "a.json")
        html_path = tmp_path / "EX-TEST_report.html"
        content = html_path.read_text()
        assert "thermal management" in content

    def test_html_recommendation_low_voltage(self, tmp_path: Path) -> None:
        """avg_voltage < 3.0 adds voltage recommendation (line 317)."""
        gen = ReportGenerator(output_dir=tmp_path)
        summary = self._make_summary(avg_voltage=2.5)
        gen._generate_html(summary, {}, tmp_path / "a.csv", tmp_path / "a.json")
        html_path = tmp_path / "EX-TEST_report.html"
        content = html_path.read_text()
        assert "power supply stability" in content

    def test_html_recommendation_all_nominal(self, tmp_path: Path) -> None:
        """No issues -> 'All checks nominal' recommendation (line 319)."""
        gen = ReportGenerator(output_dir=tmp_path)
        summary = self._make_summary(fail_rate=0.0, avg_voltage=3.3, avg_temperature=25.0)
        gen._generate_html(summary, {}, tmp_path / "a.csv", tmp_path / "a.json")
        html_path = tmp_path / "EX-TEST_report.html"
        content = html_path.read_text()
        assert "All checks nominal" in content

    def test_generate_all_creates_files(self, tmp_path: Path) -> None:
        """generate_all() creates HTML, CSV, and JSON outputs."""
        gen = ReportGenerator(output_dir=tmp_path)
        results = [_result("EX-1", "t1", "memory", "PASS")]
        measurements = [_measurement("EX-1", voltage=3.3, temperature=25.0)]
        summary = AnalyticsSummary(
            execution_id="EX-1",
            total_tests=1,
            passed=1,
            failed=0,
            pass_rate=100.0,
            fail_rate=0.0,
            avg_duration_ms=5.0,
            failures_by_category={"memory": 1},
            slowest_tests=[{"test_name": "t1", "duration_ms": 5.0, "status": "PASS"}],
            avg_voltage=3.3,
            avg_temperature=25.0,
        )
        paths = gen.generate_all(summary, results, measurements)
        assert paths["html"].exists()
        assert paths["csv"].exists()
        assert paths["json"].exists()
