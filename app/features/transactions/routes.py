"""
Transaction routes.

Exposes:
- POST /accounts/{account_id}/transactions  — add a transaction
- GET  /accounts/{account_id}/transactions  — list transaction history

PUT, PATCH, DELETE are explicitly NOT defined so FastAPI returns 405.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.features.transactions import service
from app.features.transactions.schemas import (
    PaginatedResponse,
    TransactionCreate,
    TransactionResponse,
    TransactionType,
)

router = APIRouter(prefix="/accounts/{account_id}/transactions", tags=["Transactions"])


@router.post(
    "",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a transaction",
    description=(
        "Creates a credit or debit transaction for the specified account. "
        "The balance update and transaction insert are atomic. "
        "Duplicate `reference_id` for the same account returns 409."
    ),
    responses={
        201: {"description": "Transaction created successfully."},
        404: {"description": "Account not found."},
        409: {"description": "Duplicate reference_id — transaction already exists."},
        422: {"description": "Validation error or insufficient balance."},
    },
)
def add_transaction(
    account_id: UUID,
    body: TransactionCreate,
    db: Session = Depends(get_db),
):
    return service.add_transaction(
        db,
        account_id,
        body.type,
        body.amount,
        body.description,
        body.reference_id,
    )


@router.get(
    "",
    response_model=PaginatedResponse[TransactionResponse],
    summary="Get transaction history",
    description=(
        "Returns paginated, latest-first transaction history for the account. "
        "Optionally filter by transaction type."
    ),
    responses={
        200: {"description": "Transaction history retrieved successfully."},
        404: {"description": "Account not found."},
        422: {"description": "Invalid query parameters."},
    },
)
def get_transactions(
    account_id: UUID,
    type: TransactionType | None = Query(
        default=None, description="Filter by transaction type."
    ),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)."),
    limit: int = Query(
        default=10, ge=1, le=100, description="Items per page (1–100)."
    ),
    db: Session = Depends(get_db),
):
    return service.get_transactions(db, account_id, type, page, limit)
