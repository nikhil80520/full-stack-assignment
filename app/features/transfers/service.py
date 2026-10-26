"""
Transfer service — atomic money transfer between two accounts.

Both the debit and credit happen inside ONE database transaction.
Account rows are locked in sorted-id order to prevent deadlocks.

Idempotency: the client-supplied ``reference_id`` is used to derive
two child reference IDs:
    - ``{reference_id}-debit``   (on the source account)
    - ``{reference_id}-credit``  (on the destination account)
If both already exist, the transfer is considered a duplicate and
returns 409.
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AccountNotFound,
    DuplicateTransaction,
    InsufficientBalance,
    SameAccountTransfer,
)
from app.features.accounts.model import Account
from app.features.transactions.model import Transaction


def _lock_accounts_ordered(
    db: Session, id_a: str, id_b: str
) -> tuple[Account, Account]:
    """Lock two account rows in deterministic (sorted) order to avoid deadlocks."""
    first_id, second_id = sorted([id_a, id_b])
    is_sqlite = "sqlite" in db.bind.dialect.name  # type: ignore[union-attr]

    def _load(aid: str) -> Account:
        stmt = select(Account).where(Account.id == aid)
        if not is_sqlite:
            stmt = stmt.with_for_update()
        acc = db.execute(stmt).scalar_one_or_none()
        if acc is None:
            raise AccountNotFound(f"Account {aid} not found.")
        return acc

    acc_first = _load(first_id)
    acc_second = _load(second_id)

    # Return in caller's order
    if first_id == id_a:
        return acc_first, acc_second
    return acc_second, acc_first


def execute_transfer(
    db: Session,
    from_account_id: UUID,
    to_account_id: UUID,
    amount: Decimal,
    description: str,
    reference_id: str,
) -> dict:
    """Atomically debit source and credit destination."""
    from_id = str(from_account_id)
    to_id = str(to_account_id)

    if from_id == to_id:
        raise SameAccountTransfer()

    debit_ref = f"{reference_id}-debit"
    credit_ref = f"{reference_id}-credit"

    # Check idempotency — if BOTH child txns exist, it's a duplicate
    existing_debit = (
        db.query(Transaction)
        .filter_by(account_id=from_id, reference_id=debit_ref)
        .first()
    )
    existing_credit = (
        db.query(Transaction)
        .filter_by(account_id=to_id, reference_id=credit_ref)
        .first()
    )
    if existing_debit and existing_credit:
        raise DuplicateTransaction(
            message="This transfer has already been processed.",
            existing_transaction={
                "debit_transaction_id": existing_debit.id,
                "credit_transaction_id": existing_credit.id,
            },
        )

    source, dest = _lock_accounts_ordered(db, from_id, to_id)

    if source.balance < amount:
        raise InsufficientBalance(
            f"Cannot transfer {amount}; source balance is {source.balance}."
        )

    source.balance -= amount
    dest.balance += amount

    now = datetime.now(timezone.utc)

    txn_debit = Transaction(
        account_id=from_id,
        type="debit",
        amount=amount,
        description=description or f"Transfer to {to_id}",
        reference_id=debit_ref,
        created_at=now,
    )
    txn_credit = Transaction(
        account_id=to_id,
        type="credit",
        amount=amount,
        description=description or f"Transfer from {from_id}",
        reference_id=credit_ref,
        created_at=now,
    )
    db.add(txn_debit)
    db.add(txn_credit)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise DuplicateTransaction(
            message="This transfer has already been processed (race condition)."
        )

    db.commit()
    db.refresh(txn_debit)
    db.refresh(txn_credit)

    return {
        "transfer_reference_id": reference_id,
        "from_account_id": from_id,
        "to_account_id": to_id,
        "amount": amount,
        "debit_transaction_id": txn_debit.id,
        "credit_transaction_id": txn_credit.id,
        "description": description,
        "created_at": now,
    }
