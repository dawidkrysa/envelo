"""Thin async wrapper over the API Gateway.

Every call returns a safe empty value on failure (`[]`, `{}`, `None`) rather than
raising: the screens are read-mostly and a failed fetch should leave the UI empty
rather than take the app down. Callers that need to tell "failed" from "nothing
there" - the write paths - check for `None` explicitly.

Read paths could not make that distinction at all, which is worse than it
sounds: with the gateway down, a screen rendered "0,00 zł" and "nothing here
yet" - not an empty state but a confident false one. `collect_failures()` fixes
that without changing a single return type; see its docstring.
"""

import asyncio
import contextvars
from contextlib import contextmanager

import httpx

import auth
from config import API_GATEWAY_URL

# Which reads failed inside the innermost `collect_failures()` block, or None
# when nobody is listening. A ContextVar rather than a module global because
# several screens can be building at once (each `page.run_task` is its own
# task) and one screen's outage must not surface on another's banner.
_failures: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar("api_failures", default=None)


@contextmanager
def collect_failures():
    """Records which reads failed inside the block, e.g.

        with collect_failures() as failures:
            envelopes, spent = await asyncio.gather(get_envelopes(), get_spent_by_envelope())
        if failures:
            ...  # say so, instead of rendering zeros as if they were the truth

    Works across `asyncio.gather`: a task copies the current context when it is
    created, so the tasks see - and append to - the very same list object this
    block installed. The block therefore has to be entered *before* the gather.

    A 404 is deliberately not a failure: the gateway answers "no rows" with 404
    on most list endpoints, so counting it would make an empty budget look like
    an outage - exactly the confusion this is meant to end.
    """
    failures: list[str] = []
    token = _failures.set(failures)
    try:
        yield failures
    finally:
        _failures.reset(token)


def _note_failure(endpoint: str, error: Exception) -> None:
    # 401 is not an outage either: it means "sign in again", and `_request` has
    # already sent the user to the login screen by the time a caller sees it.
    if isinstance(error, httpx.HTTPStatusError) and error.response.status_code in (401, 404):
        return
    bucket = _failures.get()
    if bucket is not None:
        bucket.append(endpoint)


# One client per event loop, reused across calls.
#
# Not an optimisation detail: constructing an `httpx.AsyncClient` costs ~150ms
# here (trust store and SSL context setup), while a request on an existing one
# takes ~4ms. With a fresh client per call, opening a screen that makes five
# requests spent most of a second doing nothing but building clients - and
# running them concurrently did not help, because that cost is CPU-bound and
# serialised by the GIL.
#
# Keyed by loop rather than a single module-level client because a client binds
# its connection pool to the loop it first ran on: a cached one would break the
# moment anything created a second loop, which is exactly what pytest-asyncio
# does for every test.
_clients: dict[asyncio.AbstractEventLoop, httpx.AsyncClient] = {}


def _client() -> httpx.AsyncClient:
    loop = asyncio.get_running_loop()
    client = _clients.get(loop)
    if client is None or client.is_closed:
        client = httpx.AsyncClient(base_url=API_GATEWAY_URL, timeout=5)
        _clients[loop] = client
    for dead in [key for key in _clients if key.is_closed()]:
        del _clients[dead]
    return client



async def _send(method: str, url: str, token: str | None, **kwargs) -> httpx.Response:
    if token is not None:
        kwargs["headers"] = {**kwargs.get("headers", {}), "Authorization": f"Bearer {token}"}
    return await getattr(_client(), method)(url, **kwargs)


async def _request(method: str, url: str, **kwargs) -> httpx.Response:
    """Every gateway call goes through here: it signs the request with the
    session's access token and, when that has expired, refreshes it once and
    retries.

    The header is set per request, never on the shared client - see `auth.py`
    for why. Network errors are left to propagate, so each caller's existing
    `except httpx.HTTPError` keeps deciding what an outage looks like.
    """
    page = auth.current_page()
    token = auth.access_token(page)
    response = await _send(method, url, token, **kwargs)

    if response.status_code == 401 and auth.is_signed_in(page) and await _refresh(page, token):
        response = await _send(method, url, auth.access_token(page), **kwargs)
    if response.status_code == 401 and page is not None:
        _signed_out(page)
    return response


async def _refresh(page, stale_access_token: str | None) -> bool:
    """Swap the refresh token for a new pair. True if there is a usable access
    token afterwards.

    Under the session's lock, and only if nobody else has refreshed meanwhile:
    a screen's `asyncio.gather` makes several requests hit the expired token at
    once, and a second refresh with the token the first just rotated would look
    like theft to the server, which then revokes the whole session.
    """
    async with auth.refresh_lock(page):
        current = auth.access_token(page)
        if current != stale_access_token:
            return current is not None
        refresh_token = auth.refresh_token(page)
        if refresh_token is None:
            return False
        response = await _client().post("/auth/refresh", json={"refresh_token": refresh_token})
        if response.status_code != 200:
            return False
        auth.store_tokens(page, response.json())
        return True


