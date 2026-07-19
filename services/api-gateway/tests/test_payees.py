SEEDED_ACCOUNT_ID = "00000000-0000-0000-0000-000000000101"


async def test_create_list_update_delete_payee(client):
    create_response = await client.post("/budget/payees", json={"name": "Corner shop"})
    assert create_response.status_code == 201
    payee = create_response.json()
    assert payee["name"] == "Corner shop"
    payee_id = payee["id"]

    list_response = await client.get("/budget/payees")
    assert list_response.status_code == 200
    assert any(p["id"] == payee_id for p in list_response.json())

    update_response = await client.put(
        f"/budget/payees/{payee_id}", json={"name": "Renamed shop"}
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Renamed shop"

    delete_response = await client.delete(f"/budget/payees/{payee_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["id"] == payee_id


async def test_delete_payee_with_transactions_is_blocked(client):
    payee_response = await client.post(
        "/budget/payees", json={"name": "Payee with history"}
    )
    payee_id = payee_response.json()["id"]

    transaction_response = await client.post(
        "/budget/transactions",
        json={
            "account_id": SEEDED_ACCOUNT_ID,
            "payee_id": payee_id,
            "amount": "-15.00",
            "currency": "PLN",
            "transaction_date": "2026-01-05",
        },
    )
    assert transaction_response.status_code == 201

    delete_response = await client.delete(f"/budget/payees/{payee_id}")
    assert delete_response.status_code == 409
