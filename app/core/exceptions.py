"""
Custom exception classes for the Transaction Ledger API.

Each exception carries enough context for the error handler to produce
the standard error envelope without leaking internals.
"""


class LedgerException(Exception):
    """Base class for all domain exceptions."""

    code: str = "LEDGER_ERROR"
    status_code: int = 400
    message: str = "A ledger error occurred."

    def __init__(self, message: str | None = None, details: list | None = None):
        self.message = message or self.__class__.message
        self.details = details or []
        super().__init__(self.message)


class AccountNotFound(LedgerException):
    code = "ACCOUNT_NOT_FOUND"
    status_code = 404
    message = "The requested account does not exist."


class InsufficientBalance(LedgerException):
    code = "INSUFFICIENT_BALANCE"
    status_code = 422
    message = "The account does not have sufficient balance for this operation."


class DuplicateTransaction(LedgerException):
    """Raised when a transaction with the same reference_id already exists
    for the given account.  Carries the existing transaction so it can be
    returned in the 409 body."""

    code = "DUPLICATE_TRANSACTION"
    status_code = 409
    message = "A transaction with this reference_id already exists for this account."

    def __init__(
        self,
        message: str | None = None,
        details: list | None = None,
        existing_transaction: dict | None = None,
    ):
        super().__init__(message, details)
        self.existing_transaction = existing_transaction


class SameAccountTransfer(LedgerException):
    code = "SAME_ACCOUNT_TRANSFER"
    status_code = 422
    message = "Source and destination accounts must be different."
