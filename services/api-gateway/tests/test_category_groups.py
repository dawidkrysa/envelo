async def test_create_list_update_delete_category_group(client):
    create_response = await client.post(
        "/budget/category-groups", json={"name": "Fun money", "sort_order": 5}
    )
    assert create_response.status_code == 201
    group = create_response.json()
    assert group["name"] == "Fun money"
    group_id = group["id"]

    list_response = await client.get("/budget/category-groups")
    assert list_response.status_code == 200
    assert any(g["id"] == group_id for g in list_response.json())

    update_response = await client.put(
        f"/budget/category-groups/{group_id}", json={"sort_order": 9}
    )
    assert update_response.status_code == 200
    assert update_response.json()["sort_order"] == 9

    delete_response = await client.delete(f"/budget/category-groups/{group_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["id"] == group_id


async def test_delete_category_group_with_envelopes_is_blocked(client):
    group_response = await client.post(
        "/budget/category-groups", json={"name": "Group with envelopes", "sort_order": 1}
    )
    group_id = group_response.json()["id"]

    envelope_response = await client.post(
        "/budget/envelopes",
        json={"category_group_id": group_id, "name": "Test envelope"},
    )
    assert envelope_response.status_code == 201

    delete_response = await client.delete(f"/budget/category-groups/{group_id}")
    assert delete_response.status_code == 409
