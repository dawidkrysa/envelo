SEEDED_CATEGORY_GROUP_ID = "00000000-0000-0000-0000-000000000301"


async def _create_envelope(client, name: str) -> str:
    """Created here rather than borrowing a seeded id: envelopes can be deleted
    now, so an id written down in a test file is no longer guaranteed to exist in
    the shared dev database."""
    response = await client.post(
        "/budget/envelopes",
        json={"category_group_id": SEEDED_CATEGORY_GROUP_ID, "name": name},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_create_list_update_delete_categorization_rule(client):
    envelope_id = await _create_envelope(client, "Rule target")

    create_response = await client.post(
        "/budget/categorization-rules",
        json={"envelope_id": envelope_id, "phrase": "STARBUCKS"},
    )
    assert create_response.status_code == 201
    rule = create_response.json()
    assert rule["envelope_id"] == envelope_id
    assert rule["phrase"] == "STARBUCKS"
    rule_id = rule["id"]

    list_response = await client.get("/budget/categorization-rules")
    assert list_response.status_code == 200
    assert any(r["id"] == rule_id for r in list_response.json())

    update_response = await client.put(
        f"/budget/categorization-rules/{rule_id}", json={"phrase": "STARBUCKS COFFEE"}
    )
    assert update_response.status_code == 200
    assert update_response.json()["phrase"] == "STARBUCKS COFFEE"

    delete_response = await client.delete(f"/budget/categorization-rules/{rule_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["id"] == rule_id


async def test_create_categorization_rule_unknown_envelope_is_rejected(client):
    response = await client.post(
        "/budget/categorization-rules",
        json={
            "envelope_id": "00000000-0000-0000-0000-000000009999",
            "phrase": "STARBUCKS",
        },
    )
    assert response.status_code == 409
