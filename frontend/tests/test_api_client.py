from datetime import date

import httpx

import api_client

_ACCOUNTS = [{"id": "acc-1", "name": "ING Checking"}]
_PAYEES = [{"id": "pay-1", "name": "Albert Heijn"}]
_ENVELOPES = [{"id": "env-1", "name": "Groceries"}]
_TRANSACTIONS = [{"id": "tx-1", "amount": "-12.50"}]
_CATEGORY_GROUPS = [{"id": "cg-1", "name": "Everyday"}]
_ALLOCATIONS = [{"id": "alloc-1", "envelope_id": "env-1", "month": "2026-07-01", "assigned_amount": "100.00"}]


class _FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json_data = json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._json_data


class _FakeAsyncClient:
    def __init__(self, status_code=200, raises=None, json_data=None):
        self._status_code = status_code
        self._raises = raises
        self._json_data = json_data
        self.last_path = None
        self.last_params = None
        self.last_json = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def get(self, path, params=None):
        self.last_path = path
        self.last_params = params
        if self._raises is not None:
            raise self._raises
        return _FakeResponse(self._status_code, self._json_data)

    async def post(self, path, json=None):
        self.last_path = path
        self.last_json = json
        if self._raises is not None:
            raise self._raises
        return _FakeResponse(self._status_code, self._json_data)

    async def put(self, path, json=None):
        self.last_path = path
        self.last_json = json
        if self._raises is not None:
            raise self._raises
        return _FakeResponse(self._status_code, self._json_data)


async def test_get_health_true_when_api_gateway_returns_200(monkeypatch):
    monkeypatch.setattr(
        api_client.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(status_code=200)
    )
    assert await api_client.get_health() is True


async def test_get_health_false_when_api_gateway_returns_error_status(monkeypatch):
    monkeypatch.setattr(
        api_client.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(status_code=503)
    )
    assert await api_client.get_health() is False


async def test_get_health_false_when_request_fails(monkeypatch):
    monkeypatch.setattr(
        api_client.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(raises=httpx.ConnectError("boom")),
    )
    assert await api_client.get_health() is False


async def test_get_accounts_returns_parsed_list(monkeypatch):
    monkeypatch.setattr(
        api_client.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(status_code=200, json_data=_ACCOUNTS),
    )
    assert await api_client.get_accounts() == _ACCOUNTS


async def test_get_accounts_returns_empty_list_on_server_error(monkeypatch):
    monkeypatch.setattr(
        api_client.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(status_code=500)
    )
    assert await api_client.get_accounts() == []


async def test_get_accounts_returns_empty_list_on_connection_failure(monkeypatch):
    monkeypatch.setattr(
        api_client.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(raises=httpx.ConnectError("boom")),
    )
    assert await api_client.get_accounts() == []


async def test_get_payees_returns_parsed_list(monkeypatch):
    monkeypatch.setattr(
        api_client.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(status_code=200, json_data=_PAYEES),
    )
    assert await api_client.get_payees() == _PAYEES


async def test_get_payees_returns_empty_list_on_server_error(monkeypatch):
    monkeypatch.setattr(
        api_client.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(status_code=404)
    )
    assert await api_client.get_payees() == []


async def test_get_envelopes_returns_parsed_list(monkeypatch):
    monkeypatch.setattr(
        api_client.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(status_code=200, json_data=_ENVELOPES),
    )
    assert await api_client.get_envelopes() == _ENVELOPES


async def test_get_envelopes_returns_empty_list_on_server_error(monkeypatch):
    monkeypatch.setattr(
        api_client.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(status_code=500)
    )
    assert await api_client.get_envelopes() == []


async def test_get_transactions_returns_parsed_list(monkeypatch):
    monkeypatch.setattr(
        api_client.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(status_code=200, json_data=_TRANSACTIONS),
    )
    assert await api_client.get_transactions() == _TRANSACTIONS


async def test_get_transactions_returns_empty_list_when_filters_match_nothing(monkeypatch):
    """The repository raises 404 when a filtered query matches no rows - treated as
    an empty result, same as any other non-2xx response caught via raise_for_status()."""
    monkeypatch.setattr(
        api_client.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(status_code=404)
    )
    assert await api_client.get_transactions(account_id="acc-1") == []


async def test_get_transactions_returns_empty_list_on_server_error(monkeypatch):
    monkeypatch.setattr(
        api_client.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(status_code=500)
    )
    assert await api_client.get_transactions() == []


async def test_get_transactions_sends_no_params_when_no_filters_given(monkeypatch):
    fake_client = _FakeAsyncClient(status_code=200, json_data=[])
    monkeypatch.setattr(api_client.httpx, "AsyncClient", lambda **kwargs: fake_client)
    await api_client.get_transactions()
    assert fake_client.last_path == "/budget/transactions"
    assert fake_client.last_params == {}


async def test_get_transactions_maps_filters_to_backend_query_param_names(monkeypatch):
    fake_client = _FakeAsyncClient(status_code=200, json_data=[])
    monkeypatch.setattr(api_client.httpx, "AsyncClient", lambda **kwargs: fake_client)
    await api_client.get_transactions(
        account_id="acc-1",
        envelope_id="env-1",
        category_group_id="cg-1",
        date_from=date(2026, 7, 1),
        date_to=date(2026, 7, 31),
    )
    assert fake_client.last_params == {
        "accountId": "acc-1",
        "envelopeId": "env-1",
        "categoryGroupId": "cg-1",
        "dateFrom": date(2026, 7, 1),
        "dateTo": date(2026, 7, 31),
    }


