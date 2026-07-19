SEEDED_CATEGORY_GROUP_ID = "00000000-0000-0000-0000-000000000301"


async def _create_envelope(client, name: str):
    response = await client.post(
        "/budget/envelopes",
        json={"category_group_id": SEEDED_CATEGORY_GROUP_ID, "name": name},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_create_get_update_envelope_allocation(client):
    envelope_id = await _create_envelope(client, "Allocation target")

    create_response = await client.post(
        "/budget/envelope-allocations",
        json={
            "envelope_id": envelope_id,
            "month": "2026-03-01",
            "assigned_amount": "200.00",
        },
    )
    assert create_response.status_code == 201
    allocation = create_response.json()
    assert allocation["assigned_amount"] == "200.00"
    allocation_id = allocation["id"]

    list_response = await client.get(
        "/budget/envelope-allocations", params={"envelopeId": envelope_id}
    )
    assert list_response.status_code == 200
    assert [a["id"] for a in list_response.json()] == [allocation_id]

    update_response = await client.put(
        f"/budget/envelope-allocations/{allocation_id}",
        json={"assigned_amount": "0"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["assigned_amount"] == "0"


async def test_create_envelope_allocation_rejects_negative_amount(client):
    envelope_id = await _create_envelope(client, "Negative amount target")

    response = await client.post(
        "/budget/envelope-allocations",
        json={
            "envelope_id": envelope_id,
            "month": "2026-03-01",
            "assigned_amount": "-1.00",
        },
    )
    assert response.status_code == 422


async def test_create_envelope_allocation_duplicate_month_is_blocked(client):
    envelope_id = await _create_envelope(client, "Duplicate month target")
    payload = {
        "envelope_id": envelope_id,
        "month": "2026-04-01",
        "assigned_amount": "50.00",
    }

    first = await client.post("/budget/envelope-allocations", json=payload)
    assert first.status_code == 201

    second = await client.post("/budget/envelope-allocations", json=payload)
    assert second.status_code == 409


async def test_transfer_between_envelope_allocations(client):
    source_envelope_id = await _create_envelope(client, "Transfer source")
    target_envelope_id = await _create_envelope(client, "Transfer target")

    await client.post(
        "/budget/envelope-allocations",
        json={
            "envelope_id": source_envelope_id,
            "month": "2026-05-01",
            "assigned_amount": "100.00",
        },
    )

    response = await client.post(
        "/budget/envelope-allocations/transfer",
        json={
            "from_envelope_id": source_envelope_id,
            "to_envelope_id": target_envelope_id,
            "month": "2026-05-01",
            "amount": "40.00",
        },
    )
    assert response.status_code == 200
    source, target = response.json()
    assert source["assigned_amount"] == "60.00"
    assert target["assigned_amount"] == "40.00"


async def test_transfer_rejects_insufficient_funds(client):
    source_envelope_id = await _create_envelope(client, "Underfunded source")
    target_envelope_id = await _create_envelope(client, "Underfunded target")

    await client.post(
        "/budget/envelope-allocations",
        json={
            "envelope_id": source_envelope_id,
            "month": "2026-06-01",
            "assigned_amount": "10.00",
        },
    )

    response = await client.post(
        "/budget/envelope-allocations/transfer",
        json={
            "from_envelope_id": source_envelope_id,
            "to_envelope_id": target_envelope_id,
            "month": "2026-06-01",
            "amount": "999.00",
        },
    )
    assert response.status_code == 409


async def test_transfer_to_same_envelope_is_rejected(client):
    envelope_id = await _create_envelope(client, "Self transfer target")

    response = await client.post(
        "/budget/envelope-allocations/transfer",
        json={
            "from_envelope_id": envelope_id,
            "to_envelope_id": envelope_id,
            "month": "2026-07-01",
            "amount": "10.00",
        },
    )
    assert response.status_code == 400
