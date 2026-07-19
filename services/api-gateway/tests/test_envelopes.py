SEEDED_CATEGORY_GROUP_ID = "00000000-0000-0000-0000-000000000301"


async def test_create_list_update_delete_envelope(client):
    create_response = await client.post(
        "/budget/envelopes",
        json={
            "category_group_id": SEEDED_CATEGORY_GROUP_ID,
            "name": "Test envelope",
            "target_amount": "100.00",
        },
    )
    assert create_response.status_code == 201
    envelope = create_response.json()
    assert envelope["name"] == "Test envelope"
    envelope_id = envelope["id"]

    list_response = await client.get("/budget/envelopes")
    assert list_response.status_code == 200
    assert any(e["id"] == envelope_id for e in list_response.json())

    update_response = await client.put(
        f"/budget/envelopes/{envelope_id}", json={"name": "Renamed envelope"}
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Renamed envelope"

    delete_response = await client.delete(f"/budget/envelopes/{envelope_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["id"] == envelope_id


async def test_create_envelope_rejects_negative_target_amount(client):
    response = await client.post(
        "/budget/envelopes",
        json={
            "category_group_id": SEEDED_CATEGORY_GROUP_ID,
            "name": "Invalid envelope",
            "target_amount": "-1.00",
        },
    )
    assert response.status_code == 422


async def test_get_envelopes_filters_by_category_group(client):
    group_response = await client.post(
        "/budget/category-groups", json={"name": "Filter test group", "sort_order": 1}
    )
    group_id = group_response.json()["id"]

    envelope_response = await client.post(
        "/budget/envelopes",
        json={"category_group_id": group_id, "name": "Scoped envelope"},
    )
    envelope_id = envelope_response.json()["id"]

    response = await client.get(
        "/budget/envelopes", params={"categoryGroupId": group_id}
    )
    assert response.status_code == 200
    returned_ids = [e["id"] for e in response.json()]
    assert returned_ids == [envelope_id]


async def test_delete_envelope_with_allocation_is_blocked(client):
    envelope_response = await client.post(
        "/budget/envelopes",
        json={"category_group_id": SEEDED_CATEGORY_GROUP_ID, "name": "Allocated envelope"},
    )
    envelope_id = envelope_response.json()["id"]

    allocation_response = await client.post(
        "/budget/envelope-allocations",
        json={"envelope_id": envelope_id, "month": "2026-02-01", "assigned_amount": "50.00"},
    )
    assert allocation_response.status_code == 201

    delete_response = await client.delete(f"/budget/envelopes/{envelope_id}")
    assert delete_response.status_code == 409
