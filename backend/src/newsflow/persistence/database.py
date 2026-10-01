"""Runtime SQLAlchemy session wiring for durable API read models."""

from collections.abc import Iterator
from functools import lru_cache
from os import getenv

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


@lru_cache
def _session_factory(database_url: str) -> sessionmaker[Session]:
    engine = create_engine(database_url, pool_pre_ping=True)
    return sessionmaker(bind=engine)


def configured_session_factory() -> sessionmaker[Session] | None:
    """Return a reusable factory only when durable storage is configured."""
    database_url = getenv("DATABASE_URL", "").strip()
    return _session_factory(database_url) if database_url else None


def database_session() -> Iterator[Session | None]:
    """Yield a request-scoped session, or None in an unconfigured local shell."""
    factory = configured_session_factory()
    if factory is None:
        yield None
        return
    with factory() as session:
        yield session


def reset_database_session_factory() -> None:
    """Clear cached engines for isolated tests or an explicit configuration reload."""
    _session_factory.cache_clear()
