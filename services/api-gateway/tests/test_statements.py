from app.core.config import get_settings

SEEDED_ACCOUNT_ID = "00000000-0000-0000-0000-000000000101"
SEEDED_ENVELOPE_GROCERIES_ID = "00000000-0000-0000-0000-000000000401"
SEEDED_ENVELOPE_SUBSCRIPTIONS_ID = "00000000-0000-0000-0000-000000000403"


async def test_upload_statement_success(client):
    response = await client.post(
        "/budget/statements/upload",
        data={"account_id": SEEDED_ACCOUNT_ID},
        files={
            "file": (
                "jan.csv",
                b"date,amount,description,payee\n2026-01-01,10.00,Coffee,Starbucks\n",
                "text/csv",
            )
        },
    )
    assert response.status_code == 201
    statement = response.json()
    assert statement["account_id"] == SEEDED_ACCOUNT_ID
    assert statement["filename"] == "jan.csv"
    assert statement["format"] == "csv"
    assert statement["status"] == "parsed"
    assert statement["error_message"] is None

    transactions = (
        await client.get(
            "/budget/transactions", params={"accountId": SEEDED_ACCOUNT_ID}
        )
    ).json()
    imported = [t for t in transactions if t["statement_id"] == statement["id"]]
    assert len(imported) == 1
    assert imported[0]["amount"] == "10.00"
    assert imported[0]["description"] == "Coffee"
    assert imported[0]["currency"] == "PLN"

    payees = (await client.get("/budget/payees")).json()
    assert any(p["id"] == imported[0]["payee_id"] for p in payees)


async def test_upload_statement_rejects_unsupported_format(client):
    response = await client.post(
        "/budget/statements/upload",
        data={"account_id": SEEDED_ACCOUNT_ID},
        files={"file": ("jan.pdf", b"%PDF-1.4 not a real pdf", "application/pdf")},
    )
    assert response.status_code == 400


