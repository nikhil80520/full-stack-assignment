"""
Account SQLAlchemy model.

Balance is stored as NUMERIC(18, 2) — exact decimal, never float.
A CHECK constraint ensures balance can never go negative at the DB level.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, Numeric, String
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Account(Base):
    __tablename__ = "accounts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    balance = Column(Numeric(18, 2), nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    # Relationship to transactions (for ORM convenience, not required for queries)
    transactions = relationship("Transaction", back_populates="account", lazy="dynamic")

    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_accounts_balance_non_negative"),
    )
