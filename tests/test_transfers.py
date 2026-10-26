"""
Tests for the Transfers feature.
"""

from decimal import Decimal
from tests.conftest import create_test_account, credit


class TestTransferSuccess:
    def test_basic_transfer(self, client):
        alice = create_test_account(client, "Alice")
        bob = create_test_account(client, "Bob")
        credit(client, alice["id"], "100.00", "SEED-A")

        resp = client.post(
            "/transfers",
            json={
                "from_account_id": alice["id"],
                "to_account_id": bob["id"],
                "amount": "30.00",
                "description": "Payment",
                "reference_id": "XFER-001",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["from_account_id"] == alice["id"]
        assert data["to_account_id"] == bob["id"]
        assert Decimal(str(data["amount"])) == Decimal("30")
        assert "debit_transaction_id" in data
        assert "credit_transaction_id" in data

        # Verify balances
        alice_bal = client.get(f"/accounts/{alice['id']}/balance").json()
        bob_bal = client.get(f"/accounts/{bob['id']}/balance").json()
        assert Decimal(str(alice_bal["balance"])) == Decimal("70")
        assert Decimal(str(bob_bal["balance"])) == Decimal("30")

    def test_transfer_creates_two_transactions(self, client):
        alice = create_test_account(client, "Alice")
        bob = create_test_account(client, "Bob")
        credit(client, alice["id"], "100.00", "SEED")

        client.post(
            "/transfers",
            json={
                "from_account_id": alice["id"],
                "to_account_id": bob["id"],
                "amount": "25.00",
                "description": "Split bill",
                "reference_id": "XFER-002",
            },
        )

        # Alice should have a debit
        alice_txns = client.get(f"/accounts/{alice['id']}/transactions").json()
        debit_txn = [t for t in alice_txns["data"] if t["type"] == "debit"]
        assert len(debit_txn) == 1
        assert debit_txn[0]["reference_id"] == "XFER-002-debit"

        # Bob should have a credit
        bob_txns = client.get(f"/accounts/{bob['id']}/transactions").json()
        credit_txn = [t for t in bob_txns["data"] if t["type"] == "credit"]
        assert len(credit_txn) == 1
        assert credit_txn[0]["reference_id"] == "XFER-002-credit"


class TestTransferFailure:
    def test_insufficient_balance(self, client):
        alice = create_test_account(client, "Alice")
        bob = create_test_account(client, "Bob")
        credit(client, alice["id"], "20.00", "SEED")

        resp = client.post(
            "/transfers",
            json={
                "from_account_id": alice["id"],
                "to_account_id": bob["id"],
                "amount": "50.00",
                "description": "Too much",
                "reference_id": "XFER-FAIL",
            },
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INSUFFICIENT_BALANCE"

        # Balances must be unchanged
        assert Decimal(str(client.get(f"/accounts/{alice['id']}/balance").json()["balance"])) == Decimal("20")
        assert Decimal(str(client.get(f"/accounts/{bob['id']}/balance").json()["balance"])) == Decimal("0")

    def test_same_account(self, client):
        alice = create_test_account(client, "Alice")
        credit(client, alice["id"], "100.00", "SEED")

        resp = client.post(
            "/transfers",
            json={
                "from_account_id": alice["id"],
                "to_account_id": alice["id"],
                "amount": "10.00",
                "reference_id": "SELF",
            },
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "SAME_ACCOUNT_TRANSFER"

    def test_source_not_found(self, client):
        bob = create_test_account(client, "Bob")
        resp = client.post(
            "/transfers",
            json={
                "from_account_id": "00000000-0000-0000-0000-000000000000",
                "to_account_id": bob["id"],
                "amount": "10.00",
                "reference_id": "MISS",
            },
        )
        assert resp.status_code == 404

    def test_dest_not_found(self, client):
        alice = create_test_account(client, "Alice")
        credit(client, alice["id"], "100.00", "SEED")
        resp = client.post(
            "/transfers",
            json={
                "from_account_id": alice["id"],
                "to_account_id": "00000000-0000-0000-0000-000000000000",
                "amount": "10.00",
                "reference_id": "MISS",
            },
        )
        assert resp.status_code == 404

    def test_rollback_on_failure_no_partial(self, client):
        """If the transfer fails, neither account's balance should change."""
        alice = create_test_account(client, "Alice")
        bob = create_test_account(client, "Bob")
        credit(client, alice["id"], "50.00", "SEED")

        # Attempt a transfer that exceeds balance
        client.post(
            "/transfers",
            json={
                "from_account_id": alice["id"],
                "to_account_id": bob["id"],
                "amount": "999.00",
                "reference_id": "ROLLBACK-TEST",
            },
        )

        # No partial state
        assert Decimal(str(client.get(f"/accounts/{alice['id']}/balance").json()["balance"])) == Decimal("50")
        assert Decimal(str(client.get(f"/accounts/{bob['id']}/balance").json()["balance"])) == Decimal("0")

        # No orphaned transactions
        alice_txns = client.get(
            f"/accounts/{alice['id']}/transactions", params={"limit": 100}
        ).json()
        bob_txns = client.get(
            f"/accounts/{bob['id']}/transactions", params={"limit": 100}
        ).json()
        # Alice should only have the SEED credit, not a debit for the failed transfer
        assert alice_txns["pagination"]["total_records"] == 1
        assert bob_txns["pagination"]["total_records"] == 0


class TestTransferIdempotency:
    def test_duplicate_transfer_returns_409(self, client):
        alice = create_test_account(client, "Alice")
        bob = create_test_account(client, "Bob")
        credit(client, alice["id"], "100.00", "SEED")

        payload = {
            "from_account_id": alice["id"],
            "to_account_id": bob["id"],
            "amount": "25.00",
            "reference_id": "XFER-DUP",
        }
        r1 = client.post("/transfers", json=payload)
        assert r1.status_code == 201

        r2 = client.post("/transfers", json=payload)
        assert r2.status_code == 409
        assert r2.json()["error"]["code"] == "DUPLICATE_TRANSACTION"

        # Balance should reflect only ONE transfer
        assert Decimal(str(client.get(f"/accounts/{alice['id']}/balance").json()["balance"])) == Decimal("75")
        assert Decimal(str(client.get(f"/accounts/{bob['id']}/balance").json()["balance"])) == Decimal("25")
