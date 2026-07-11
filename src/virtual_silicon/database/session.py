"""SQLAlchemy session management and database initialization."""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from virtual_silicon.database.models import Base

logger = logging.getLogger(__name__)


class DatabaseSession:
    """Manages a SQLAlchemy engine and session factory for a given database URL."""

    def __init__(self, database_url: str = "sqlite:///./virtual_silicon.db") -> None:
        """Initialize the database session manager.

        Args:
            database_url: SQLAlchemy-compatible database URL.
        """
        self._url = database_url
        if ":memory:" in database_url:
            self._engine = create_engine(
                database_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        elif database_url.startswith("sqlite"):
            self._engine = create_engine(
                database_url, connect_args={"check_same_thread": False}
            )
        else:
            self._engine = create_engine(database_url)
        self._session_factory = sessionmaker(bind=self._engine, autoflush=False, autocommit=False)
        logger.debug("DatabaseSession created for %s.", database_url)

    def create_tables(self) -> None:
        """Create all ORM tables if they do not already exist."""
        Base.metadata.create_all(self._engine)
        logger.info("Database tables created/verified.")

    def drop_tables(self) -> None:
        """Drop all ORM tables (use for test teardown)."""
        Base.metadata.drop_all(self._engine)
        logger.warning("All database tables dropped.")

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Context manager that provides a transactional database session.

        Yields:
            An active SQLAlchemy Session.
        """
        sess: Session = self._session_factory()
        try:
            yield sess
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()

    @property
    def engine(self) -> object:
        """The underlying SQLAlchemy engine."""
        return self._engine


def get_session(database_url: str = "sqlite:///./virtual_silicon.db") -> DatabaseSession:
    """Factory function to create a DatabaseSession.

    Args:
        database_url: SQLAlchemy-compatible database URL.

    Returns:
        Initialized DatabaseSession instance.
    """
    db = DatabaseSession(database_url)
    db.create_tables()
    return db
