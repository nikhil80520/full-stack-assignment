"""
Tests for the Transactions feature.
"""

import pytest
from decimal import Decimal
from tests.conftest import create_test_account, credit, debit


class TestAddTransaction:
    def test_credit_success(self, client):
        acc = create_test_account(client)
        resp = client.post(
            f"/accounts/{acc['id']}/transactions",
            json={
                "type": "credit",
                "amount": "100.00",
                "reference_id": "TXN-001",
                "description": "Initial deposit",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == "credit"
        assert Decimal(str(data["amount"])) == Decimal("100")
        assert data["reference_id"] == "TXN-001"

    def test_debit_success(self, client):
        acc = create_test_account(client)
        credit(client, acc["id"], "100.00", "C1")
        resp = client.post(
            f"/accounts/{acc['id']}/transactions",
            json={
                "type": "debit",
                "amount": "30.00",
                "reference_id": "D1",
                "description": "Withdrawal",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == "debit"

    def test_debit_insufficient_balance(self, client):
        acc = create_test_account(client)
        credit(client, acc["id"], "50.00", "C1")
        resp = client.post(
            f"/accounts/{acc['id']}/transactions",
            json={
                "type": "debit",
                "amount": "100.00",
                "reference_id": "D1",
            },
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INSUFFICIENT_BALANCE"
        # Balance must be unchanged
        bal = client.get(f"/accounts/{acc['id']}/balance").json()
        assert Decimal(str(bal["balance"])) == Decimal("50")

    def test_balance_consistency(self, client):
        """100 + 50 - 30 - 20 = 100."""
        acc = create_test_account(client)
        credit(client, acc["id"], "100.00", "C1")
        credit(client, acc["id"], "50.00", "C2")
        debit(client, acc["id"], "30.00", "D1")
        debit(client, acc["id"], "20.00", "D2")
        bal = client.get(f"/accounts/{acc['id']}/balance").json()
        assert Decimal(str(bal["balance"])) == Decimal("100")

    def test_balance_equals_sum_of_transactions(self, client):
        """Verify balance = sum(credits) - sum(debits) from the full history."""
        acc = create_test_account(client)
        credit(client, acc["id"], "200.00", "C1")
        credit(client, acc["id"], "50.50", "C2")
        debit(client, acc["id"], "30.25", "D1")
        debit(client, acc["id"], "20.00", "D2")

        # Fetch all transactions
        history = client.get(
            f"/accounts/{acc['id']}/transactions", params={"limit": 100}
        ).json()

        recomputed = Decimal("0")
        for txn in history["data"]:
            amt = Decimal(str(txn["amount"]))
            if txn["type"] == "credit":
                recomputed += amt
            else:
                recomputed -= amt

        bal = client.get(f"/accounts/{acc['id']}/balance").json()
        assert Decimal(str(bal["balance"])) == recomputed

    def test_duplicate_reference_id_same_account(self, client):
        acc = create_test_account(client)
        credit(client, acc["id"], "100.00", "DUP-1")
        resp = client.post(
            f"/accounts/{acc['id']}/transactions",
            json={"type": "credit", "amount": "50.00", "reference_id": "DUP-1"},
        )
        assert resp.status_code == 409
        body = resp.json()
        assert body["error"]["code"] == "DUPLICATE_TRANSACTION"
        assert "existing_transaction" in body["error"]
        # Balance must NOT change
        bal = client.get(f"/accounts/{acc['id']}/balance").json()
        assert Decimal(str(bal["balance"])) == Decimal("100")

    def test_same_reference_id_different_accounts(self, client):
        acc1 = create_test_account(client, "Alice")
        acc2 = create_test_account(client, "Bob")
        r1 = client.post(
            f"/accounts/{acc1['id']}/transactions",
            json={"type": "credit", "amount": "10.00", "reference_id": "SHARED"},
        )
        r2 = client.post(
            f"/accounts/{acc2['id']}/transactions",
            json={"type": "credit", "amount": "20.00", "reference_id": "SHARED"},
        )
        assert r1.status_code == 201
        assert r2.status_code == 201

    def test_account_not_found(self, client):
        resp = client.post(
            "/accounts/00000000-0000-0000-0000-000000000000/transactions",
            json={"type": "credit", "amount": "10.00", "reference_id": "X"},
        )
        assert resp.status_code == 404

    def test_invalid_type(self, client):
        acc = create_test_account(client)
        resp = client.post(
            f"/accounts/{acc['id']}/transactions",
            json={"type": "refund", "amount": "10.00", "reference_id": "X"},
        )
        assert resp.status_code == 422

    def test_zero_amount(self, client):
        acc = create_test_account(client)
        resp = client.post(
            f"/accounts/{acc['id']}/transactions",
            json={"type": "credit", "amount": "0", "reference_id": "X"},
        )
        assert resp.status_code == 422

    def test_negative_amount(self, client):
        acc = create_test_account(client)
        resp = client.post(
            f"/accounts/{acc['id']}/transactions",
            json={"type": "credit", "amount": "-10.00", "reference_id": "X"},
        )
        assert resp.status_code == 422

    def test_amount_too_many_decimals(self, client):
        acc = create_test_account(client)
        resp = client.post(
            f"/accounts/{acc['id']}/transactions",
            json={"type": "credit", "amount": "10.123", "reference_id": "X"},
        )
        assert resp.status_code == 422

    def test_empty_reference_id(self, client):
        acc = create_test_account(client)
        resp = client.post(
            f"/accounts/{acc['id']}/transactions",
            json={"type": "credit", "amount": "10.00", "reference_id": ""},
        )
        assert resp.status_code == 422

    def test_whitespace_only_reference_id(self, client):
        acc = create_test_account(client)
        resp = client.post(
            f"/accounts/{acc['id']}/transactions",
            json={"type": "credit", "amount": "10.00", "reference_id": "   "},
        )
        assert resp.status_code == 422


class TestTransactionImmutability:
    """Transactions must not be updatable or deletable via the API."""

    def test_put_not_allowed(self, client):
        acc = create_test_account(client)
        resp = client.put(
            f"/accounts/{acc['id']}/transactions",
            json={"type": "credit", "amount": "10.00", "reference_id": "X"},
        )
        assert resp.status_code == 405

    def test_patch_not_allowed(self, client):
        acc = create_test_account(client)
        resp = client.patch(
            f"/accounts/{acc['id']}/transactions",
            json={"amount": "999.00"},
        )
        assert resp.status_code == 405

    def test_delete_not_allowed(self, client):
        acc = create_test_account(client)
        resp = client.delete(f"/accounts/{acc['id']}/transactions")
        assert resp.status_code == 405

    def test_db_trigger_blocks_update(self, client, db):
        """The SQLite trigger should abort any UPDATE on transactions."""
        from sqlalchemy import text

        acc = create_test_account(client)
        credit(client, acc["id"], "100.00", "C1")

        # Attempt a raw SQL UPDATE — must raise
        with pytest.raises(Exception):
            db.execute(
                text(
                    "UPDATE transactions SET amount = 999 "
                    "WHERE account_id = :aid AND reference_id = 'C1'"
                ),
                {"aid": acc["id"]},
            )

    def test_db_trigger_blocks_delete(self, client, db):
        """The SQLite trigger should abort any DELETE on transactions."""
        from sqlalchemy import text

        acc = create_test_account(client)
        credit(client, acc["id"], "100.00", "C1")

        with pytest.raises(Exception):
            db.execute(
                text(
                    "DELETE FROM transactions "
                    "WHERE account_id = :aid AND reference_id = 'C1'"
                ),
                {"aid": acc["id"]},
            )


class TestGetTransactions:
    def _seed(self, client):
        acc = create_test_account(client)
        for i in range(1, 16):
            t = "credit" if i % 2 == 1 else "debit"
            # Ensure sufficient balance for debits
            if t == "credit":
                credit(client, acc["id"], "100.00", f"TXN-{i}")
            else:
                debit(client, acc["id"], "10.00", f"TXN-{i}")
        return acc

    def test_default_pagination(self, client):
        acc = self._seed(client)
        resp = client.get(f"/accounts/{acc['id']}/transactions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 10
        assert data["pagination"]["current_page"] == 1
        assert data["pagination"]["page_size"] == 10
        assert data["pagination"]["total_records"] == 15
        assert data["pagination"]["total_pages"] == 2

    def test_custom_page_and_limit(self, client):
        acc = self._seed(client)
        resp = client.get(
            f"/accounts/{acc['id']}/transactions",
            params={"page": 2, "limit": 5},
        )
        data = resp.json()
        assert len(data["data"]) == 5
        assert data["pagination"]["current_page"] == 2

    def test_filter_by_type_credit(self, client):
        acc = self._seed(client)
        resp = client.get(
            f"/accounts/{acc['id']}/transactions",
            params={"type": "credit", "limit": 100},
        )
        data = resp.json()
        assert all(t["type"] == "credit" for t in data["data"])
        assert data["pagination"]["total_records"] == 8  # 8 credits

    def test_filter_by_type_debit(self, client):
        acc = self._seed(client)
        resp = client.get(
            f"/accounts/{acc['id']}/transactions",
            params={"type": "debit", "limit": 100},
        )
        data = resp.json()
        assert all(t["type"] == "debit" for t in data["data"])
        assert data["pagination"]["total_records"] == 7  # 7 debits

    def test_latest_first_ordering(self, client):
        acc = create_test_account(client)
        credit(client, acc["id"], "10.00", "FIRST")
        credit(client, acc["id"], "20.00", "SECOND")
        credit(client, acc["id"], "30.00", "THIRD")
        resp = client.get(f"/accounts/{acc['id']}/transactions")
        data = resp.json()["data"]
        assert data[0]["reference_id"] == "THIRD"
        assert data[2]["reference_id"] == "FIRST"

    def test_invalid_page_zero(self, client):
        acc = create_test_account(client)
        resp = client.get(
            f"/accounts/{acc['id']}/transactions", params={"page": 0}
        )
        assert resp.status_code == 422

    def test_invalid_limit_too_large(self, client):
        acc = create_test_account(client)
        resp = client.get(
            f"/accounts/{acc['id']}/transactions", params={"limit": 200}
        )
        assert resp.status_code == 422

    def test_invalid_type_filter(self, client):
        acc = create_test_account(client)
        resp = client.get(
            f"/accounts/{acc['id']}/transactions", params={"type": "refund"}
        )
        assert resp.status_code == 422

    def test_account_not_found(self, client):
        resp = client.get(
            "/accounts/00000000-0000-0000-0000-000000000000/transactions"
        )
        assert resp.status_code == 404


class TestConcurrency:
    def test_parallel_debits_never_go_negative(self, client, db):
        """Several near-simultaneous debits must never take balance below 0.

        Because we're using SQLite in tests (single writer), we simulate
        this by rapidly issuing debits that would overdraw if all succeeded.
        """
        acc = create_test_account(client)
        credit(client, acc["id"], "100.00", "SEED")

        # Fire 20 debits of 10 each — only 10 should succeed
        success_count = 0
        for i in range(20):
            resp = client.post(
                f"/accounts/{acc['id']}/transactions",
                json={
                    "type": "debit",
                    "amount": "10.00",
                    "reference_id": f"RACE-{i}",
                },
            )
            if resp.status_code == 201:
                success_count += 1

        bal = client.get(f"/accounts/{acc['id']}/balance").json()
        assert Decimal(str(bal["balance"])) >= Decimal("0")
        assert success_count == 10
