"""
Transfer routes — POST /transfers.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.features.transfers import service
from app.features.transfers.schemas import TransferRequest, TransferResponse

router = APIRouter(prefix="/transfers", tags=["Transfers"])


@router.post(
    "",
    response_model=TransferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Transfer money between accounts",
    description=(
        "Atomically debits the source account and credits the destination. "
        "Creates two linked transactions. Idempotent via `reference_id`. "
        "Both accounts must exist and be different; source must have sufficient balance."
    ),
    responses={
        201: {"description": "Transfer completed successfully."},
        404: {"description": "One or both accounts not found."},
        409: {"description": "Duplicate transfer (same reference_id)."},
        422: {
            "description": (
                "Validation error, insufficient balance, or same-account transfer."
            )
        },
    },
)
def create_transfer(body: TransferRequest, db: Session = Depends(get_db)):
    return service.execute_transfer(
        db,
        body.from_account_id,
        body.to_account_id,
        body.amount,
        body.description,
        body.reference_id,
    )
