# Transaction Ledger API

A robust, production-grade backend REST API for a double-entry style financial transaction ledger built with **FastAPI**, **SQLAlchemy 2.0**, and **Pydantic v2**. Supports account lifecycle management, atomic credit and debit operations, transaction history with filtering/pagination, and atomic peer-to-peer money transfers with idempotency guarantees.

---

## Table of Contents

- [Features](#features)
- [Architecture & Tech Stack](#architecture--tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Environment Configuration](#environment-configuration)
  - [Running the Application](#running-the-application)
- [Running Tests](#running-tests)
- [API Documentation](#api-documentation)
  - [Interactive Documentation (Swagger / ReDoc)](#interactive-documentation-swagger--redoc)
  - [Unified Error Envelope](#unified-error-envelope)
  - [Endpoints Overview](#endpoints-overview)
- [Data Integrity & Concurrency Architecture](#data-integrity--concurrency-architecture)
  - [Atomicity & Balance Guarantees](#atomicity--balance-guarantees)
  - [Database-Level Immutability](#database-level-immutability)
  - [Idempotency & Race Condition Prevention](#idempotency--race-condition-prevention)
  - [Deadlock-Free Transfers](#deadlock-free-transfers)
- [Assumptions & Design Decisions](#assumptions--design-decisions)

---

## Features

- **Account Management**: Create accounts with guaranteed zero initial balance; prevent balance tampering via client payloads (`extra="forbid"`).
- **Atomic Transactions**: Credit and debit operations execute atomically with account balance updates. Balance can never drop below zero.
- **Idempotent Transactions**: Unique `reference_id` per account. Duplicate attempts return `409 Conflict` without modifying balances.
- **Transaction History**: Paginated (configurable `page` and `limit`), sorted in latest-first order with stable tie-breaking, and filterable by transaction type (`credit` / `debit`).
- **Bonus Feature — Money Transfer**: Atomic transfer from account A to account B. Linked debit and credit transactions with deadlock avoidance and transfer idempotency.
- **Strict Data Integrity**: SQLite triggers enforcing table-level immutability (`NO UPDATE`, `NO DELETE`), database check constraints (`balance >= 0`, `amount > 0`), and unique constraints.
- **Comprehensive Test Suite**: 46 automated tests across accounts, transactions, transfers, concurrency, and immutability using `pytest` and `TestClient` with isolated in-memory databases.

---

## Architecture & Tech Stack

- **Language / Runtime**: Python 3.11+
- **Framework**: FastAPI (high-performance ASGI web framework)
- **Data Validation & Serialization**: Pydantic v2
- **ORM & Database Layer**: SQLAlchemy 2.0
- **Database**: SQLite (default, WAL mode enabled with foreign keys enforced) / PostgreSQL compatible via `DATABASE_URL`
- **Server**: Uvicorn ASGI server
- **Testing**: Pytest, FastAPI TestClient (`httpx`)

---

## Project Structure

A feature-based (vertical slice) architecture is used to group related models, routes, schemas, and domain logic:

```text
full-stack-assignment/
├── app/
│   ├── main.py                     # FastAPI application factory, lifespan, router registration
│   ├── core/
│   │   ├── config.py               # Application settings (Pydantic Settings)
│   │   ├── error_handlers.py       # Global exception handlers for standard JSON error envelope
│   │   └── exceptions.py          # Custom domain exceptions (LedgerException hierarchy)
│   ├── db/
│   │   ├── base.py                 # Declarative Base metadata
│   │   └── session.py              # Engine, sessionmaker, and get_db dependency
│   └── features/
│       ├── accounts/               # Account vertical slice
│       │   ├── model.py            # Account SQLAlchemy model
│       │   ├── routes.py           # HTTP endpoints for accounts
│       │   ├── schemas.py          # Account Pydantic schemas
│       │   └── service.py          # Account business logic
│       ├── transactions/           # Transaction vertical slice
│       │   ├── model.py            # Transaction SQLAlchemy model & SQLite triggers
│       │   ├── routes.py           # HTTP endpoints for transactions
│       │   ├── schemas.py          # Transaction Pydantic schemas
│       │   └── service.py          # Transaction business logic & locking
│       └── transfers/              # Transfer vertical slice (Bonus)
│           ├── routes.py           # HTTP endpoints for transfers
│           ├── schemas.py          # Transfer Pydantic schemas
│           └── service.py          # Deadlock-free atomic transfer service
├── tests/
│   ├── conftest.py                 # Pytest fixtures (in-memory SQLite static pool, client overrides)
│   ├── test_accounts.py            # Account unit & integration tests
│   ├── test_transactions.py        # Transaction, concurrency, immutability tests
│   └── test_transfers.py           # Peer-to-peer transfer & rollback tests
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment variable template
└── README.md                       # Project documentation
```

---

## Getting Started

### Prerequisites

- Python 3.11 or higher
- Git (optional)

### Installation

1. Clone or navigate into the repository:
   ```bash
   cd full-stack-assignment
   ```

2. Create and activate a virtual environment:
   ```bash
   # Windows (PowerShell)
   python -m venv venv
   .\venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Environment Configuration

Copy `.env.example` to `.env` (or configure your shell environment):
```bash
cp .env.example .env
```

Default settings:
```ini
DATABASE_URL=sqlite:///./ledger.db
```
To switch to PostgreSQL, configure a valid PostgreSQL connection string:
```ini
DATABASE_URL=postgresql://user:password@localhost:5432/ledger
```

### Running the Application

Run the server with Uvicorn:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
On startup:
- Tables are created automatically if they do not already exist.
- Immutability database triggers are verified and registered.

---

## Running Tests

The test suite executes against an in-memory SQLite database using `StaticPool` to ensure complete isolation and zero side effects on your local database file:

```bash
pytest -v
```

All 46 test cases should pass:
```text
tests/test_accounts.py ......................... [ 19%]
tests/test_transactions.py ..................... [ 82%]
tests/test_transfers.py ........................ [100%]
====================== 46 passed in 3.22s ======================
```

---

## API Documentation

### Interactive Documentation (Swagger / ReDoc)

Once the application is running, explore the interactive OpenAPI documentation:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Unified Error Envelope

All API errors return a standard, machine-readable envelope:
```json
{
  "error": {
    "code": "INSUFFICIENT_BALANCE",
    "message": "Cannot debit 150.00; current balance is 100.00.",
    "details": []
  }
}
```

For duplicate transaction conflicts (`409 Conflict`), the error payload includes details of the existing transaction:
```json
{
  "error": {
    "code": "DUPLICATE_TRANSACTION",
    "message": "A transaction with this reference_id already exists for this account.",
    "details": [],
    "existing_transaction": {
      "id": "b3e0c07c-e587-4340-a170-b7ca061213f5",
      "account_id": "902d3381-817c-48c9-a9a7-932f913617be",
      "type": "credit",
      "amount": "100.00",
      "description": "Initial deposit",
      "reference_id": "TXN-001",
      "created_at": "2026-10-26T13:30:00Z"
    }
  }
}
```

### Endpoints Overview

#### 1. Accounts
- **`POST /accounts`**
  - **Summary**: Create a new account.
  - **Request Body**:
    ```json
    {
      "name": "Jane Doe"
    }
    ```
  - **Response (201 Created)**:
    ```json
    {
      "id": "902d3381-817c-48c9-a9a7-932f913617be",
      "name": "Jane Doe",
      "balance": "0.00",
      "created_at": "2026-10-26T13:30:00.000000Z"
    }
    ```
- **`GET /accounts/{account_id}/balance`**
  - **Summary**: Retrieve account balance.
  - **Response (200 OK)**:
    ```json
    {
      "account_id": "902d3381-817c-48c9-a9a7-932f913617be",
      "balance": "250.00"
    }
    ```

#### 2. Transactions
- **`POST /accounts/{account_id}/transactions`**
  - **Summary**: Record a credit or debit transaction.
  - **Request Body**:
    ```json
    {
      "type": "credit",
      "amount": "100.00",
      "reference_id": "TXN-1001",
      "description": "Consulting invoice"
    }
    ```
  - **Response (201 Created)**:
    ```json
    {
      "id": "b3e0c07c-e587-4340-a170-b7ca061213f5",
      "account_id": "902d3381-817c-48c9-a9a7-932f913617be",
      "type": "credit",
      "amount": "100.00",
      "description": "Consulting invoice",
      "reference_id": "TXN-1001",
      "created_at": "2026-10-26T13:30:00.000000Z"
    }
    ```
- **`GET /accounts/{account_id}/transactions`**
  - **Summary**: Get paginated transactions in latest-first order.
  - **Query Parameters**:
    - `type` (optional): `credit` or `debit`
    - `page` (optional, default `1`, min `1`)
    - `limit` (optional, default `10`, min `1`, max `100`)
  - **Response (200 OK)**:
    ```json
    {
      "data": [
        {
          "id": "b3e0c07c-e587-4340-a170-b7ca061213f5",
          "account_id": "902d3381-817c-48c9-a9a7-932f913617be",
          "type": "credit",
          "amount": "100.00",
          "description": "Consulting invoice",
          "reference_id": "TXN-1001",
          "created_at": "2026-10-26T13:30:00.000000Z"
        }
      ],
      "pagination": {
        "current_page": 1,
        "page_size": 10,
        "total_records": 1,
        "total_pages": 1
      }
    }
    ```

#### 3. Transfers (Bonus Feature)
- **`POST /transfers`**
  - **Summary**: Atomically transfer money between two accounts.
  - **Request Body**:
    ```json
    {
      "from_account_id": "902d3381-817c-48c9-a9a7-932f913617be",
      "to_account_id": "f5195972-3543-41bb-9273-db6e5f67b557",
      "amount": "40.00",
      "reference_id": "XFER-2026-001",
      "description": "Shared expense split"
    }
    ```
  - **Response (201 Created)**:
    ```json
    {
      "transfer_reference_id": "XFER-2026-001",
      "from_account_id": "902d3381-817c-48c9-a9a7-932f913617be",
      "to_account_id": "f5195972-3543-41bb-9273-db6e5f67b557",
      "amount": "40.00",
      "debit_transaction_id": "31b18d2b-cf22-4914-b49b-75176ec739e8",
      "credit_transaction_id": "893d5671-55fc-428a-86c2-07ceb1086438",
      "description": "Shared expense split",
      "created_at": "2026-10-26T13:31:00.000000Z"
    }
    ```

---

## Data Integrity & Concurrency Architecture

### Atomicity & Balance Guarantees
- The account balance and transaction records are modified within the **exact same database transaction**.
- In addition to service-level checks, a database check constraint (`CONSTRAINT ck_accounts_balance_non_negative CHECK (balance >= 0)`) ensures that even if concurrent requests bypass application logic, the database engine enforces non-negative balances.
- Precise financial arithmetic is preserved using Python's `Decimal` type and SQLAlchemy's `Numeric(18, 2)` column definitions, preventing floating-point rounding errors.

### Database-Level Immutability
- Financial ledgers require strict immutability. Transactions cannot be updated or deleted.
- **HTTP Layer**: The API explicitly does not register `PUT`, `PATCH`, or `DELETE` endpoints for `/accounts/{id}/transactions`, returning `405 Method Not Allowed`.
- **Database Engine Layer**: SQLite triggers `trg_transactions_no_update` and `trg_transactions_no_delete` intercept any direct SQL `UPDATE` or `DELETE` statements on the `transactions` table and raise an abort error.

### Idempotency & Race Condition Prevention
- A database-level unique constraint `UNIQUE(account_id, reference_id)` prevents duplicate transactions for the same account.
- If two identical requests race simultaneously:
  1. One request succeeds and commits.
  2. The concurrent request encounters the unique constraint violation during `db.flush()`.
  3. The service intercepts the `IntegrityError`, rolls back the transaction, retrieves the committed record, and returns a clear `409 Conflict` with the existing transaction data.

### Deadlock-Free Transfers
- When transferring funds between two accounts, row-level locks must be acquired on both account records.
- If Account A transfers to Account B while Account B transfers to Account A simultaneously, arbitrary lock acquisition causes a deadlock.
- The transfer service avoids deadlocks by sorting the account IDs deterministically (`sorted([from_id, to_id])`) before acquiring locks (`SELECT ... FOR UPDATE` in PostgreSQL; SQLite WAL serialized lock ordering).

---

## Assumptions & Design Decisions

1. **Table Creation on Startup**:
   - For simplicity and ease of running without running manual migrations, tables are created at startup via `Base.metadata.create_all(bind=engine)`. In enterprise production environments, an Alembic migration pipeline would be used.
2. **Currency & Precision**:
   - Amounts use 2 decimal places (`Numeric(18, 2)`). Inputs with more than 2 decimal places or negative/zero amounts are rejected with `422 Unprocessable Entity`.
3. **Primary Keys & Sorting**:
   - `id` fields are UUIDv4 strings for client interaction.
   - An auto-incrementing integer sequence column (`seq`) acts as a stable sort tie-breaker alongside `created_at DESC` to ensure deterministic sorting order even under high-frequency writes within the same millisecond.
4. **Transfer Reference Decomposition**:
   - Transfers generate a linked debit transaction (`{reference_id}-debit`) on the source account and a credit transaction (`{reference_id}-credit`) on the destination account. Idempotency is enforced by verifying both reference IDs.
