"""
Application factory.

- Registers all feature routers.
- Installs unified exception handlers.
- Creates DB tables and immutability triggers on startup.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.error_handlers import register_exception_handlers
from app.db.base import Base
from app.db.session import engine

# Import models so they are registered with Base.metadata before create_all
from app.features.accounts.model import Account  # noqa: F401
from app.features.transactions.model import (
    Transaction,  # noqa: F401
    create_immutability_triggers,
)

# Import routers
from app.features.accounts.routes import router as accounts_router
from app.features.transactions.routes import router as transactions_router
from app.features.transfers.routes import router as transfers_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables and triggers
    Base.metadata.create_all(bind=engine)
    create_immutability_triggers(engine)
    yield
    # Shutdown: nothing to clean up


app = FastAPI(
    title="Transaction Ledger API",
    description=(
        "A backend API for a simple transaction ledger system. "
        "Allows creating accounts, performing credit/debit transactions, "
        "retrieving balances and transaction history, and transferring money "
        "between accounts."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Exception handlers — unified error envelope
register_exception_handlers(app)

# Feature routers
app.include_router(accounts_router)
app.include_router(transactions_router)
app.include_router(transfers_router)
