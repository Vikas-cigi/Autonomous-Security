"""SQLAlchemy engine / session factory for DI."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from evidence_repository.persistence.orm import Base


def create_db_engine(
    database_url: str,
    *,
    echo: bool = False,
    pool_pre_ping: bool = True,
) -> Engine:
    """
    Create a SQLAlchemy engine.

    Examples:
        postgresql+psycopg://user:pass@localhost:5432/xolaris
        sqlite+pysqlite:///:memory:
    """

    return create_engine(
        database_url,
        echo=echo,
        pool_pre_ping=pool_pre_ping,
        future=True,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Bind a sessionmaker to ``engine``."""

    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_schema(engine: Engine) -> None:
    """Create all Evidence Repository tables."""

    Base.metadata.create_all(bind=engine)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""

    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class SessionFactory:
    """Thin DI-friendly wrapper around ``sessionmaker``."""

    def __init__(
        self,
        database_url: str,
        *,
        echo: bool = False,
        create_tables: bool = False,
    ) -> None:
        self.engine = create_db_engine(database_url, echo=echo)
        if create_tables:
            init_schema(self.engine)
        self._factory = create_session_factory(self.engine)

    def __call__(self) -> Session:
        return self._factory()

    @contextmanager
    def session(self) -> Iterator[Session]:
        with session_scope(self._factory) as session:
            yield session
