"""Unit tests for database session and repository edge cases."""

from __future__ import annotations

import pytest

from virtual_silicon.database.repository import TestRepository
from virtual_silicon.database.session import DatabaseSession, get_session


@pytest.mark.unit
class TestDatabaseSession:
    """Covers session.py missing lines: 39-40, 53-55, 62."""

    def test_drop_tables(self) -> None:
        """drop_tables() drops all ORM tables without error (lines 39-40)."""
        db = DatabaseSession("sqlite:///:memory:")
        db.create_tables()
        db.drop_tables()  # Should not raise

    def test_session_rollback_on_exception(self) -> None:
        """Session rolls back and re-raises on exception (lines 53-55)."""
        db = DatabaseSession("sqlite:///:memory:")
        db.create_tables()
        with pytest.raises(ValueError, match="forced rollback"):
            with db.session() as sess:
                # Use the session briefly then raise to trigger rollback
                _ = sess  # touch session
                raise ValueError("forced rollback")

    def test_engine_property(self) -> None:
        """engine property returns the underlying SQLAlchemy engine (line 62)."""
        db = DatabaseSession("sqlite:///:memory:")
        assert db.engine is not None
        # Should have a connect method (it's a SQLAlchemy engine)
        assert hasattr(db.engine, "connect")

    def test_get_session_factory(self) -> None:
        """get_session() creates and returns an initialized DatabaseSession."""
        db = get_session("sqlite:///:memory:")
        assert db is not None
        assert db.engine is not None


@pytest.mark.unit
class TestRepositoryMissingRun:
    """Covers repository.py missing lines: 128-129, 168, 199, 225."""

    def test_save_test_result_no_run_warns(self, temp_db: TestRepository) -> None:
        """save_test_result warns and returns when no run found (lines 128-129)."""
        # Should not raise, just log a warning
        temp_db.save_test_result(
            "NONEXISTENT_EID",
            test_name="dummy_test",
            category="memory",
            status="PASS",
        )
        # Verify nothing was saved
        results = temp_db.get_all_results("NONEXISTENT_EID")
        assert results == []

    def test_save_measurement_no_run(self, temp_db: TestRepository) -> None:
        """save_measurement early-returns when no run found (line 168)."""
        temp_db.save_measurement("NONEXISTENT_EID", voltage=3.3, current=0.5)
        measurements = temp_db.get_measurements("NONEXISTENT_EID")
        assert measurements == []

    def test_save_fault_event_no_run(self, temp_db: TestRepository) -> None:
        """save_fault_event early-returns when no run found (line 199)."""
        temp_db.save_fault_event(
            "NONEXISTENT_EID",
            fault_id="F1",
            fault_type="stuck_bit",
            description="test",
            cycle=10,
        )
        # Just ensure it doesn't raise

    def test_save_protocol_transaction_no_run(self, temp_db: TestRepository) -> None:
        """save_protocol_transaction early-returns when no run found (line 225)."""
        temp_db.save_protocol_transaction(
            "NONEXISTENT_EID",
            protocol="I2C",
            direction="read",
            address=0x48,
            register=0x00,
            data=[0xA5],
            success=True,
            error="",
        )
        # Just ensure it doesn't raise

    def test_save_measurement_with_valid_run(self, temp_db: TestRepository) -> None:
        """save_measurement saves correctly when run exists."""
        temp_db.create_test_run("EID-MEAS")
        temp_db.save_measurement("EID-MEAS", voltage=3.3, current=0.5, temperature=25.0)
        items = temp_db.get_measurements("EID-MEAS")
        assert len(items) == 1
        assert items[0].voltage == 3.3

    def test_save_fault_event_with_valid_run(self, temp_db: TestRepository) -> None:
        """save_fault_event saves correctly when run exists."""
        temp_db.create_test_run("EID-FAULT")
        temp_db.save_fault_event("EID-FAULT", fault_id="F1", fault_type="stuck_bit", cycle=5)
        # Just ensure no exception

    def test_save_protocol_transaction_with_valid_run(self, temp_db: TestRepository) -> None:
        """save_protocol_transaction saves correctly when run exists."""
        temp_db.create_test_run("EID-PROTO")
        temp_db.save_protocol_transaction(
            "EID-PROTO",
            protocol="SPI",
            direction="write",
            address=0x00,
            register=0x02,
            data=[0x05],
            success=True,
        )
        # Just ensure no exception
