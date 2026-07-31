import httpx

from config import API_GATEWAY_URL


async def get_health() -> bool:
    try:
        async with httpx.AsyncClient(base_url=API_GATEWAY_URL, timeout=5) as client:
            response = await client.get("/health")
            response.raise_for_status()
        return response.status_code == 200
    except httpx.HTTPError:
        return False


async def get_accounts() -> list[dict]:  # GET /budget/accounts
    try:
        async with httpx.AsyncClient(base_url=API_GATEWAY_URL, timeout=5) as client:
            response = await client.get("/budget/accounts")
            response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return []


# GET /budget/payees
async def get_payees() -> list[dict]:
    try:
        async with httpx.AsyncClient(base_url=API_GATEWAY_URL, timeout=5) as client:
            response = await client.get("/budget/payees")
            response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return []


# GET /budget/envelopes
async def get_envelopes() -> list[dict]:
    try:
        async with httpx.AsyncClient(base_url=API_GATEWAY_URL, timeout=5) as client:
            response = await client.get("/budget/envelopes")
            response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return []


# GET /budget/transactions z query params
# Repo raises 404 when filters match nothing — treated as empty, same as any other HTTPError,
async def get_transactions(
    *, account_id=None, envelope_id=None, category_group_id=None, date_from=None, date_to=None
) -> list[dict]:

    params = {}
    if account_id is not None:
        params["accountId"] = account_id
    if category_group_id is not None:
        params["categoryGroupId"] = category_group_id
    if envelope_id is not None:
        params["envelopeId"] = envelope_id
    if date_from is not None:
        params["dateFrom"] = date_from
    if date_to is not None:
        params["dateTo"] = date_to

    try:
        async with httpx.AsyncClient(base_url=API_GATEWAY_URL, timeout=5) as client:
            response = await client.get("/budget/transactions", params=params)
            response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return []


async def create_transaction(payload: dict) -> dict | None:  # POST /budget/transactions
    try:
        async with httpx.AsyncClient(base_url=API_GATEWAY_URL, timeout=5) as client:
            response = await client.post("/budget/transactions", json=payload)
            response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


async def create_payee(name: str) -> dict | None:  # POST /budget/payees
    try:
        async with httpx.AsyncClient(base_url=API_GATEWAY_URL, timeout=5) as client:
            response = await client.post("/budget/payees", json={"name": name})
            response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None
