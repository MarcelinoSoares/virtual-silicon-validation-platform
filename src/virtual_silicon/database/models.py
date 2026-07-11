"""SQLAlchemy ORM models for test execution data."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""


class TestRun(Base):
    """Top-level record for a complete test execution run."""

    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    firmware_version: Mapped[str] = mapped_column(String(32), default="1.0")
    chip_version: Mapped[str] = mapped_column(String(32), default="VS-1000-A")
    environment: Mapped[str] = mapped_column(String(64), default="virtual")
    total_tests: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="running")

    test_cases: Mapped[list[TestCase]] = relationship(
        back_populates="test_run", cascade="all, delete-orphan"
    )
    measurements: Mapped[list[Measurement]] = relationship(
        back_populates="test_run", cascade="all, delete-orphan"
    )
    fault_events: Mapped[list[FaultEvent]] = relationship(
        back_populates="test_run", cascade="all, delete-orphan"
    )
    transactions: Mapped[list[ProtocolTransaction]] = relationship(
        back_populates="test_run", cascade="all, delete-orphan"
    )


class TestCase(Base):
    """A single test case belonging to a test run."""

    __tablename__ = "test_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_run_id: Mapped[int] = mapped_column(ForeignKey("test_runs.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="general")

    test_run: Mapped[TestRun] = relationship(back_populates="test_cases")
    results: Mapped[list[TestResult]] = relationship(
        back_populates="test_case", cascade="all, delete-orphan"
    )


class TestResult(Base):
    """Result record for a single test case execution."""

    __tablename__ = "test_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"), nullable=False)
    execution_id: Mapped[str] = mapped_column(String(64), nullable=False)
    test_name: Mapped[str] = mapped_column(String(256), nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="general")
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    expected_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    firmware_version: Mapped[str] = mapped_column(String(32), default="1.0")
    chip_version: Mapped[str] = mapped_column(String(32), default="VS-1000-A")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    test_case: Mapped[TestCase] = relationship(back_populates="results")


class Measurement(Base):
    """Instrument measurement record associated with a test run."""

    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_run_id: Mapped[int] = mapped_column(ForeignKey("test_runs.id"), nullable=False)
    execution_id: Mapped[str] = mapped_column(String(64), nullable=False)
    voltage: Mapped[float | None] = mapped_column(Float, nullable=True)
    current: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    brightness: Mapped[float | None] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    test_run: Mapped[TestRun] = relationship(back_populates="measurements")


class FaultEvent(Base):
    """Record of a fault injection event."""

    __tablename__ = "fault_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_run_id: Mapped[int] = mapped_column(ForeignKey("test_runs.id"), nullable=False)
    execution_id: Mapped[str] = mapped_column(String(64), nullable=False)
    fault_id: Mapped[str] = mapped_column(String(64), nullable=False)
    fault_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    cycle: Mapped[int] = mapped_column(Integer, default=0)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    test_run: Mapped[TestRun] = relationship(back_populates="fault_events")


class ProtocolTransaction(Base):
    """Log of a single I2C or SPI transaction."""

    __tablename__ = "protocol_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_run_id: Mapped[int] = mapped_column(ForeignKey("test_runs.id"), nullable=False)
    execution_id: Mapped[str] = mapped_column(String(64), nullable=False)
    protocol: Mapped[str] = mapped_column(String(8), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    address: Mapped[int] = mapped_column(Integer, default=0)
    register: Mapped[int] = mapped_column(Integer, default=0)
    data: Mapped[str] = mapped_column(Text, default="")
    success: Mapped[bool] = mapped_column(Integer, default=1)
    error: Mapped[str] = mapped_column(Text, default="")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    test_run: Mapped[TestRun] = relationship(back_populates="transactions")
