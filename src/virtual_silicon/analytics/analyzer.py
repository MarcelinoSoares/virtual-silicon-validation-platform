"""Test result analytics using Pandas."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class AnalyticsSummary:
    """Aggregated analytics results from a test execution."""

    execution_id: str
    total_tests: int
    passed: int
    failed: int
    pass_rate: float
    fail_rate: float
    avg_duration_ms: float
    slowest_tests: list[dict] = field(default_factory=list)
    failures_by_category: dict[str, int] = field(default_factory=dict)
    failures_by_firmware: dict[str, int] = field(default_factory=dict)
    avg_voltage: float | None = None
    avg_current: float | None = None
    avg_temperature: float | None = None
    temp_failure_correlation: float | None = None
    most_common_faults: list[dict] = field(default_factory=list)


class TestAnalyzer:
    """Analyzes test results and measurements using Pandas DataFrames.

    Produces pass/fail statistics, category breakdowns, duration analysis,
    measurement trends, and temperature/failure correlation.
    """

    def __init__(self, results: list, measurements: list, fault_events: list) -> None:
        """Initialize the analyzer with raw ORM result lists.

        Args:
            results: List of TestResult ORM objects.
            measurements: List of Measurement ORM objects.
            fault_events: List of FaultEvent ORM objects.
        """
        self._results_df = self._build_results_df(results)
        self._measurements_df = self._build_measurements_df(measurements)
        self._faults_df = self._build_faults_df(fault_events)

    def _build_results_df(self, results: list) -> pd.DataFrame:
        if not results:
            return pd.DataFrame(columns=["execution_id", "test_name", "category", "status", "duration_ms", "firmware_version"])
        rows = [
            {
                "execution_id": r.execution_id,
                "test_name": r.test_name,
                "category": r.category,
                "status": r.status,
                "duration_ms": r.duration_ms,
                "firmware_version": r.firmware_version,
                "error_message": r.error_message or "",
            }
            for r in results
        ]
        return pd.DataFrame(rows)

    def _build_measurements_df(self, measurements: list) -> pd.DataFrame:
        if not measurements:
            return pd.DataFrame(columns=["execution_id", "voltage", "current", "temperature", "brightness"])
        rows = [
            {
                "execution_id": m.execution_id,
                "voltage": m.voltage,
                "current": m.current,
                "temperature": m.temperature,
                "brightness": m.brightness,
            }
            for m in measurements
        ]
        return pd.DataFrame(rows)

    def _build_faults_df(self, fault_events: list) -> pd.DataFrame:
        if not fault_events:
            return pd.DataFrame(columns=["fault_id", "fault_type", "execution_id"])
        rows = [
            {
                "fault_id": fe.fault_id,
                "fault_type": fe.fault_type,
                "execution_id": fe.execution_id,
                "cycle": fe.cycle,
            }
            for fe in fault_events
        ]
        return pd.DataFrame(rows)

    def summarize(self, execution_id: str) -> AnalyticsSummary:
        """Generate a full analytics summary for the given execution.

        Args:
            execution_id: Execution identifier to filter on.

        Returns:
            AnalyticsSummary with all computed metrics.
        """
        df = self._results_df
        if not df.empty:
            df = df[df["execution_id"] == execution_id]

        total = len(df)
        if total == 0:
            return AnalyticsSummary(
                execution_id=execution_id,
                total_tests=0, passed=0, failed=0,
                pass_rate=0.0, fail_rate=0.0,
                avg_duration_ms=0.0,
            )

        passed = int((df["status"] == "PASS").sum())
        failed = int((df["status"] == "FAIL").sum())
        pass_rate = round(passed / total * 100, 2)
        fail_rate = round(failed / total * 100, 2)
        avg_duration = round(float(df["duration_ms"].mean()), 3)

        slowest = (
            df.nlargest(5, "duration_ms")[["test_name", "duration_ms", "status"]]
            .to_dict(orient="records")
        )

        failures_by_cat: dict[str, int] = {}
        if failed > 0:
            fail_df = df[df["status"] == "FAIL"]
            failures_by_cat = fail_df.groupby("category").size().to_dict()

        failures_by_fw: dict[str, int] = {}
        if failed > 0:
            fail_df = df[df["status"] == "FAIL"]
            failures_by_fw = fail_df.groupby("firmware_version").size().to_dict()

        # Measurement metrics
        mdf = self._measurements_df
        if not mdf.empty:
            mdf = mdf[mdf["execution_id"] == execution_id]

        avg_voltage: float | None = None
        avg_current: float | None = None
        avg_temp: float | None = None
        temp_corr: float | None = None

        if not mdf.empty:
            if "voltage" in mdf and mdf["voltage"].notna().any():
                avg_voltage = round(float(mdf["voltage"].dropna().mean()), 4)
            if "current" in mdf and mdf["current"].notna().any():
                avg_current = round(float(mdf["current"].dropna().mean()), 4)
            if "temperature" in mdf and mdf["temperature"].notna().any():
                avg_temp = round(float(mdf["temperature"].dropna().mean()), 2)

        # Most common faults
        faults_list: list[dict] = []
        fdf = self._faults_df
        if not fdf.empty:
            fdf = fdf[fdf["execution_id"] == execution_id]
            if not fdf.empty:
                faults_list = (
                    fdf.groupby("fault_type").size()
                    .reset_index(name="count")
                    .sort_values("count", ascending=False)
                    .to_dict(orient="records")
                )

        return AnalyticsSummary(
            execution_id=execution_id,
            total_tests=total,
            passed=passed,
            failed=failed,
            pass_rate=pass_rate,
            fail_rate=fail_rate,
            avg_duration_ms=avg_duration,
            slowest_tests=slowest,
            failures_by_category={str(k): int(v) for k, v in failures_by_cat.items()},
            failures_by_firmware={str(k): int(v) for k, v in failures_by_fw.items()},
            avg_voltage=avg_voltage,
            avg_current=avg_current,
            avg_temperature=avg_temp,
            temp_failure_correlation=temp_corr,
            most_common_faults=faults_list,
        )

    def compare_runs(self, execution_ids: list[str]) -> pd.DataFrame:
        """Compare pass rates and average duration across multiple executions.

        Args:
            execution_ids: List of execution IDs to compare.

        Returns:
            DataFrame with per-run summary statistics.
        """
        rows = []
        for eid in execution_ids:
            s = self.summarize(eid)
            rows.append({
                "execution_id": eid,
                "total_tests": s.total_tests,
                "pass_rate": s.pass_rate,
                "fail_rate": s.fail_rate,
                "avg_duration_ms": s.avg_duration_ms,
            })
        return pd.DataFrame(rows)