def _signed_out(page) -> None:
    """The session is over (refresh refused, or a fresh token still rejected):
    forget it and go to the login screen - once, however many requests noticed."""
    was_signed_in = auth.is_signed_in(page)
    auth.clear(page)
    if was_signed_in:
        try:
            page.navigate("/login")
        except Exception:
            pass


def _auth_error(response: httpx.Response) -> str:
    """A sentence for the login card, from a refused /auth/* request."""
    if response.status_code == 409:
        return "An account with this email already exists. Sign in instead."
    if response.status_code == 422:
        fields = {str(part) for error in response.json().get("detail", []) for part in error.get("loc", [])}
        if "password" in fields:
            return "Use a password of at least 12 characters."
        return "That doesn't look like an email address."
    if response.status_code == 401:
        return "That email and password don't match."
    return "Couldn't sign in - try again."


async def _sign_in(path: str, email: str, password: str) -> dict | None:
    try:
        response = await _client().post(path, json={"email": email, "password": password})
    except httpx.HTTPError:
        return None
    if response.status_code in (200, 201):
        return response.json()
    return {"error": _auth_error(response)}


# POST /auth/login
async def login(email: str, password: str) -> dict | None:
    """The token pair, `{"error": <sentence>}` if the server refused, or `None`
    if it could not be reached. Storing the pair is the caller's job."""
    return await _sign_in("/auth/login", email, password)


# POST /auth/register
async def register(email: str, password: str) -> dict | None:
    """Creates the account and signs it in - same return shape as `login`."""
    return await _sign_in("/auth/register", email, password)


# POST /auth/logout
async def logout(refresh_token: str) -> None:
    """Revoke the refresh token server-side. Best effort: signing out locally
    must not depend on the server answering."""
    try:
        await _client().post("/auth/logout", json={"refresh_token": refresh_token})
    except httpx.HTTPError:
        pass

async def get_health() -> bool:
    try:
        response = await _request("get", "/health")
        response.raise_for_status()
        return response.status_code == 200
    except httpx.HTTPError:
        return False


async def get_accounts() -> list[dict]:  # GET /budget/accounts
    try:
        response = await _request("get", "/budget/accounts")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as error:
        _note_failure("accounts", error)
        return []


# GET /budget/accounts/balances
async def get_account_balances() -> dict[str, dict]:
    """`{account_id: {balance, transaction_count, last_imported_at}}`.

    Keyed by id so a caller can look an account up directly. Summed by the
    database rather than from a fetched transaction list, which caps at 100 rows
    and would understate any account with real history.
    """
    try:
        response = await _request("get", "/budget/accounts/balances")
        response.raise_for_status()
        return {row["account_id"]: row for row in response.json()}
    except httpx.HTTPError as error:
        _note_failure("balances", error)
        return {}


