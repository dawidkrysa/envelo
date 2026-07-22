from app.core.config import get_settings

SEEDED_ACCOUNT_ID = "00000000-0000-0000-0000-000000000101"


async def test_upload_statement_success(client):
    response = await client.post(
        "/budget/statements/upload",
        data={"account_id": SEEDED_ACCOUNT_ID},
        files={"file": ("jan.csv", b"date,amount\n2026-01-01,10.00\n", "text/csv")},
    )
    assert response.status_code == 201
    statement = response.json()
    assert statement["account_id"] == SEEDED_ACCOUNT_ID
    assert statement["filename"] == "jan.csv"
    assert statement["format"] == "csv"
    assert statement["status"] == "pending"


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
