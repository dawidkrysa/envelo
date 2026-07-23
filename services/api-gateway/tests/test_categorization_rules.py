SEEDED_ENVELOPE_ID = "00000000-0000-0000-0000-000000000401"


async def test_create_list_update_delete_categorization_rule(client):
    create_response = await client.post(
        "/budget/categorization-rules",
        json={"envelope_id": SEEDED_ENVELOPE_ID, "phrase": "STARBUCKS"},
    )
    assert create_response.status_code == 201
    rule = create_response.json()
    assert rule["envelope_id"] == SEEDED_ENVELOPE_ID
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
