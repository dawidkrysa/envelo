from app.core.config import get_settings

SEEDED_ACCOUNT_ID = "00000000-0000-0000-0000-000000000101"
SEEDED_CATEGORY_GROUP_ID = "00000000-0000-0000-0000-000000000301"


async def _create_envelope(client, name: str) -> str:
    """Created here rather than borrowing a seeded envelope id.

    The categorization tests below used to lean on two seeded rows and on the
    seeded Biedronka -> Groceries transaction history. Envelopes can be deleted
    now, and deleting one uncategorises its transactions - so both the row and the
    history it carried could vanish from the shared dev database, which is exactly
    what happened. Building the situation in the test makes it independent of
    whatever the database currently holds.
    """
    response = await client.post(
        "/budget/envelopes",
        json={"category_group_id": SEEDED_CATEGORY_GROUP_ID, "name": name},
    )
    assert response.status_code == 201
    return response.json()["id"]


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
            "/budget/transactions",
            # Scoped to the window the fixture CSVs use. `GET /budget/transactions`
            # returns one page of the newest rows, so an unscoped lookup only found
            # these while the database happened to be nearly empty.
            params={"accountId": SEEDED_ACCOUNT_ID, "dateFrom": "2026-01-01", "dateTo": "2026-02-28"},
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
            "/budget/transactions",
            # Scoped to the window the fixture CSVs use. `GET /budget/transactions`
            # returns one page of the newest rows, so an unscoped lookup only found
            # these while the database happened to be nearly empty.
            params={"accountId": SEEDED_ACCOUNT_ID, "dateFrom": "2026-01-01", "dateTo": "2026-02-28"},
        )
    ).json()
    imported = [t for t in transactions if t["statement_id"] == statement["id"]]
    assert imported == []


async def test_upload_statement_applies_matching_categorization_rule(client):
    envelope_id = await _create_envelope(client, "Rule-matched envelope")
    rule_response = await client.post(
        "/budget/categorization-rules",
        json={"envelope_id": envelope_id, "phrase": "UBER EATS"},
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
            "/budget/transactions",
            # Scoped to the window the fixture CSVs use. `GET /budget/transactions`
            # returns one page of the newest rows, so an unscoped lookup only found
            # these while the database happened to be nearly empty.
            params={"accountId": SEEDED_ACCOUNT_ID, "dateFrom": "2026-01-01", "dateTo": "2026-02-28"},
        )
    ).json()
    imported = [t for t in transactions if t["statement_id"] == statement["id"]]
    assert len(imported) == 1
    assert imported[0]["envelope_id"] == envelope_id
    assert imported[0]["categorization_source"] == "rule"


async def test_upload_statement_prefers_payee_history_over_rule(client):
    """Where a payee has been filed before wins over a phrase rule.

    The history is built here rather than borrowed from the seed data: the payee
    needs a prior transaction in a specific envelope, and that is a fact about the
    database that a test asserting on it should own.
    """
    history_envelope_id = await _create_envelope(client, "Where this payee usually goes")
    rule_envelope_id = await _create_envelope(client, "Where the rule would put it")

    payee = (await client.post("/budget/payees", json={"name": "Sklep Historyczny"})).json()
    prior = await client.post(
        "/budget/transactions",
        json={
            "account_id": SEEDED_ACCOUNT_ID,
            "envelope_id": history_envelope_id,
            "payee_id": payee["id"],
            "amount": "-30.00",
            "currency": "PLN",
            "transaction_date": "2026-01-15",
        },
    )
    assert prior.status_code == 201

    rule_response = await client.post(
        "/budget/categorization-rules",
        json={"envelope_id": rule_envelope_id, "phrase": "SUPERMARKET"},
    )
    assert rule_response.status_code == 201

    # Matches the rule's phrase *and* names the payee with history - the two
    # deliberately disagree, so the assertion below can only pass one way.
    response = await client.post(
        "/budget/statements/upload",
        data={"account_id": SEEDED_ACCOUNT_ID},
        files={
            "file": (
                "feb.csv",
                b"date,amount,description,payee\n"
                b"2026-02-02,50.00,SUPERMARKET RUN,Sklep Historyczny\n",
                "text/csv",
            )
        },
    )
    assert response.status_code == 201
    statement = response.json()

    transactions = (
        await client.get(
            "/budget/transactions",
            # Scoped to the window the fixture CSVs use. `GET /budget/transactions`
            # returns one page of the newest rows, so an unscoped lookup only found
            # these while the database happened to be nearly empty.
            params={"accountId": SEEDED_ACCOUNT_ID, "dateFrom": "2026-01-01", "dateTo": "2026-02-28"},
        )
    ).json()
    imported = [t for t in transactions if t["statement_id"] == statement["id"]]
    assert len(imported) == 1
    assert imported[0]["envelope_id"] == history_envelope_id
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
            "/budget/transactions",
            # Scoped to the window the fixture CSVs use. `GET /budget/transactions`
            # returns one page of the newest rows, so an unscoped lookup only found
            # these while the database happened to be nearly empty.
            params={"accountId": SEEDED_ACCOUNT_ID, "dateFrom": "2026-01-01", "dateTo": "2026-02-28"},
        )
    ).json()
    imported = [t for t in transactions if t["statement_id"] == statement["id"]]
    assert len(imported) == 1
    assert imported[0]["envelope_id"] is None
    assert imported[0]["categorization_source"] is None