async def test_upload_statement_rejects_empty_file(client):
    response = await client.post(
        "/budget/statements/upload",
        data={"account_id": SEEDED_ACCOUNT_ID},
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert response.status_code == 400


async def test_upload_statement_rejects_oversized_file(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_size_bytes", 10)

    response = await client.post(
        "/budget/statements/upload",
        data={"account_id": SEEDED_ACCOUNT_ID},
        files={"file": ("jan.csv", b"date,amount\n2026-01-01,10.00\n", "text/csv")},
    )
    assert response.status_code == 413


async def test_upload_statement_missing_account_returns_404(client):
    response = await client.post(
        "/budget/statements/upload",
        data={"account_id": "00000000-0000-0000-0000-000000009999"},
        files={"file": ("jan.csv", b"date,amount\n2026-01-01,10.00\n", "text/csv")},
    )
    assert response.status_code == 404


async def test_upload_statement_missing_required_column_marks_failed(client):
    response = await client.post(
        "/budget/statements/upload",
        data={"account_id": SEEDED_ACCOUNT_ID},
        files={"file": ("jan.csv", b"date,description\n2026-01-01,Coffee\n", "text/csv")},
    )
    assert response.status_code == 201
    statement = response.json()
    assert statement["status"] == "failed"
    assert statement["error_message"]


async def test_upload_statement_invalid_date_marks_failed(client):
    response = await client.post(
        "/budget/statements/upload",
        data={"account_id": SEEDED_ACCOUNT_ID},
        files={"file": ("jan.csv", b"date,amount\n01-01-2026,10.00\n", "text/csv")},
    )
    assert response.status_code == 201
    statement = response.json()
    assert statement["status"] == "failed"
    assert statement["error_message"]


async def test_upload_statement_invalid_amount_marks_failed(client):
    response = await client.post(
        "/budget/statements/upload",
        data={"account_id": SEEDED_ACCOUNT_ID},
        files={
            "file": (
                "jan.csv",
                b"date,amount\n2026-01-01,not-a-number\n",
                "text/csv",
            )
        },
    )
    assert response.status_code == 201
    statement = response.json()
    assert statement["status"] == "failed"
    assert statement["error_message"]


async def test_upload_statement_zero_amount_marks_failed(client):
    response = await client.post(
        "/budget/statements/upload",
        data={"account_id": SEEDED_ACCOUNT_ID},
        files={"file": ("jan.csv", b"date,amount\n2026-01-01,0\n", "text/csv")},
    )
    assert response.status_code == 201
    statement = response.json()
    assert statement["status"] == "failed"
    assert statement["error_message"]


async def test_upload_statement_partial_bad_file_creates_zero_transactions(client):
    response = await client.post(
        "/budget/statements/upload",
        data={"account_id": SEEDED_ACCOUNT_ID},
        files={
            "file": (
                "jan.csv",
                b"date,amount\n2026-01-01,10.00\n2026-01-02,not-a-number\n",
                "text/csv",
            )
        },
    )
    assert response.status_code == 201
    statement = response.json()
    assert statement["status"] == "failed"

    transactions = (
        await client.get(
            "/budget/transactions", params={"accountId": SEEDED_ACCOUNT_ID}
        )
    ).json()
    imported = [t for t in transactions if t["statement_id"] == statement["id"]]
    assert imported == []


async def test_upload_statement_applies_matching_categorization_rule(client):
    rule_response = await client.post(
        "/budget/categorization-rules",
        json={"envelope_id": SEEDED_ENVELOPE_SUBSCRIPTIONS_ID, "phrase": "UBER EATS"},
    )
    assert rule_response.status_code == 201

    response = await client.post(
        "/budget/statements/upload",
        data={"account_id": SEEDED_ACCOUNT_ID},
        files={
            "file": (
                "feb.csv",
                b"date,amount,description,payee\n"
                b"2026-02-01,35.00,UBER EATS ORDER,Uber Eats\n",
                "text/csv",
            )
        },
    )
    assert response.status_code == 201
    statement = response.json()

    transactions = (
        await client.get(
            "/budget/transactions", params={"accountId": SEEDED_ACCOUNT_ID}
        )
    ).json()
    imported = [t for t in transactions if t["statement_id"] == statement["id"]]
    assert len(imported) == 1
    assert imported[0]["envelope_id"] == SEEDED_ENVELOPE_SUBSCRIPTIONS_ID
    assert imported[0]["categorization_source"] == "rule"


async def test_upload_statement_prefers_payee_history_over_rule(client):
    # Seeded payee "Biedronka" already has a prior transaction categorized
    # into the Groceries envelope (infra/postgres/seed/seed_data.sql).
    rule_response = await client.post(
        "/budget/categorization-rules",
        json={
            "envelope_id": SEEDED_ENVELOPE_SUBSCRIPTIONS_ID,
            "phrase": "SUPERMARKET",
        },
    )
    assert rule_response.status_code == 201

    response = await client.post(
        "/budget/statements/upload",
        data={"account_id": SEEDED_ACCOUNT_ID},
        files={
            "file": (
                "feb.csv",
                b"date,amount,description,payee\n"
                b"2026-02-02,50.00,SUPERMARKET RUN,Biedronka\n",
                "text/csv",
            )
        },
    )
    assert response.status_code == 201
    statement = response.json()

    transactions = (
        await client.get(
            "/budget/transactions", params={"accountId": SEEDED_ACCOUNT_ID}
        )
    ).json()
    imported = [t for t in transactions if t["statement_id"] == statement["id"]]
    assert len(imported) == 1
    assert imported[0]["envelope_id"] == SEEDED_ENVELOPE_GROCERIES_ID
    assert imported[0]["categorization_source"] == "rule"


async def test_upload_statement_without_match_leaves_transaction_uncategorized(client):
    response = await client.post(
        "/budget/statements/upload",
        data={"account_id": SEEDED_ACCOUNT_ID},
        files={
            "file": (
                "feb.csv",
                b"date,amount,description,payee\n"
                b"2026-02-03,12.00,Unrecognized purchase,Random Merchant XYZ\n",
                "text/csv",
            )
        },
    )
    assert response.status_code == 201
    statement = response.json()

    transactions = (
        await client.get(
            "/budget/transactions", params={"accountId": SEEDED_ACCOUNT_ID}
        )
    ).json()
    imported = [t for t in transactions if t["statement_id"] == statement["id"]]
    assert len(imported) == 1
    assert imported[0]["envelope_id"] is None
    assert imported[0]["categorization_source"] is None
