"""
Pydantic v2 schemas for the Transactions feature.

Amount validation:
- Must be > 0
- Must be a finite number (no NaN, Infinity)
- At most 2 decimal places
"""

import math
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransactionType(str, Enum):
    credit = "credit"
    debit = "debit"


class TransactionCreate(BaseModel):
    """Request body for adding a transaction."""

    model_config = ConfigDict(extra="forbid")

    type: TransactionType = Field(
        ..., description="Transaction type: 'credit' or 'debit'."
    )
    amount: Decimal = Field(
        ...,
        gt=0,
        description="Transaction amount, must be > 0 with at most 2 decimal places.",
        json_schema_extra={"examples": ["50.00"]},
    )
    description: str = Field(
        default="",
        max_length=500,
        description="Optional description of the transaction.",
    )
    reference_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique reference ID for this transaction within the account.",
        json_schema_extra={"examples": ["TXN-001"]},
    )

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        # Reject NaN / Infinity
        if not v.is_finite():
            raise ValueError("Amount must be a finite number.")
        # At most 2 decimal places
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


class TransactionResponse(BaseModel):
    """Single transaction returned to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    type: TransactionType
    amount: Decimal
    description: str
    reference_id: str
    created_at: datetime


class PaginationMeta(BaseModel):
    current_page: int
    page_size: int
    total_records: int
    total_pages: int


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    data: list[T]
    pagination: PaginationMeta
