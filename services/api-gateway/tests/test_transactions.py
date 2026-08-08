import pytest_asyncio

SEEDED_ACCOUNT_ID = "00000000-0000-0000-0000-000000000101"
SEEDED_CATEGORY_GROUP_ID = "00000000-0000-0000-0000-000000000301"


@pytest_asyncio.fixture
async def envelope_id(client) -> str:
    """An envelope this test created, not a seeded id written down here.

    These tests used to point at the seeded "Groceries" row. That was only ever
    safe because the API refused to delete an envelope that had allocations or
    transactions; deleting one is allowed now, so any row in the shared dev
    database can legitimately disappear - and when Groceries did, eleven tests
    that had nothing to do with deleting envelopes started failing on a 409.

    Rolled back with the rest of the test, like everything else the suite writes.
    """
    response = await client.post(
        "/budget/envelopes",
        json={"category_group_id": SEEDED_CATEGORY_GROUP_ID, "name": "Transactions test envelope"},
    )
    assert response.status_code == 201
    return response.json()["id"]


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


async def test_update_transaction_sets_manual_categorization(client, envelope_id):
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
        json={"envelope_id": envelope_id},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["envelope_id"] == envelope_id
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


async def _post_transaction(client, *, amount, transaction_date, envelope_id):
    response = await client.post(
        "/budget/transactions",
        json={
            "account_id": SEEDED_ACCOUNT_ID,
            "envelope_id": envelope_id,
            "amount": amount,
            "currency": "PLN",
            "transaction_date": transaction_date,
        },
    )
    assert response.status_code == 201
    return response.json()


async def test_spent_by_envelope_sums_only_money_out(client, envelope_id):
    """Income must not net off spending: an envelope that received a refund has
    not "spent less", and letting it cancel out would show room that is not
    there."""
    await _post_transaction(client, envelope_id=envelope_id, amount="-40.00", transaction_date="2030-03-05")
    await _post_transaction(client, envelope_id=envelope_id, amount="-60.00", transaction_date="2030-03-06")
    await _post_transaction(client, envelope_id=envelope_id, amount="500.00", transaction_date="2030-03-07")

    response = await client.get(
        "/budget/transactions/spent-by-envelope", params={"dateFrom": "2030-03-01", "dateTo": "2030-03-31"}
    )
    assert response.status_code == 200
    rows = {r["envelope_id"]: r["spent"] for r in response.json()}
    assert rows[envelope_id] == "100.00"


async def test_spent_by_envelope_respects_the_period(client, envelope_id):
    await _post_transaction(client, envelope_id=envelope_id, amount="-40.00", transaction_date="2030-04-05")
    await _post_transaction(client, envelope_id=envelope_id, amount="-1000.00", transaction_date="2030-05-05")

    response = await client.get(
        "/budget/transactions/spent-by-envelope", params={"dateFrom": "2030-04-01", "dateTo": "2030-04-30"}
    )
    rows = {r["envelope_id"]: r["spent"] for r in response.json()}
    assert rows[envelope_id] == "40.00"


