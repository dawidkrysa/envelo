import api_client
import httpx


class _FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


class _FakeAsyncClient:
    def __init__(self, status_code=200, raises=None):
        self._status_code = status_code
        self._raises = raises

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def get(self, path):
        if self._raises is not None:
            raise self._raises
        return _FakeResponse(self._status_code)


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
