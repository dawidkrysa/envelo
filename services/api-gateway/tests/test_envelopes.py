SEEDED_CATEGORY_GROUP_ID = "00000000-0000-0000-0000-000000000301"
SEEDED_ACCOUNT_ID = "00000000-0000-0000-0000-000000000101"


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


async def test_deleting_an_envelope_drops_its_allocations(client):
    """An allocation describes an envelope that is about to stop existing, so it
    goes with it. This used to be a 409, which made an envelope permanent the
    moment any month's money had been assigned to it."""
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
    assert delete_response.status_code == 200

    remaining = await client.get("/budget/envelope-allocations", params={"envelopeId": envelope_id})
    assert remaining.status_code == 404  # the gateway's "no rows" answer


async def test_deleting_an_envelope_uncategorises_its_transactions(client):
    """The transactions really happened - they lose their envelope, not their
    existence. Refusing the delete until every one of them was reassigned meant
    a single import made a mistyped envelope permanent."""
    envelope_response = await client.post(
        "/budget/envelopes",
        json={"category_group_id": SEEDED_CATEGORY_GROUP_ID, "name": "Envelope with history"},
    )
    envelope_id = envelope_response.json()["id"]

    transaction_response = await client.post(
        "/budget/transactions",
        json={
            "account_id": SEEDED_ACCOUNT_ID,
            "envelope_id": envelope_id,
            "amount": "-25.00",
            "currency": "PLN",
            "transaction_date": "2026-02-11",
        },
    )
    assert transaction_response.status_code == 201
    transaction_id = transaction_response.json()["id"]

    delete_response = await client.delete(f"/budget/envelopes/{envelope_id}")
    assert delete_response.status_code == 200

    # Narrowed by date: the seeded database holds well over a page of
    # transactions, so an unfiltered first page need not contain this one.
    listed = await client.get(
        "/budget/transactions", params={"dateFrom": "2026-02-11", "dateTo": "2026-02-11", "limit": 100}
    )
    kept = [t for t in listed.json() if t["id"] == transaction_id]
    assert kept, "the transaction was deleted along with its envelope"
    assert kept[0]["envelope_id"] is None
    assert kept[0]["amount"] == "-25.00"


async def test_deleting_an_envelope_keeps_the_budget_balanced(client):
    """`to_assign` must absorb exactly what the envelope stops holding: its
    allocations return to the pool, and its spending stops being corrected for."""
    from decimal import Decimal

    envelope_response = await client.post(
        "/budget/envelopes",
        json={"category_group_id": SEEDED_CATEGORY_GROUP_ID, "name": "Balanced delete"},
    )
    envelope_id = envelope_response.json()["id"]
    await client.post(
        "/budget/envelope-allocations",
        json={"envelope_id": envelope_id, "month": "2026-02-01", "assigned_amount": "80.00"},
    )
    await client.post(
        "/budget/transactions",
        json={
            "account_id": SEEDED_ACCOUNT_ID,
            "envelope_id": envelope_id,
            "amount": "-30.00",
            "currency": "PLN",
            "transaction_date": "2026-02-11",
        },
    )

    before = Decimal((await client.get("/budget/envelope-allocations/to-assign")).json()["to_assign"])

    assert (await client.delete(f"/budget/envelopes/{envelope_id}")).status_code == 200

    after = Decimal((await client.get("/budget/envelope-allocations/to-assign")).json()["to_assign"])
    # The envelope held 80 assigned less 30 spent; that 50 is now unassigned.
    assert after - before == Decimal("50.00")


async def test_deleting_an_envelope_drops_its_categorization_rules(client):
    envelope_response = await client.post(
        "/budget/envelopes",
        json={"category_group_id": SEEDED_CATEGORY_GROUP_ID, "name": "Ruled envelope"},
    )
    envelope_id = envelope_response.json()["id"]

    rule_response = await client.post(
        "/budget/categorization-rules",
        json={"envelope_id": envelope_id, "phrase": "some unlikely phrase"},
    )
    assert rule_response.status_code == 201
    rule_id = rule_response.json()["id"]

    assert (await client.delete(f"/budget/envelopes/{envelope_id}")).status_code == 200

    listed = await client.get("/budget/categorization-rules", params={"limit": 100})
    remaining = listed.json() if listed.status_code == 200 else []
    assert not any(r["id"] == rule_id for r in remaining)
