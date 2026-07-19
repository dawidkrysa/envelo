SEEDED_ACCOUNT_ID = "00000000-0000-0000-0000-000000000101"
SEEDED_ENVELOPE_ID = "00000000-0000-0000-0000-000000000401"


async def test_create_transaction_rejects_zero_amount(client):
    response = await client.post(
        "/budget/transactions",
        json={
            "account_id": SEEDED_ACCOUNT_ID,
            "amount": "0",
            "currency": "PLN",
            "transaction_date": "2026-01-01",
        },
    )
    assert response.status_code == 422


async def test_create_transaction_success(client):
    response = await client.post(
        "/budget/transactions",
        json={
            "account_id": SEEDED_ACCOUNT_ID,
            "amount": "-42.50",
            "currency": "PLN",
            "transaction_date": "2026-01-01",
            "description": "test purchase",
        },
    )
    assert response.status_code == 201
    transaction = response.json()
    assert transaction["amount"] == "-42.50"
    assert transaction["cleared"] is False
    assert transaction["categorization_source"] is None


async def test_update_transaction_sets_manual_categorization(client):
    create_response = await client.post(
        "/budget/transactions",
        json={
            "account_id": SEEDED_ACCOUNT_ID,
            "amount": "-10.00",
            "currency": "PLN",
            "transaction_date": "2026-01-02",
        },
    )
    transaction_id = create_response.json()["id"]
    assert create_response.json()["categorization_source"] is None

    update_response = await client.put(
        f"/budget/transactions/{transaction_id}",
        json={"envelope_id": SEEDED_ENVELOPE_ID},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["envelope_id"] == SEEDED_ENVELOPE_ID
    assert updated["categorization_source"] == "manual"


async def test_get_transactions_filters_by_date_range(client):
    in_range = await client.post(
        "/budget/transactions",
        json={
            "account_id": SEEDED_ACCOUNT_ID,
            "amount": "-5.00",
            "currency": "PLN",
            "transaction_date": "2099-06-15",
        },
    )
    assert in_range.status_code == 201
    in_range_id = in_range.json()["id"]

    out_of_range = await client.post(
        "/budget/transactions",
        json={
            "account_id": SEEDED_ACCOUNT_ID,
            "amount": "-7.00",
            "currency": "PLN",
            "transaction_date": "2099-08-01",
        },
    )
    assert out_of_range.status_code == 201
    out_of_range_id = out_of_range.json()["id"]

    response = await client.get(
        "/budget/transactions",
        params={"dateFrom": "2099-06-01", "dateTo": "2099-06-30"},
    )
    assert response.status_code == 200
    returned_ids = [t["id"] for t in response.json()]
    assert in_range_id in returned_ids
    assert out_of_range_id not in returned_ids
