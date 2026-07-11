"""Repository pattern for test data persistence."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from virtual_silicon.database.models import (
    FaultEvent,
    Measurement,
    ProtocolTransaction,
    TestCase,
    TestResult,
    TestRun,
)
from virtual_silicon.database.session import DatabaseSession

logger = logging.getLogger(__name__)


class TestRepository:
    """Provides CRUD operations for test execution data.

    Uses the repository pattern to decouple business logic from database access.
    """

    def __init__(self, db: DatabaseSession) -> None:
        """Initialize the repository.

        Args:
            db: DatabaseSession instance.
        """
        self._db = db

    def create_test_run(
        self,
        execution_id: str,
        firmware_version: str = "1.0",
        chip_version: str = "VS-1000-A",
        environment: str = "virtual",
    ) -> TestRun:
        """Create and persist a new test run record.

        Args:
            execution_id: Unique execution identifier.
            firmware_version: Firmware version string.
            chip_version: Chip version string.
            environment: Test environment label.

        Returns:
            Persisted TestRun instance.
        """
        with self._db.session() as sess:
            run = TestRun(
                execution_id=execution_id,
                firmware_version=firmware_version,
                chip_version=chip_version,
                environment=environment,
                status="running",
            )
            sess.add(run)
            sess.flush()
            sess.refresh(run)
            run_id = run.id
        logger.info("Created test run: %s (id=%s).", execution_id, run_id)
        return self.get_test_run(execution_id)  # type: ignore[return-value]

    def get_test_run(self, execution_id: str) -> TestRun | None:
        """Retrieve a test run by execution ID.

        Args:
            execution_id: Execution identifier.

        Returns:
            TestRun if found, else None.
        """
        with self._db.session() as sess:
            return sess.query(TestRun).filter_by(execution_id=execution_id).first()

    def finish_test_run(self, execution_id: str, passed: int, failed: int) -> None:
        """Mark a test run as complete with pass/fail totals.

        Args:
            execution_id: Execution identifier.
            passed: Number of passed tests.
            failed: Number of failed tests.
        """
        with self._db.session() as sess:
            run = sess.query(TestRun).filter_by(execution_id=execution_id).first()
            if run:
                run.finished_at = datetime.now(UTC)
                run.passed = passed
                run.failed = failed
                run.total_tests = passed + failed
                run.status = "passed" if failed == 0 else "failed"

    def save_test_result(
        self,
        execution_id: str,
        test_name: str,
        category: str,
        status: str,
        duration_ms: float = 0.0,
        expected: str = "",
        actual: str = "",
        error_message: str = "",
        firmware_version: str = "1.0",
        chip_version: str = "VS-1000-A",
    ) -> None:
        """Save a test result associated with the given execution run.

        Args:
            execution_id: Execution identifier.
            test_name: Name of the test.
            category: Test category (e.g. 'memory', 'register').
            status: 'PASS' or 'FAIL'.
            duration_ms: Test duration in milliseconds.
            expected: Expected result description.
            actual: Actual result description.
            error_message: Error details if any.
            firmware_version: Firmware version.
            chip_version: Chip version.
        """
        with self._db.session() as sess:
            run = sess.query(TestRun).filter_by(execution_id=execution_id).first()
            if not run:
                logger.warning("No test run found for execution_id=%s.", execution_id)
                return
            tc = TestCase(test_run_id=run.id, name=test_name, category=category)
            sess.add(tc)
            sess.flush()
            result = TestResult(
                test_case_id=tc.id,
                execution_id=execution_id,
                test_name=test_name,
                category=category,
                status=status,
                duration_ms=duration_ms,
                expected_result=expected,
                actual_result=actual,
                error_message=error_message or None,
                firmware_version=firmware_version,
                chip_version=chip_version,
            )
            sess.add(result)

    def save_measurement(
        self,
        execution_id: str,
        voltage: float | None = None,
        current: float | None = None,
        temperature: float | None = None,
        brightness: float | None = None,
    ) -> None:
        """Persist an instrument measurement snapshot.

        Args:
            execution_id: Execution identifier.
            voltage: Voltage in volts.
            current: Current in amperes.
            temperature: Temperature in Celsius.
            brightness: Brightness in luminance units.
        """
        with self._db.session() as sess:
            run = sess.query(TestRun).filter_by(execution_id=execution_id).first()
            if not run:
                return
            m = Measurement(
                test_run_id=run.id,
                execution_id=execution_id,
                voltage=voltage,
                current=current,
                temperature=temperature,
                brightness=brightness,
            )
            sess.add(m)

    def save_fault_event(
        self,
        execution_id: str,
        fault_id: str,
        fault_type: str,
        description: str = "",
        cycle: int = 0,
    ) -> None:
        """Persist a fault injection event.

        Args:
            execution_id: Execution identifier.
            fault_id: Fault configuration ID.
            fault_type: Fault type string.
            description: Human-readable description.
            cycle: Chip cycle count at fault injection.
        """
        with self._db.session() as sess:
            run = sess.query(TestRun).filter_by(execution_id=execution_id).first()
            if not run:
                return
            fe = FaultEvent(
                test_run_id=run.id,
                execution_id=execution_id,
                fault_id=fault_id,
                fault_type=fault_type,
                description=description,
                cycle=cycle,
            )
            sess.add(fe)

    def save_protocol_transaction(
        self,
        execution_id: str,
        protocol: str,
        direction: str,
        address: int,
        register: int,
        data: list[int],
        success: bool,
        error: str = "",
    ) -> None:
        """Persist a protocol transaction log entry."""
        with self._db.session() as sess:
            run = sess.query(TestRun).filter_by(execution_id=execution_id).first()
            if not run:
                return
            pt = ProtocolTransaction(
                test_run_id=run.id,
                execution_id=execution_id,
                protocol=protocol,
                direction=direction,
                address=address,
                register=register,
                data=json.dumps(data),
                success=success,
                error=error,
            )
            sess.add(pt)

    def get_all_results(self, execution_id: str | None = None) -> list[TestResult]:
        """Retrieve test results, optionally filtered by execution ID."""
        with self._db.session() as sess:
            q = sess.query(TestResult)
            if execution_id:
                q = q.filter_by(execution_id=execution_id)
            results = q.all()
            sess.expunge_all()
            return results

    def get_measurements(self, execution_id: str | None = None) -> list[Measurement]:
        """Retrieve measurements, optionally filtered by execution ID."""
        with self._db.session() as sess:
            q = sess.query(Measurement)
            if execution_id:
                q = q.filter_by(execution_id=execution_id)
            items = q.all()
            sess.expunge_all()
            return items

    def list_test_runs(self) -> list[TestRun]:
        """Return all test runs ordered by start time."""
        with self._db.session() as sess:
            runs = sess.query(TestRun).order_by(TestRun.started_at).all()
            sess.expunge_all()
            return runs
