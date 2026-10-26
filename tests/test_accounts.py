"""
Tests for the Accounts feature.
"""

import pytest
from decimal import Decimal
from tests.conftest import create_test_account


class TestCreateAccount:
    def test_create_account_success(self, client):
        resp = client.post("/accounts", json={"name": "Alice"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Alice"
        assert Decimal(str(data["balance"])) == Decimal("0")
        assert "id" in data
        assert "created_at" in data

    def test_create_account_trims_name(self, client):
        resp = client.post("/accounts", json={"name": "  Bob  "})
        assert resp.status_code == 201
        assert resp.json()["name"] == "Bob"

    def test_create_account_missing_name(self, client):
        resp = client.post("/accounts", json={})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_create_account_empty_name(self, client):
        resp = client.post("/accounts", json={"name": ""})
        assert resp.status_code == 422

    def test_create_account_rejects_balance_field(self, client):
        """Client should NOT be allowed to set the initial balance."""
        resp = client.post("/accounts", json={"name": "Eve", "balance": 1000})
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        # The detail should mention the extra field
        fields = [d["field"] for d in body["error"]["details"]]
        assert any("balance" in f for f in fields)

    def test_create_account_rejects_extra_fields(self, client):
        resp = client.post(
            "/accounts", json={"name": "Mallory", "is_admin": True}
        )
        assert resp.status_code == 422


class TestGetBalance:
    def test_get_balance_success(self, client):
        acc = create_test_account(client, "Alice")
        resp = client.get(f"/accounts/{acc['id']}/balance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["account_id"] == acc["id"]
        assert Decimal(str(data["balance"])) == Decimal("0")

    def test_get_balance_nonexistent_account(self, client):
        resp = client.get("/accounts/00000000-0000-0000-0000-000000000000/balance")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"

    def test_get_balance_malformed_uuid(self, client):
        """Malformed UUID in the path should return 422 (FastAPI path validation)."""
        resp = client.get("/accounts/not-a-uuid/balance")
        assert resp.status_code == 422
