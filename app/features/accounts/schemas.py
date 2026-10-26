"""
Pydantic v2 request / response schemas for the Accounts feature.

``extra="forbid"`` on ``AccountCreate`` ensures the client cannot sneak
in a ``balance`` field (or anything else beyond ``name``).
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AccountCreate(BaseModel):
    """Request body for creating a new account."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Account holder name (required, non-empty after trimming).",
        json_schema_extra={"examples": ["Alice Johnson"]},
    )


class AccountResponse(BaseModel):
    """Full account representation returned to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    balance: Decimal = Field(
        ..., description="Current balance with 2 decimal places.", examples=["0.00"]
    )
    created_at: datetime


class BalanceResponse(BaseModel):
    """Lightweight response for the balance endpoint."""

    model_config = ConfigDict(from_attributes=True)

    account_id: UUID
    balance: Decimal = Field(
        ..., description="Current balance with 2 decimal places.", examples=["150.00"]
    )
