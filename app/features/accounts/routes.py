"""
Account routes — thin layer between HTTP and the service.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.features.accounts import service
from app.features.accounts.schemas import AccountCreate, AccountResponse, BalanceResponse

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.post(
    "",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new account",
    description=(
        "Creates a new account with balance = 0. "
        "The client may NOT supply a `balance` field; doing so returns 422."
    ),
    responses={
        201: {"description": "Account created successfully."},
        422: {"description": "Validation error (e.g. extra fields, missing name)."},
    },
)
def create_account(body: AccountCreate, db: Session = Depends(get_db)):
    return service.create_account(db, body.name)


@router.get(
    "/{account_id}/balance",
    response_model=BalanceResponse,
    summary="Get account balance",
    description="Returns the current balance for the given account.",
    responses={
        200: {"description": "Balance retrieved successfully."},
        404: {"description": "Account not found."},
    },
)
def get_balance(account_id: UUID, db: Session = Depends(get_db)):
    return service.get_balance(db, account_id)
