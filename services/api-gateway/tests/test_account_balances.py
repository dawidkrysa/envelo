from decimal import Decimal

SEEDED_ACCOUNT_ID = "00000000-0000-0000-0000-000000000101"


async def _create_account(client, name: str, *, currency: str = "PLN") -> str:
    response = await client.post(
        "/budget/accounts",
        json={"name": name, "type": "checking", "currency": currency},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _post_transaction(client, account_id: str, amount: str, day: str) -> None:
    response = await client.post(
        "/budget/transactions",
        json={
            "account_id": account_id,
            "amount": amount,
            "currency": "PLN",
            "transaction_date": day,
        },
    )
    assert response.status_code == 201


async def _balances(client) -> dict[str, dict]:
    response = await client.get("/budget/accounts/balances")
    assert response.status_code == 200
    return {row["account_id"]: row for row in response.json()}


async def test_balance_is_the_sum_of_every_transaction_on_the_account(client):
    account_id = await _create_account(client, "Balance under test")
    await _post_transaction(client, account_id, "1000.00", "2026-03-01")
    await _post_transaction(client, account_id, "-250.50", "2026-03-02")

    row = (await _balances(client))[account_id]

    assert Decimal(row["balance"]) == Decimal("749.50")
    assert row["transaction_count"] == 2


async def test_a_balance_can_be_negative(client):
    """A credit card in debt is the normal case for one, so this must not be
    clamped or reported as an absolute value."""
    account_id = await _create_account(client, "Card in debt")
    await _post_transaction(client, account_id, "-318.44", "2026-03-01")

    assert Decimal((await _balances(client))[account_id]["balance"]) == Decimal("-318.44")


async def test_an_untouched_account_is_listed_with_a_zero_balance(client):
    """Left out entirely, this screen's account list would disagree with
    `GET /budget/accounts` - a new account would simply not appear."""
    account_id = await _create_account(client, "Nothing has happened here")

    row = (await _balances(client))[account_id]

    assert Decimal(row["balance"]) == Decimal("0")
    assert row["transaction_count"] == 0
    assert row["last_imported_at"] is None


async def test_one_accounts_transactions_do_not_land_on_another(client):
    first = await _create_account(client, "First")
    second = await _create_account(client, "Second")
    await _post_transaction(client, first, "100.00", "2026-03-01")

    balances = await _balances(client)

    assert Decimal(balances[first]["balance"]) == Decimal("100.00")
    assert Decimal(balances[second]["balance"]) == Decimal("0")


async def test_last_imported_at_follows_the_newest_statement(client):
    account_id = await _create_account(client, "Imported into twice")
    for _ in range(2):
        response = await client.post(
            "/budget/statements/upload",
            data={"account_id": account_id},
            files={"file": ("jan.csv", b"date,amount\n2026-01-01,10.00\n", "text/csv")},
        )
        assert response.status_code == 201
    statements = (await client.get("/budget/statements", params={"accountId": account_id})).json()
    newest = max(s["imported_at"] for s in statements)

    assert (await _balances(client))[account_id]["last_imported_at"] == newest


async def test_a_balance_is_not_capped_by_the_transaction_page_size(client):
    """The whole point of the aggregate. `GET /budget/transactions` returns at
    most `limit` rows, so summing that list client-side would understate any
    account with more history than one page."""
    account_id = await _create_account(client, "Busy account")
    for day in range(1, 8):
        for _ in range(20):
            await _post_transaction(client, account_id, "-1.00", f"2026-04-{day:02d}")

    row = (await _balances(client))[account_id]

    assert row["transaction_count"] == 140
    assert Decimal(row["balance"]) == Decimal("-140.00")


async def test_balances_cover_the_seeded_account_too(client):
    """Sanity check that the endpoint reports on accounts it did not create -
    the assertions above all build their own."""
    assert SEEDED_ACCOUNT_ID in await _balances(client)
