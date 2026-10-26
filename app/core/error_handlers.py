"""
FastAPI exception handlers that map domain exceptions and framework errors
to the ONE consistent error envelope:

    {
        "error": {
            "code": "MACHINE_READABLE_CODE",
            "message": "Human-readable message.",
            "details": [...]
        }
    }
"""

import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import LedgerException, DuplicateTransaction

logger = logging.getLogger("ledger")


def _envelope(code: str, message: str, details: list | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or []}}


async def ledger_exception_handler(_request: Request, exc: LedgerException):
    from fastapi.responses import JSONResponse

    body = _envelope(exc.code, exc.message, exc.details)
    # For duplicate transactions, include the existing transaction in details
    if isinstance(exc, DuplicateTransaction) and exc.existing_transaction:
        body["error"]["existing_transaction"] = exc.existing_transaction
    return JSONResponse(status_code=exc.status_code, content=body)


async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    from fastapi.responses import JSONResponse

    details = []
    for err in exc.errors():
        details.append(
            {
                "field": " -> ".join(str(loc) for loc in err["loc"]),
                "message": err["msg"],
                "type": err["type"],
            }
        )
    return JSONResponse(
        status_code=422,
        content=_envelope("VALIDATION_ERROR", "Request validation failed.", details),
    )


async def http_exception_handler(_request: Request, exc: StarletteHTTPException):
    from fastapi.responses import JSONResponse

    code_map = {
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
    }
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope(
            code_map.get(exc.status_code, "HTTP_ERROR"),
            str(exc.detail),
        ),
    )


async def unhandled_exception_handler(_request: Request, exc: Exception):
    from fastapi.responses import JSONResponse

    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content=_envelope(
            "INTERNAL_SERVER_ERROR",
            "An unexpected error occurred. Please try again later.",
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all custom exception handlers to the FastAPI application."""
    app.add_exception_handler(LedgerException, ledger_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)  # type: ignore[arg-type]
