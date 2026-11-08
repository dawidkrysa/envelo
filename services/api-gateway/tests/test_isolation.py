"""Per-user data isolation (#37, step 3).

Two real users, signed in with real tokens: Alice builds a small budget, and
Bob - who knows every one of her ids - tries to read it, change it, delete it,
and point his own rows at it. Every attempt must look exactly like the id not
existing at all (404), and Alice's budget must be untouched afterwards.

A single-user test cannot catch a missing user filter: with one user, "my rows"
and "all rows" are the same rows. This file is the only thing that notices.
"""

import uuid

import pytest
import pytest_asyncio
from app.db.repositories.categorization_rule import match_envelope_for_transaction

PASSWORD = "correct horse battery"
MONTH = "2026-03-01"


async def _sign_up(client) -> dict:
    email = f"user-{uuid.uuid4().hex[:12]}@example.com"
    response = await client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert response.status_code == 201, response.text
    access_token = response.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


async def _post(client, headers, path, body) -> dict:
    response = await client.post(path, json=body, headers=headers)
    assert response.status_code == 201, f"{path}: {response.text}"
    return response.json()


async def _build_budget(client, headers, label: str) -> dict:
    """One of everything, owned by whoever `headers` signs in as."""
    group = await _post(client, headers, "/budget/category-groups", {"name": f"{label} group", "sort_order": 1})
    envelope = await _post(
        client, headers, "/budget/envelopes", {"category_group_id": group["id"], "name": f"{label} groceries"}
    )
    account = await _post(
        client, headers, "/budget/accounts", {"name": f"{label} bank", "type": "checking", "currency": "PLN"}
    )
    payee = await _post(client, headers, "/budget/payees", {"name": f"{label} shop"})
    transaction = await _post(
        client,
        headers,
        "/budget/transactions",
        {
            "account_id": account["id"],
            "envelope_id": envelope["id"],
            "payee_id": payee["id"],
            "amount": "-42.50",
            "currency": "PLN",
            "transaction_date": "2026-03-05",
        },
    )
    allocation = await _post(
        client,
        headers,
        "/budget/envelope-allocations",
        {"envelope_id": envelope["id"], "month": MONTH, "assigned_amount": "300.00"},
    )
    rule = await _post(
        client, headers, "/budget/categorization-rules", {"envelope_id": envelope["id"], "phrase": "Biedronka"}
    )
    upload = await client.post(
        "/budget/statements/upload",
        data={"account_id": account["id"]},
        files={"file": ("mar.csv", b"date,amount,description,payee\n2026-03-07,-10.00,Bread,Bakery\n", "text/csv")},
        headers=headers,
    )
    assert upload.status_code == 201, upload.text
    return {
        "group": group["id"],
        "envelope": envelope["id"],
        "account": account["id"],
        "payee": payee["id"],
        "transaction": transaction["id"],
        "allocation": allocation["id"],
        "rule": rule["id"],
        "statement": upload.json()["id"],
    }


@pytest_asyncio.fixture
async def alice(anon_client):
    return await _sign_up(anon_client)


@pytest_asyncio.fixture
async def bob(anon_client):
    return await _sign_up(anon_client)


@pytest_asyncio.fixture
async def alices(anon_client, alice):
    return await _build_budget(anon_client, alice, "Alice")


# --- Reads -----------------------------------------------------------------


# The gateway answers "no rows" with 404 on most list endpoints (see CLAUDE.md),
# so for a user with nothing yet, that is the expected answer - not Alice's rows.
@pytest.mark.parametrize(
    "path",
    [
        "/budget/accounts",
        "/budget/payees",
        "/budget/category-groups",
        "/budget/envelopes",
        "/budget/envelope-allocations",
        "/budget/categorization-rules",
        "/budget/statements",
    ],
)
async def test_lists_show_nothing_of_another_users(anon_client, alices, bob, path):
    response = await anon_client.get(path, headers=bob)
    assert response.status_code == 404, response.text


@pytest.mark.parametrize(
    "path",
    [
        "/budget/transactions",
        "/budget/transactions/spent-by-envelope",
        "/budget/accounts/balances",
        "/budget/payees/stats",
    ],
)
async def test_aggregates_show_nothing_of_another_users(anon_client, alices, bob, path):
    response = await anon_client.get(path, headers=bob)
    assert response.status_code == 200
    assert response.json() == []


async def test_transaction_count_ignores_another_users(anon_client, alices, bob):
    response = await anon_client.get("/budget/transactions", headers=bob)
    assert response.headers["X-Total-Count"] == "0"