async def test_spent_by_envelope_returns_an_empty_list_for_a_quiet_period(client):
    """An empty list, not the 404 the transaction *list* endpoint raises: a month
    with no spending is a real answer, not a missing resource. The frontend sums
    these into "Spent" columns, and a 404 there would read as zero anyway - but
    only by accident."""
    response = await client.get(
        "/budget/transactions/spent-by-envelope", params={"dateFrom": "2035-01-01", "dateTo": "2035-01-31"}
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_spent_by_envelope_is_not_capped_by_the_list_page_size(client, envelope_id):
    """The whole point of the endpoint. `GET /budget/transactions` returns at
    most `limit` rows, so summing that list client-side silently understated
    every total once a period held more transactions than one page."""
    for day in range(1, 8):
        for _ in range(20):
            await _post_transaction(client, envelope_id=envelope_id, amount="-1.00", transaction_date=f"2030-06-{day:02d}")

    listed = await client.get(
        "/budget/transactions", params={"dateFrom": "2030-06-01", "dateTo": "2030-06-30", "limit": 100}
    )
    assert len(listed.json()) == 100  # 140 exist, one page holds 100

    response = await client.get(
        "/budget/transactions/spent-by-envelope", params={"dateFrom": "2030-06-01", "dateTo": "2030-06-30"}
    )
    rows = {r["envelope_id"]: r["spent"] for r in response.json()}
    assert rows[envelope_id] == "140.00"


async def test_transactions_are_listed_newest_first(client, envelope_id):
    """Without an ORDER BY, which rows a LIMIT returns is whatever the planner
    produced - so "the latest 100" was really "an arbitrary 100", and paging
    through `skip` could repeat or skip rows."""
    await _post_transaction(client, envelope_id=envelope_id, amount="-10.00", transaction_date="2031-01-10")
    await _post_transaction(client, envelope_id=envelope_id, amount="-20.00", transaction_date="2031-01-30")
    await _post_transaction(client, envelope_id=envelope_id, amount="-30.00", transaction_date="2031-01-20")

    response = await client.get(
        "/budget/transactions", params={"dateFrom": "2031-01-01", "dateTo": "2031-01-31"}
    )
    dates = [t["transaction_date"] for t in response.json()]
    assert dates == sorted(dates, reverse=True)
    assert dates[0] == "2031-01-30"


async def test_transaction_list_reports_the_full_match_count(client, envelope_id):
    """Without this the screen had no way to tell a full page from the end of the
    data - it showed 100 rows and called that "100 of 100" while 410 matched."""
    for day in range(1, 6):
        await _post_transaction(client, envelope_id=envelope_id, amount="-1.00", transaction_date=f"2032-02-{day:02d}")

    response = await client.get(
        "/budget/transactions",
        params={"dateFrom": "2032-02-01", "dateTo": "2032-02-28", "limit": 2},
    )
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.headers["X-Total-Count"] == "5"


async def test_transaction_list_pages_without_repeating_or_skipping(client, envelope_id):
    for day in range(1, 6):
        await _post_transaction(client, envelope_id=envelope_id, amount=f"-{day}.00", transaction_date=f"2032-03-{day:02d}")

    params = {"dateFrom": "2032-03-01", "dateTo": "2032-03-31", "limit": 2}
    seen = []
    for skip in (0, 2, 4):
        page = (await client.get("/budget/transactions", params={**params, "skip": skip})).json()
        seen.extend(t["id"] for t in page)

    assert len(seen) == 5
    assert len(set(seen)) == 5  # a stable ORDER BY is what makes this hold


async def test_a_page_past_the_end_is_empty_not_an_error(client):
    """It used to 404. That made the last page of a paginated list look like a
    broken request, and an empty month indistinguishable from a failure."""
    response = await client.get(
        "/budget/transactions", params={"dateFrom": "2033-01-01", "dateTo": "2033-01-31"}
    )
    assert response.status_code == 200
    assert response.json() == []
    assert response.headers["X-Total-Count"] == "0"


async def test_search_matches_payee_name(client):
    payee = (await client.post("/budget/payees", json={"name": "Kwiaciarnia Stokrotka"})).json()
    await client.post(
        "/budget/transactions",
        json={
            "account_id": SEEDED_ACCOUNT_ID,
            "payee_id": payee["id"],
            "amount": "-19.99",
            "currency": "PLN",
            "transaction_date": "2034-05-01",
        },
    )

    response = await client.get(
        "/budget/transactions",
        params={"dateFrom": "2034-05-01", "dateTo": "2034-05-31", "q": "stokrotka"},
    )
    assert len(response.json()) == 1
    assert response.headers["X-Total-Count"] == "1"


async def test_search_matches_description_case_insensitively(client):
    await client.post(
        "/budget/transactions",
        json={
            "account_id": SEEDED_ACCOUNT_ID,
            "amount": "-30.00",
            "currency": "PLN",
            "description": "Bilet miesięczny",
            "transaction_date": "2034-06-01",
        },
    )

    response = await client.get(
        "/budget/transactions",
        params={"dateFrom": "2034-06-01", "dateTo": "2034-06-30", "q": "BILET"},
    )
    assert len(response.json()) == 1


async def test_search_matches_an_amount_ignoring_its_sign(client, envelope_id):
    """The table renders "−42,50 zł" and nobody types the minus when looking for
    a payment."""
    await _post_transaction(client, envelope_id=envelope_id, amount="-42.50", transaction_date="2034-07-01")
    await _post_transaction(client, envelope_id=envelope_id, amount="-99.00", transaction_date="2034-07-02")

    response = await client.get(
        "/budget/transactions",
        params={"dateFrom": "2034-07-01", "dateTo": "2034-07-31", "q": "42,50"},
    )
    assert [t["amount"] for t in response.json()] == ["-42.50"]


async def test_search_keeps_transactions_that_have_no_payee(client):
    """The payee lookup is an OUTER join. An inner one would drop every
    uncategorised row - the ones most worth finding - from both the page and the
    count."""
    await client.post(
        "/budget/transactions",
        json={
            "account_id": SEEDED_ACCOUNT_ID,
            "amount": "-15.00",
            "currency": "PLN",
            "description": "Nieznana płatność kartą",
            "transaction_date": "2034-08-01",
        },
    )

    response = await client.get(
        "/budget/transactions",
        params={"dateFrom": "2034-08-01", "dateTo": "2034-08-31", "q": "nieznana"},
    )
    assert len(response.json()) == 1
    assert response.json()[0]["payee_id"] is None


async def test_search_count_matches_the_search_not_the_whole_period(client, envelope_id):
    """The count and the page are built from one shared filter helper - a total
    that ignored `q` would make the pager offer pages that do not exist."""
    for day in range(1, 4):
        await _post_transaction(client, envelope_id=envelope_id, amount="-5.00", transaction_date=f"2034-09-{day:02d}")
    await client.post(
        "/budget/transactions",
        json={
            "account_id": SEEDED_ACCOUNT_ID,
            "amount": "-5.00",
            "currency": "PLN",
            "description": "Prezent urodzinowy",
            "transaction_date": "2034-09-04",
        },
    )

    response = await client.get(
        "/budget/transactions",
        params={"dateFrom": "2034-09-01", "dateTo": "2034-09-30", "q": "prezent"},
    )
    assert response.headers["X-Total-Count"] == "1"
