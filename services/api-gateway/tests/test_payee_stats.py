from decimal import Decimal

SEEDED_ACCOUNT_ID = "00000000-0000-0000-0000-000000000101"
SEEDED_CATEGORY_GROUP_ID = "00000000-0000-0000-0000-000000000301"


async def _create_payee(client, name: str) -> str:
    response = await client.post("/budget/payees", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


async def _create_envelope(client, name: str) -> str:
    response = await client.post(
        "/budget/envelopes",
        json={"category_group_id": SEEDED_CATEGORY_GROUP_ID, "name": name},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _spend(client, payee_id: str, amount: str, day: str, envelope_id: str | None = None) -> str:
    payload = {
        "account_id": SEEDED_ACCOUNT_ID,
        "payee_id": payee_id,
        "amount": amount,
        "currency": "PLN",
        "transaction_date": day,
    }
    if envelope_id is not None:
        payload["envelope_id"] = envelope_id
    response = await client.post("/budget/transactions", json=payload)
    assert response.status_code == 201
    return response.json()["id"]


async def _stats(client) -> dict[str, dict]:
    response = await client.get("/budget/payees/stats")
    assert response.status_code == 200
    return {row["payee_id"]: row for row in response.json()}


async def test_payee_stats_count_sum_and_date_the_transactions(client):
    payee_id = await _create_payee(client, "Stats subject")
    await _spend(client, payee_id, "-40.00", "2026-05-02")
    await _spend(client, payee_id, "-60.00", "2026-05-09")

    row = (await _stats(client))[payee_id]

    assert row["transaction_count"] == 2
    assert Decimal(row["total"]) == Decimal("-100.00")
    assert row["last_transaction_date"] == "2026-05-09"


async def test_a_payee_that_pays_you_reports_a_positive_total(client):
    """The total is signed, not an amount spent: an employer or a refund is not
    a negative amount of spending, it is money in."""
    payee_id = await _create_payee(client, "Employer")
    await _spend(client, payee_id, "5000.00", "2026-05-01")

    assert Decimal((await _stats(client))[payee_id]["total"]) == Decimal("5000.00")


async def test_top_envelope_is_where_the_payee_usually_goes(client):
    """The same signal `match_envelope_for_transaction` falls back on, so the
    screen shows where an unrecognised transaction from this payee would land."""
    payee_id = await _create_payee(client, "Mostly groceries")
    usual = await _create_envelope(client, "Usual envelope")
    other = await _create_envelope(client, "Occasional envelope")
    await _spend(client, payee_id, "-10.00", "2026-05-01", usual)
    await _spend(client, payee_id, "-10.00", "2026-05-02", usual)
    await _spend(client, payee_id, "-10.00", "2026-05-03", other)

    assert (await _stats(client))[payee_id]["top_envelope_id"] == usual


async def test_a_payee_with_only_uncategorized_transactions_has_no_top_envelope(client):
    payee_id = await _create_payee(client, "Never filed")
    await _spend(client, payee_id, "-10.00", "2026-05-01")

    assert (await _stats(client))[payee_id]["top_envelope_id"] is None


async def test_a_payee_nothing_has_been_spent_on_is_still_listed(client):
    """Dropping it would make this screen disagree with `GET /budget/payees`."""
    payee_id = await _create_payee(client, "Created by hand")

    row = (await _stats(client))[payee_id]

    assert row["transaction_count"] == 0
    assert Decimal(row["total"]) == Decimal("0")
    assert row["last_transaction_date"] is None


async def test_one_payees_transactions_do_not_land_on_another(client):
    first = await _create_payee(client, "First payee")
    second = await _create_payee(client, "Second payee")
    await _spend(client, first, "-25.00", "2026-05-01")

    stats = await _stats(client)

    assert stats[first]["transaction_count"] == 1
    assert stats[second]["transaction_count"] == 0


async def test_payee_stats_are_not_capped_by_the_transaction_page_size(client):
    payee_id = await _create_payee(client, "Very busy payee")
    for day in range(1, 8):
        for _ in range(20):
            await _spend(client, payee_id, "-1.00", f"2026-06-{day:02d}")

    row = (await _stats(client))[payee_id]

    assert row["transaction_count"] == 140
    assert Decimal(row["total"]) == Decimal("-140.00")


async def test_merging_moves_the_transactions_and_removes_the_duplicate(client):
    """An import creates a payee per spelling, so the same shop arrives as
    several and its history is split between them."""
    duplicate = await _create_payee(client, "BIEDRONKA 1234")
    survivor = await _create_payee(client, "Biedronka")
    moved = await _spend(client, duplicate, "-30.00", "2026-05-01")
    await _spend(client, survivor, "-20.00", "2026-05-02")

    response = await client.post(
        "/budget/payees/merge",
        json={"from_payee_id": duplicate, "into_payee_id": survivor},
    )
    assert response.status_code == 200
    assert response.json()["id"] == survivor

    stats = await _stats(client)
    assert duplicate not in stats
    assert stats[survivor]["transaction_count"] == 2
    assert Decimal(stats[survivor]["total"]) == Decimal("-50.00")

    transaction = (await client.get("/budget/transactions", params={"dateFrom": "2026-05-01", "dateTo": "2026-05-01"})).json()
    assert [t["payee_id"] for t in transaction if t["id"] == moved] == [survivor]


async def test_merging_a_payee_into_itself_is_rejected(client):
    """It would delete the payee and repoint its transactions at a row that no
    longer exists."""
    payee_id = await _create_payee(client, "Self merge")

    response = await client.post(
        "/budget/payees/merge",
        json={"from_payee_id": payee_id, "into_payee_id": payee_id},
    )
    assert response.status_code == 400


async def test_merging_an_unknown_payee_is_a_404(client):
    payee_id = await _create_payee(client, "Real payee")

    response = await client.post(
        "/budget/payees/merge",
        json={
            "from_payee_id": "00000000-0000-0000-0000-000000009999",
            "into_payee_id": payee_id,
        },
    )
    assert response.status_code == 404


async def test_renaming_a_payee_keeps_its_transactions(client):
    """Rename is a `PUT`, not a delete-and-recreate, so the history behind
    categorization survives it."""
    payee_id = await _create_payee(client, "Old spelling")
    await _spend(client, payee_id, "-15.00", "2026-05-01")

    response = await client.put(f"/budget/payees/{payee_id}", json={"name": "New spelling"})
    assert response.status_code == 200
    assert response.json()["name"] == "New spelling"

    assert (await _stats(client))[payee_id]["transaction_count"] == 1