# POST /budget/accounts
async def create_account(payload: dict) -> dict | None:
    try:
        response = await _request("post", "/budget/accounts", json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


# PUT /budget/accounts/{accountId}
async def update_account(account_id: str, payload: dict) -> dict | None:
    try:
        response = await _request("put", f"/budget/accounts/{account_id}", json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


# GET /budget/payees
async def get_payees() -> list[dict]:
    try:
        response = await _request("get", "/budget/payees")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as error:
        _note_failure("payees", error)
        return []


# GET /budget/envelopes
async def get_envelopes() -> list[dict]:
    try:
        response = await _request("get", "/budget/envelopes")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as error:
        _note_failure("envelopes", error)
        return []


def _transaction_params(account_id, envelope_id, category_group_id, date_from, date_to) -> dict:
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
    return params


# GET /budget/transactions/{page}
async def get_transactions_page(
    *,
    account_id=None,
    envelope_id=None,
    category_group_id=None,
    date_from=None,
    date_to=None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[dict], int]:
    """One page of transactions plus how many match in total.

    The count comes from the `X-Total-Count` header. Separate from
    `get_transactions` below - which just wants the most recent rows and has no
    use for a page number - so neither caller has to carry the other's concerns.

    `search` is passed to the server rather than applied to the returned page:
    the page is 50 rows out of possibly thousands, so filtering it here would
    answer "which of these 50 match", not "which of my transactions match".
    """
    params = {**_transaction_params(account_id, envelope_id, category_group_id, date_from, date_to)}
    if search and search.strip():
        params["q"] = search.strip()
    params["skip"] = skip
    params["limit"] = limit
    try:
        response = await _request("get", "/budget/transactions", params=params)
        response.raise_for_status()
        rows = response.json()
        return rows, int(response.headers.get("X-Total-Count", len(rows)))
    except (httpx.HTTPError, ValueError) as error:
        _note_failure("transactions", error)
        return [], 0


# GET /budget/transactions z query params
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
        response = await _request("get", "/budget/transactions", params=params)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as error:
        _note_failure("transactions", error)
        return []


# GET /budget/transactions/spent-by-envelope
async def get_spent_by_envelope(*, date_from=None, date_to=None) -> dict[str, float]:
    """Money out per envelope over a period, summed by the database.

    Returned as `{envelope_id: spent}` so callers can look up an envelope
    directly. Screens used to fetch the raw transactions and sum them in Python,
    which quietly went wrong past `GET /budget/transactions`' 100-row limit -
    with 144 transactions in a month the "Spent" column was simply incorrect.
    """
    params = {}
    if date_from is not None:
        params["dateFrom"] = date_from
    if date_to is not None:
        params["dateTo"] = date_to
    try:
        response = await _request("get", "/budget/transactions/spent-by-envelope", params=params)
        response.raise_for_status()
        return {row["envelope_id"]: float(row["spent"]) for row in response.json()}
    except httpx.HTTPError as error:
        _note_failure("spending", error)
        return {}


# POST /budget/transactions
async def create_transaction(payload: dict) -> dict | None:
    try:
        response = await _request("post", "/budget/transactions", json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


# GET /budget/payees/stats
async def get_payee_stats() -> dict[str, dict]:
    """`{payee_id: {total, transaction_count, last_transaction_date, top_envelope_id}}`.

    `total` is signed: a payee that pays you (an employer, a refund) reports a
    positive. Counted and summed by the database, because a payee with more
    history than one page of `GET /budget/transactions` would otherwise be
    reported short.
    """
    try:
        response = await _request("get", "/budget/payees/stats")
        response.raise_for_status()
        return {row["payee_id"]: row for row in response.json()}
    except httpx.HTTPError as error:
        _note_failure("payee history", error)
        return {}


# PUT /budget/payees/{payeeId}
async def update_payee(payee_id: str, payload: dict) -> dict | None:
    try:
        response = await _request("put", f"/budget/payees/{payee_id}", json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


# POST /budget/payees/merge
async def merge_payees(from_payee_id: str, into_payee_id: str) -> dict | None:
    """Folds one payee into another, moving its transactions across. Returns the
    surviving payee, or `None` on failure."""
    try:
        response = await _request("post", 
            "/budget/payees/merge",
            json={"from_payee_id": from_payee_id, "into_payee_id": into_payee_id},
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


# POST /budget/payees
async def create_payee(name: str) -> dict | None:
    try:
        response = await _request("post", "/budget/payees", json={"name": name})
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


# GET /budget/categorization-rules
async def get_categorization_rules() -> list[dict]:
    """The payee-matching rules applied on import.

    A rule is `{id, envelope_id, phrase}`: the phrase is matched against the
    payee's name, case-insensitively, longest match winning. There is no
    ordering to preserve and no "first rule wins" - a list position means
    nothing to the server.
    """
    try:
        response = await _request("get", "/budget/categorization-rules")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as error:
        _note_failure("rules", error)
        return []


# POST /budget/categorization-rules
async def create_categorization_rule(payload: dict) -> dict | None:
    try:
        response = await _request("post", "/budget/categorization-rules", json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


# PUT /budget/categorization-rules/{categorizationRuleId}
async def update_categorization_rule(rule_id: str, payload: dict) -> dict | None:
    try:
        response = await _request("put", f"/budget/categorization-rules/{rule_id}", json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


# DELETE /budget/categorization-rules/{categorizationRuleId}
async def delete_categorization_rule(rule_id: str) -> dict | None:
    try:
        response = await _request("delete", f"/budget/categorization-rules/{rule_id}")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


# GET /budget/statements
async def get_statements(account_id=None) -> list[dict]:
    """Imported bank statements, newest first is *not* guaranteed - the server
    does not sort these, so callers that care must sort on `imported_at`."""
    params = {}
    if account_id is not None:
        params["accountId"] = account_id
    try:
        response = await _request("get", "/budget/statements", params=params)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as error:
        _note_failure("statements", error)
        return []


# GET /budget/category-groups
async def get_category_groups() -> list[dict]:
    try:
        response = await _request("get", "/budget/category-groups")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as error:
        _note_failure("category groups", error)
        return []


# GET /budget/envelope-allocations
async def get_envelope_allocations(envelope_id=None) -> list[dict]:
    params = {}
    if envelope_id is not None:
        params["envelopeId"] = envelope_id
    try:
        response = await _request("get", "/budget/envelope-allocations", params=params)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as error:
        _note_failure("assigned amounts", error)
        return []


# POST /budget/envelope-allocations
async def create_envelope_allocation(payload=None) -> dict | None:
    try:
        response = await _request("post", "/budget/envelope-allocations", json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


# PUT /budget/envelope-allocations/{allocationId}
async def update_envelope_allocation(allocation_id=None, payload=None) -> dict | None:
    try:
        response = await _request("put", f"/budget/envelope-allocations/{allocation_id}", json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


# GET /budget/envelope-allocations/to-assign
async def get_to_assign() -> float:
    try:
        response = await _request("get", "/budget/envelope-allocations/to-assign")
        response.raise_for_status()
        return float(response.json()["to_assign"])
    except httpx.HTTPError as error:
        _note_failure("money to assign", error)
        return 0


# GET /budget/forecast
async def get_forecast(month=None, as_of=None) -> dict:
    """The month's projected spending, per envelope and per category group.

    Returned as the server sent it, on purpose. The projection is the server's
    to make - `method` in the response names the estimator behind it - so this
    wrapper resolves no ids and derives no figures: a client that recomputed any
    of them would silently disagree with the model the moment the model stopped
    being straight-line pacing.

    `{}` on failure, like every other read here; callers reach for keys with
    `.get()` and `collect_failures()` tells them whether empty means "no
    envelopes" or "no server".
    """
    params = {}
    if month is not None:
        params["month"] = month
    if as_of is not None:
        params["asOf"] = as_of
    try:
        response = await _request("get", "/budget/forecast", params=params)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as error:
        _note_failure("forecast", error)
        return {}


# POST /budget/envelopes
async def create_envelope(payload: dict) -> dict | None:
    try:
        response = await _request("post", "/budget/envelopes", json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


# PUT /budget/envelopes/{envelopeId}
async def update_envelope(envelope_id: str, payload: dict) -> dict | None:
    try:
        response = await _request("put", f"/budget/envelopes/{envelope_id}", json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


# POST /budget/category-groups
async def create_category_group(payload: dict) -> dict | None:
    try:
        response = await _request("post", "/budget/category-groups", json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


# POST /budget/envelope-allocations/transfer
async def transfer_envelope_allocation(payload: dict) -> list[dict] | None:
    try:
        response = await _request("post", "/budget/envelope-allocations/transfer", json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


# DELETE /budget/envelopes/{envelopeId}
async def delete_envelope(envelope_id: str) -> dict | None:
    """Returns the deleted envelope on success, `{"error": <detail>}` if the
    backend refuses with 409, or `None` for any other failure.

    Deleting no longer conflicts on transactions: the server uncategorises them
    and drops the envelope's allocations and rules (see
    `app/db/repositories/envelope.py`). The 409 branch stays because a refusal
    is still the server's to make and swallowing its reason would be worse than
    showing it."""
    try:
        response = await _request("delete", f"/budget/envelopes/{envelope_id}")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 409:
            return {"error": e.response.json().get("detail", "Couldn't delete — try again.")}
        return None
    except httpx.HTTPError:
        return None


# PUT /budget/category-groups/{categoryGroupId}
async def update_category_group(category_group_id: str, payload: dict) -> dict | None:
    try:
        response = await _request("put", f"/budget/category-groups/{category_group_id}", json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


# DELETE /budget/category-groups/{categoryGroupId}
async def delete_category_group(category_group_id: str) -> dict | None:
    """Returns the deleted group on success, `{"error": <detail>}` when the
    backend refuses with 409 (still has envelopes - see
    `app/db/repositories/category_group.py`), or `None` for any other
    failure."""
    try:
        response = await _request("delete", f"/budget/category-groups/{category_group_id}")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 409:
            return {"error": e.response.json().get("detail", "Couldn't delete — try again.")}
        return None
    except httpx.HTTPError:
        return None


# POST /budget/statements/upload
async def create_statement(account_id: str, filename: str, content: bytes) -> dict | None:
    """Uploads a bank statement. Returns the created `StatementRead` on 201 -
    including when the server accepted the upload but couldn't parse it
    (`status == "failed"`, `error_message` set - see
    app/services/statement_import.py) - `{"error": <detail>}` if the request
    itself was rejected (bad account, unsupported format, oversized file - the
    backend's `detail` already says which), or `None` on a genuine network
    failure, where there is no server response to read a reason from."""
    try:
        response = await _request("post", 
            "/budget/statements/upload",
            data={"account_id": account_id},
            files={"file": (filename, content, "text/csv")},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        return {"error": e.response.json().get("detail", "Couldn't upload — try again.")}
    except httpx.HTTPError:
        return None
