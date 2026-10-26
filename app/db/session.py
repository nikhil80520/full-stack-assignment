"""
Database engine, session factory, and FastAPI dependency.

The engine is created from DATABASE_URL.  For SQLite the connect_args
include ``check_same_thread=False`` (required by FastAPI's thread pool)
and we enable WAL mode + ``PRAGMA journal_mode`` for better concurrent
write support.
"""

from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_connect_args: dict = {}
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    _connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
)

# SQLite: enable WAL journal mode and foreign keys on every connection
if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session and closes it after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
