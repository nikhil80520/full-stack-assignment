"""
Pydantic v2 schemas for the Transfers feature.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransferRequest(BaseModel):
    """Request body for a money transfer between accounts."""

    model_config = ConfigDict(extra="forbid")

    from_account_id: UUID = Field(..., description="Source account UUID.")
    to_account_id: UUID = Field(..., description="Destination account UUID.")
    amount: Decimal = Field(
        ...,
        gt=0,
        description="Transfer amount (> 0, max 2 decimal places).",
        json_schema_extra={"examples": ["30.00"]},
    )
    description: str = Field(
        default="",
        max_length=500,
        description="Optional transfer description.",
    )
    reference_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Idempotency key for this transfer.",
        json_schema_extra={"examples": ["XFER-001"]},
    )

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if not v.is_finite():
            raise ValueError("Amount must be a finite number.")
        if v.as_tuple().exponent < -2:  # type: ignore[operator]
            raise ValueError("Amount must have at most 2 decimal places.")
        return v

    @field_validator("reference_id")
    @classmethod
    def strip_reference_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("reference_id must not be empty after trimming.")
        return v


class TransferResponse(BaseModel):
    """Successful transfer response."""

    model_config = ConfigDict(from_attributes=True)

    transfer_reference_id: str
    from_account_id: UUID
    to_account_id: UUID
    amount: Decimal
    debit_transaction_id: UUID
    credit_transaction_id: UUID
    description: str
    created_at: datetime
