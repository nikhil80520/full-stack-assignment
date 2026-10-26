"""
Transaction SQLAlchemy model.

Key DB constraints:
- UNIQUE(account_id, reference_id) — prevents duplicate transactions per account.
- CHECK(type IN ('credit','debit'))
- CHECK(amount > 0)
- FOREIGN KEY to accounts.

Immutability triggers (SQLite):
- Blocks UPDATE on the transactions table.
- Blocks DELETE on the transactions table.
These are created in ``create_immutability_triggers()``, called at startup.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Transaction(Base):
    __tablename__ = "transactions"

    seq = Column(Integer, primary_key=True, autoincrement=True)
    id = Column(
        String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )
    account_id = Column(
        String(36), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    type = Column(String(6), nullable=False)  # 'credit' or 'debit'
    amount = Column(Numeric(18, 2), nullable=False)
    description = Column(String(500), nullable=False, default="")
    reference_id = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    account = relationship("Account", back_populates="transactions")

    __table_args__ = (
        UniqueConstraint("account_id", "reference_id", name="uq_txn_account_reference"),
        CheckConstraint("type IN ('credit', 'debit')", name="ck_txn_type"),
        CheckConstraint("amount > 0", name="ck_txn_amount_positive"),
    )


# ---------------------------------------------------------------------------
# SQLite immutability triggers
# ---------------------------------------------------------------------------

_TRIGGER_NO_UPDATE = """
CREATE TRIGGER IF NOT EXISTS trg_transactions_no_update
BEFORE UPDATE ON transactions
BEGIN
    SELECT RAISE(ABORT, 'Transactions are immutable and cannot be updated.');
END;
"""

_TRIGGER_NO_DELETE = """
CREATE TRIGGER IF NOT EXISTS trg_transactions_no_delete
BEFORE DELETE ON transactions
BEGIN
    SELECT RAISE(ABORT, 'Transactions are immutable and cannot be deleted.');
END;
"""


def create_immutability_triggers(engine) -> None:
    """Create SQLite triggers that block UPDATE and DELETE on transactions."""
    if engine.url.drivername.startswith("sqlite"):
        with engine.connect() as conn:
            conn.execute(text(_TRIGGER_NO_UPDATE))
            conn.execute(text(_TRIGGER_NO_DELETE))
            conn.commit()
