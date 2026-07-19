import uuid

import pytest


async def test_create_list_update_delete_account(client):
    create_response = await client.post(
        "/budget/accounts",
        json={"name": "Test checking", "type": "checking", "currency": "PLN"},
    )
    assert create_response.status_code == 201
    account = create_response.json()
    assert account["name"] == "Test checking"
    account_id = account["id"]

    list_response = await client.get("/budget/accounts")
    assert list_response.status_code == 200
    assert any(a["id"] == account_id for a in list_response.json())

    update_response = await client.put(
        f"/budget/accounts/{account_id}", json={"name": "Renamed checking"}
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Renamed checking"

    delete_response = await client.delete(f"/budget/accounts/{account_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["id"] == account_id

    get_after_delete = await client.get("/budget/accounts")
    remaining_ids = [a["id"] for a in get_after_delete.json()]
    assert account_id not in remaining_ids


async def test_delete_account_with_statements_is_blocked(client):
    create_response = await client.post(
        "/budget/accounts",
        json={"name": "Account with history", "type": "checking", "currency": "PLN"},
    )
    account_id = create_response.json()["id"]

    statement_response = await client.post(
        "/budget/statements",
        json={"account_id": account_id, "filename": "jan.csv", "format": "csv"},
    )
    assert statement_response.status_code == 201

    delete_response = await client.delete(f"/budget/accounts/{account_id}")
    assert delete_response.status_code == 409


async def test_update_nonexistent_account_returns_404(client):
    response = await client.put(
        f"/budget/accounts/{uuid.uuid4()}", json={"name": "Ghost"}
    )
    assert response.status_code == 404
