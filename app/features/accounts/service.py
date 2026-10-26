"""
Account business logic and database queries.
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AccountNotFound
from app.features.accounts.model import Account


def create_account(db: Session, name: str) -> Account:
    """Create a new account with balance = 0."""
    account = Account(name=name.strip(), balance=Decimal("0.00"))
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def get_account_or_404(db: Session, account_id: UUID) -> Account:
    """Return the account or raise AccountNotFound."""
    account = db.get(Account, str(account_id))
    if account is None:
        raise AccountNotFound(f"Account {account_id} not found.")
    return account


def get_balance(db: Session, account_id: UUID) -> dict:
    """Return a dict suitable for BalanceResponse."""
    account = get_account_or_404(db, account_id)
    return {"account_id": account.id, "balance": account.balance}