_NEW_TRANSACTION_PAYLOAD = {
    "account_id": "acc-1",
    "envelope_id": "env-1",
    "payee_id": "pay-1",
    "amount": "-42.50",
    "currency": "EUR",
    "transaction_date": "2026-07-24",
    "categorization_source": "manual",
}


async def test_create_transaction_returns_parsed_object_on_success(monkeypatch):
    created = {**_NEW_TRANSACTION_PAYLOAD, "id": "tx-new"}
    monkeypatch.setattr(
        api_client.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(status_code=201, json_data=created),
    )
    assert await api_client.create_transaction(_NEW_TRANSACTION_PAYLOAD) == created


async def test_create_transaction_returns_none_on_conflict(monkeypatch):
    monkeypatch.setattr(
        api_client.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(status_code=409)
    )
    assert await api_client.create_transaction(_NEW_TRANSACTION_PAYLOAD) is None


async def test_create_transaction_returns_none_on_connection_failure(monkeypatch):
    monkeypatch.setattr(
        api_client.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(raises=httpx.ConnectError("boom")),
    )
    assert await api_client.create_transaction(_NEW_TRANSACTION_PAYLOAD) is None


async def test_create_transaction_posts_the_given_payload(monkeypatch):
    fake_client = _FakeAsyncClient(status_code=201, json_data={})
    monkeypatch.setattr(api_client.httpx, "AsyncClient", lambda **kwargs: fake_client)
    await api_client.create_transaction(_NEW_TRANSACTION_PAYLOAD)
    assert fake_client.last_path == "/budget/transactions"
    assert fake_client.last_json == _NEW_TRANSACTION_PAYLOAD


async def test_get_category_groups_returns_parsed_list(monkeypatch):
    monkeypatch.setattr(
        api_client.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(status_code=200, json_data=_CATEGORY_GROUPS),
    )
    assert await api_client.get_category_groups() == _CATEGORY_GROUPS


async def test_get_category_groups_returns_empty_list_on_server_error(monkeypatch):
    monkeypatch.setattr(
        api_client.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(status_code=500)
    )
    assert await api_client.get_category_groups() == []


async def test_get_envelope_allocations_returns_parsed_list(monkeypatch):
    monkeypatch.setattr(
        api_client.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(status_code=200, json_data=_ALLOCATIONS),
    )
    assert await api_client.get_envelope_allocations() == _ALLOCATIONS


async def test_get_envelope_allocations_returns_empty_list_when_none_exist(monkeypatch):
    """The repository raises 404 when no allocation exists yet (e.g. this
    envelope has never been assigned money) - treated as an empty result,
    same as any other non-2xx response caught via raise_for_status()."""
    monkeypatch.setattr(
        api_client.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(status_code=404)
    )
    assert await api_client.get_envelope_allocations(envelope_id="env-1") == []


async def test_create_envelope_allocation_returns_parsed_object_on_success(monkeypatch):
    monkeypatch.setattr(
        api_client.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(status_code=201, json_data=_ALLOCATIONS[0]),
    )
    payload = {"envelope_id": "env-1", "month": "2026-07-01", "assigned_amount": "100.00"}
    assert await api_client.create_envelope_allocation(payload) == _ALLOCATIONS[0]


async def test_create_envelope_allocation_returns_none_on_conflict(monkeypatch):
    monkeypatch.setattr(
        api_client.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(status_code=409)
    )
    payload = {"envelope_id": "env-1", "month": "2026-07-01", "assigned_amount": "100.00"}
    assert await api_client.create_envelope_allocation(payload) is None


async def test_update_envelope_allocation_sends_put_with_payload(monkeypatch):
    fake_client = _FakeAsyncClient(status_code=200, json_data=_ALLOCATIONS[0])
    monkeypatch.setattr(api_client.httpx, "AsyncClient", lambda **kwargs: fake_client)
    result = await api_client.update_envelope_allocation("alloc-1", {"assigned_amount": "120.00"})
    assert result == _ALLOCATIONS[0]
    assert fake_client.last_path == "/budget/envelope-allocations/alloc-1"
    assert fake_client.last_json == {"assigned_amount": "120.00"}


async def test_update_envelope_allocation_returns_none_on_server_error(monkeypatch):
    monkeypatch.setattr(
        api_client.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(status_code=500)
    )
    result = await api_client.update_envelope_allocation("alloc-1", {"assigned_amount": "120.00"})
    assert result is None


async def test_get_to_assign_returns_parsed_value(monkeypatch):
    monkeypatch.setattr(
        api_client.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(status_code=200, json_data={"to_assign": "137.40"}),
    )
    assert await api_client.get_to_assign() == 137.4


async def test_get_to_assign_returns_zero_on_server_error(monkeypatch):
    monkeypatch.setattr(
        api_client.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(status_code=500)
    )
    assert await api_client.get_to_assign() == 0