async def test_to_assign_ignores_another_users_money(anon_client, alices, bob):
    response = await anon_client.get("/budget/envelope-allocations/to-assign", headers=bob)
    assert float(response.json()["to_assign"]) == 0


async def test_forecast_ignores_another_users_envelopes(anon_client, alices, bob):
    response = await anon_client.get(f"/budget/forecast?month={MONTH}", headers=bob)
    assert response.status_code == 200
    forecast = response.json()
    assert forecast["envelopes"] == []
    assert forecast["category_groups"] == []
    assert float(forecast["funded_total"]) == 0


async def test_filtering_by_another_users_id_returns_nothing(anon_client, alices, bob):
    # Filters narrow the caller's own rows; naming Alice's account must not
    # widen them to hers.
    transactions = await anon_client.get(f"/budget/transactions?accountId={alices['account']}", headers=bob)
    assert transactions.json() == []
    envelopes = await anon_client.get(f"/budget/envelopes?categoryGroupId={alices['group']}", headers=bob)
    assert envelopes.status_code == 404


# --- Writes to Alice's rows -------------------------------------------------


@pytest.mark.parametrize(
    ("key", "path", "body"),
    [
        ("account", "/budget/accounts/{}", {"name": "Hijacked"}),
        ("payee", "/budget/payees/{}", {"name": "Hijacked"}),
        ("group", "/budget/category-groups/{}", {"name": "Hijacked"}),
        ("envelope", "/budget/envelopes/{}", {"name": "Hijacked"}),
        ("allocation", "/budget/envelope-allocations/{}", {"assigned_amount": "0.00"}),
        ("rule", "/budget/categorization-rules/{}", {"phrase": "Hijacked"}),
        ("statement", "/budget/statements/{}", {}),
        ("transaction", "/budget/transactions/{}", {"description": "Hijacked"}),
    ],
)
async def test_cannot_update_another_users_rows(anon_client, alices, bob, key, path, body):
    response = await anon_client.put(path.format(alices[key]), json=body, headers=bob)
    assert response.status_code == 404, response.text


@pytest.mark.parametrize(
    ("key", "path"),
    [
        ("transaction", "/budget/transactions/{}"),
        ("rule", "/budget/categorization-rules/{}"),
        ("statement", "/budget/statements/{}"),
        ("envelope", "/budget/envelopes/{}"),
        ("payee", "/budget/payees/{}"),
        ("group", "/budget/category-groups/{}"),
        ("account", "/budget/accounts/{}"),
    ],
)
async def test_cannot_delete_another_users_rows(anon_client, alices, bob, key, path):
    response = await anon_client.delete(path.format(alices[key]), headers=bob)
    assert response.status_code == 404, response.text


async def test_failed_attempts_leave_the_owners_budget_intact(anon_client, alice, alices, bob):
    for key, path in [
        ("transaction", "/budget/transactions/{}"),
        ("envelope", "/budget/envelopes/{}"),
        ("account", "/budget/accounts/{}"),
    ]:
        await anon_client.delete(path.format(alices[key]), headers=bob)
    await anon_client.put(f"/budget/envelopes/{alices['envelope']}", json={"name": "Hijacked"}, headers=bob)

    envelopes = (await anon_client.get("/budget/envelopes", headers=alice)).json()
    assert [e["name"] for e in envelopes] == ["Alice groceries"]
    transactions = (await anon_client.get("/budget/transactions", headers=alice)).json()
    assert alices["transaction"] in {t["id"] for t in transactions}
    accounts = (await anon_client.get("/budget/accounts", headers=alice)).json()
    assert [a["id"] for a in accounts] == [alices["account"]]


# --- Bob's rows pointing at Alice's ------------------------------------------


@pytest_asyncio.fixture
async def bobs(anon_client, bob):
    return await _build_budget(anon_client, bob, "Bob")


def _transaction(account_id, **ids) -> dict:
    return {"account_id": account_id, "amount": "-1.00", "currency": "PLN", "transaction_date": "2026-03-10", **ids}


@pytest.mark.parametrize("field", ["envelope_id", "payee_id", "statement_id"])
async def test_cannot_create_a_transaction_against_another_users_rows(anon_client, alices, bob, bobs, field):
    key = {"envelope_id": "envelope", "payee_id": "payee", "statement_id": "statement"}[field]
    body = _transaction(bobs["account"], **{field: alices[key]})
    response = await anon_client.post("/budget/transactions", json=body, headers=bob)
    assert response.status_code == 404, response.text


async def test_cannot_create_a_transaction_in_another_users_account(anon_client, alices, bob):
    response = await anon_client.post("/budget/transactions", json=_transaction(alices["account"]), headers=bob)
    assert response.status_code == 404


