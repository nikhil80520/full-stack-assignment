"""
Transaction business logic.

All balance mutations happen inside a single DB transaction.
On SQLite we rely on the engine-level ``isolation_level`` set during
session creation.  On PostgreSQL we use ``SELECT ... FOR UPDATE``
to lock the account row.
"""

import math
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AccountNotFound,
    DuplicateTransaction,
    InsufficientBalance,
)
from app.features.accounts.model import Account
from app.features.transactions.model import Transaction
from app.features.transactions.schemas import (
    PaginatedResponse,
    PaginationMeta,
    TransactionResponse,
    TransactionType,
)


def _lock_account(db: Session, account_id: str) -> Account:
    """Load and lock the account row.

    - PostgreSQL: ``FOR UPDATE`` row-level lock.
    - SQLite: We rely on the journal-level write lock
      (WAL mode + the serialized nature of SQLite writes).
    """
    is_sqlite = "sqlite" in db.bind.dialect.name  # type: ignore[union-attr]
    stmt = select(Account).where(Account.id == account_id)
    if not is_sqlite:
        stmt = stmt.with_for_update()
    account = db.execute(stmt).scalar_one_or_none()
    if account is None:
        raise AccountNotFound(f"Account {account_id} not found.")
    return account


def _serialize_transaction(txn: Transaction) -> dict:
    """Convert a Transaction ORM instance to a dict for JSON serialisation."""
    return {
        "id": txn.id,
        "account_id": txn.account_id,
        "type": txn.type,
        "amount": str(txn.amount),
        "description": txn.description,
        "reference_id": txn.reference_id,
        "created_at": txn.created_at.isoformat() if txn.created_at else None,
    }


def add_transaction(
    db: Session,
    account_id: UUID,
    txn_type: TransactionType,
    amount: Decimal,
    description: str,
    reference_id: str,
) -> Transaction:
    """Create a transaction and update the account balance atomically."""
    account_id_str = str(account_id)

    # Check for duplicate reference_id first
    existing = (
        db.query(Transaction)
        .filter_by(account_id=account_id_str, reference_id=reference_id)
        .first()
    )
    if existing:
        raise DuplicateTransaction(
            existing_transaction=_serialize_transaction(existing)
        )

    account = _lock_account(db, account_id_str)

    # Apply balance change
    if txn_type == TransactionType.debit:
        if account.balance < amount:
            raise InsufficientBalance(
                f"Cannot debit {amount}; current balance is {account.balance}."
            )
        account.balance -= amount
    else:
        account.balance += amount

    txn = Transaction(
        account_id=account_id_str,
        type=txn_type.value,
        amount=amount,
        description=description,
        reference_id=reference_id,
    )
    db.add(txn)

    # Attempt flush — the UNIQUE constraint is the final guard against races
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        # Race: another request inserted the same reference_id
        existing = (
            db.query(Transaction)
            .filter_by(account_id=account_id_str, reference_id=reference_id)
            .first()
        )
        raise DuplicateTransaction(
            existing_transaction=_serialize_transaction(existing) if existing else None
        )

    db.commit()
    db.refresh(txn)
    return txn


def get_transactions(
    db: Session,
    account_id: UUID,
    txn_type: TransactionType | None,
    page: int,
    limit: int,
) -> dict:
    """Return paginated, sorted transaction history."""
    account_id_str = str(account_id)

    # Verify account exists
    account = db.get(Account, account_id_str)
    if account is None:
        raise AccountNotFound(f"Account {account_id} not found.")

    # Base query
    q = db.query(Transaction).filter(Transaction.account_id == account_id_str)

    if txn_type is not None:
        q = q.filter(Transaction.type == txn_type.value)

    total_records = q.count()
    total_pages = max(1, math.ceil(total_records / limit))

    items = (
        q.order_by(Transaction.created_at.desc(), Transaction.seq.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "data": [TransactionResponse.model_validate(t) for t in items],
        "pagination": PaginationMeta(
            current_page=page,
            page_size=limit,
            total_records=total_records,
            total_pages=total_pages,
        ),
    }
