"""
Shared pytest fixtures.

Uses a **separate in-memory SQLite** database for tests so the real DB
is never touched.  Every test function gets a fresh database (tables are
created and dropped per test via the ``db`` fixture).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.features.accounts.model import Account  # noqa: F401
from app.features.transactions.model import (
    Transaction,  # noqa: F401
    create_immutability_triggers,
)
from app.main import app

# In-memory SQLite with a static pool so all connections share the same DB
_TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(_TEST_ENGINE, "connect")
def _set_sqlite_pragmas(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_TestSession = sessionmaker(bind=_TEST_ENGINE, autocommit=False, autoflush=False)


@pytest.fixture()
def db():
    """Yield a DB session backed by a fresh in-memory database."""
    Base.metadata.create_all(bind=_TEST_ENGINE)
    create_immutability_triggers(_TEST_ENGINE)
    session = _TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=_TEST_ENGINE)


@pytest.fixture()
def client(db):
    """FastAPI TestClient that uses the test database."""

    def _override_get_db():
        try:
            yield db
        finally:
            pass  # session cleanup happens in the ``db`` fixture

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_test_account(client: TestClient, name: str = "Test User") -> dict:
    """Shortcut: create an account and return the response JSON."""
    resp = client.post("/accounts", json={"name": name})
    assert resp.status_code == 201
    return resp.json()


def credit(client: TestClient, account_id: str, amount: str, ref: str, desc: str = "") -> dict:
    resp = client.post(
        f"/accounts/{account_id}/transactions",
        json={"type": "credit", "amount": amount, "reference_id": ref, "description": desc},
    )
    return resp.json()


def debit(client: TestClient, account_id: str, amount: str, ref: str, desc: str = "") -> dict:
    resp = client.post(
        f"/accounts/{account_id}/transactions",
        json={"type": "debit", "amount": amount, "reference_id": ref, "description": desc},
    )
    return resp.json()