async def test_cannot_move_own_transaction_into_another_users_envelope(anon_client, alices, bob, bobs):
    response = await anon_client.put(
        f"/budget/transactions/{bobs['transaction']}", json={"envelope_id": alices["envelope"]}, headers=bob
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/budget/envelopes", lambda a, b: {"category_group_id": a["group"], "name": "Sneaky"}),
        ("/budget/envelope-allocations", lambda a, b: {"envelope_id": a["envelope"], "month": "2026-04-01", "assigned_amount": "1"}),
        ("/budget/categorization-rules", lambda a, b: {"envelope_id": a["envelope"], "phrase": "Sneaky"}),
    ],
)
async def test_cannot_create_rows_under_another_users_parent(anon_client, alices, bob, bobs, path, body):
    response = await anon_client.post(path, json=body(alices, bobs), headers=bob)
    assert response.status_code == 404, response.text


async def test_cannot_move_own_envelope_into_another_users_group(anon_client, alices, bob, bobs):
    response = await anon_client.put(
        f"/budget/envelopes/{bobs['envelope']}", json={"category_group_id": alices["group"]}, headers=bob
    )
    assert response.status_code == 404


async def test_cannot_upload_a_statement_into_another_users_account(anon_client, alices, bob):
    response = await anon_client.post(
        "/budget/statements/upload",
        data={"account_id": alices["account"]},
        files={"file": ("x.csv", b"date,amount,description,payee\n2026-03-07,-1.00,X,Y\n", "text/csv")},
        headers=bob,
    )
    assert response.status_code == 404


@pytest.mark.parametrize("direction", ["into-alice", "out-of-alice"])
async def test_cannot_transfer_money_across_users(anon_client, alices, bob, bobs, direction):
    source, target = (bobs, alices) if direction == "into-alice" else (alices, bobs)
    response = await anon_client.post(
        "/budget/envelope-allocations/transfer",
        json={
            "from_envelope_id": source["envelope"],
            "to_envelope_id": target["envelope"],
            "month": MONTH,
            "amount": "1.00",
        },
        headers=bob,
    )
    assert response.status_code == 404, response.text


@pytest.mark.parametrize("direction", ["into-alice", "out-of-alice"])
async def test_cannot_merge_payees_across_users(anon_client, alices, bob, bobs, direction):
    source, target = (bobs, alices) if direction == "into-alice" else (alices, bobs)
    response = await anon_client.post(
        "/budget/payees/merge",
        json={"from_payee_id": source["payee"], "into_payee_id": target["payee"]},
        headers=bob,
    )
    assert response.status_code == 404, response.text


# --- Categorization ----------------------------------------------------------


async def test_another_users_rule_does_not_file_my_import(anon_client, alices, bob):
    # Alice has a rule "Biedronka" -> her envelope. Bob imports a Biedronka
    # receipt: it must stay uncategorized, not land in (or point at) her budget.
    account = await _post(anon_client, bob, "/budget/accounts", {"name": "Bob", "type": "checking", "currency": "PLN"})
    upload = await anon_client.post(
        "/budget/statements/upload",
        data={"account_id": account["id"]},
        files={"file": ("b.csv", b"date,amount,description,payee\n2026-03-08,-5.00,Milk,Biedronka\n", "text/csv")},
        headers=bob,
    )
    assert upload.status_code == 201, upload.text

    transactions = (await anon_client.get("/budget/transactions", headers=bob)).json()
    assert len(transactions) == 1
    assert transactions[0]["envelope_id"] is None


async def test_payee_history_is_per_user(db_session, anon_client, alices, bob):
    # Alice's payee has a filed transaction; Bob asking about the same payee id
    # must not inherit her filing.
    me = (await anon_client.get("/budget/transactions", headers=bob)).json()
    assert me == []
    from app.core.security import decode_access_token

    bob_id = decode_access_token(bob["Authorization"].removeprefix("Bearer "))
    assert await match_envelope_for_transaction(db_session, bob_id, uuid.UUID(alices["payee"]), "Alice shop") is None


async def test_imports_do_not_reuse_another_users_payee(anon_client, alices, bob):
    account = await _post(anon_client, bob, "/budget/accounts", {"name": "Bob", "type": "checking", "currency": "PLN"})
    await anon_client.post(
        "/budget/statements/upload",
        data={"account_id": account["id"]},
        files={"file": ("b.csv", b"date,amount,description,payee\n2026-03-08,-5.00,Cake,Alice shop\n", "text/csv")},
        headers=bob,
    )
    transactions = (await anon_client.get("/budget/transactions", headers=bob)).json()
    assert transactions[0]["payee_id"] not in (None, alices["payee"])
