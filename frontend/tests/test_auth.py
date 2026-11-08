"""Signing in from the frontend (#20): tokens, refresh, the route guard and the
login card.

`api_client` finds the session through `ft.context.page`, which Flet sets for
every event handler. Tests set the same context variable Flet does
(`_context_page`), so the code under test runs exactly as it would in the app.
"""

import asyncio
from types import SimpleNamespace

import flet as ft
import pytest
from flet.controls.context import _context_page
from flet.messaging.session_store import SessionStore
from test_views import find_button, stub_page, walk

import api_client
import auth
from routing import VIEW_BUILDERS


@pytest.fixture
def page():
    page = stub_page()
    page.routes = []
    page.navigate = page.routes.append
    token = _context_page.set(page)
    yield page
    _context_page.reset(token)


class _Response:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json = json_data
        self.headers = {}

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._json


class _Gateway:
    """A fake gateway that accepts exactly one access token, and rotates the
    refresh token the way the real one does - reusing a rotated one fails."""

    def __init__(self, valid_access="fresh", refresh_ok=True):
        self.valid_access = valid_access
        self.also_valid: set[str] = set()
        self.refresh_ok = refresh_ok
        self.refresh_calls = []
        self.seen_headers = []

    async def get(self, url, headers=None, **kwargs):
        self.seen_headers.append((headers or {}).get("Authorization"))
        await asyncio.sleep(0)  # let concurrent requests interleave, as real I/O would
        accepted = {f"Bearer {t}" for t in {self.valid_access, *self.also_valid}}
        if (headers or {}).get("Authorization") in accepted:
            return _Response(200, [{"id": "acc-1"}])
        return _Response(401, {"detail": "Invalid or expired token"})

    async def post(self, url, json=None, **kwargs):
        if url == "/auth/refresh":
            self.refresh_calls.append(json["refresh_token"])
            await asyncio.sleep(0)
            if self.refresh_ok and len(self.refresh_calls) == 1:
                return _Response(200, {"access_token": self.valid_access, "refresh_token": "r-2"})
            return _Response(401, {"detail": "Invalid refresh token"})
        raise AssertionError(f"unexpected POST {url}")


@pytest.fixture
def gateway(monkeypatch):
    gateway = _Gateway()
    monkeypatch.setattr(api_client, "_client", lambda: gateway)
    return gateway


def _sign_in(page, access="fresh", refresh="r-1", email="ola@example.com"):
    auth.store_tokens(page, {"access_token": access, "refresh_token": refresh}, email=email)


# --- Requests ----------------------------------------------------------------


async def test_requests_carry_the_sessions_access_token(page, gateway):
    _sign_in(page)
    assert await api_client.get_accounts() == [{"id": "acc-1"}]
    assert gateway.seen_headers == ["Bearer fresh"]


async def test_no_session_means_no_header(gateway):
    # Outside a Flet callback there is no page: the request goes out bare and
    # is refused - it never borrows anyone's token.
    assert await api_client.get_accounts() == []
    assert gateway.seen_headers == [None]


async def test_each_session_sends_its_own_token(gateway):
    # The shared client is one per event loop - in flet-web, one for every
    # browser tab. A token set on it would leak between users; per-request
    # headers cannot.
    gateway.also_valid = {"alice-token", "bob-token"}
    alice, bob = stub_page(), stub_page()
    _sign_in(alice, access="alice-token")
    _sign_in(bob, access="bob-token")

    for who in (alice, bob):
        token = _context_page.set(who)
        try:
            await api_client.get_accounts()
        finally:
            _context_page.reset(token)

    assert gateway.seen_headers == ["Bearer alice-token", "Bearer bob-token"]


async def test_an_expired_token_is_refreshed_and_the_request_retried(page, gateway):
    _sign_in(page, access="expired")

    assert await api_client.get_accounts() == [{"id": "acc-1"}]
    assert gateway.refresh_calls == ["r-1"]
    assert auth.access_token(page) == "fresh"
    assert auth.refresh_token(page) == "r-2"
    assert auth.signed_in_email(page) == "ola@example.com"  # kept across refresh


async def test_concurrent_401s_refresh_only_once(page, gateway):
    # A screen loads with asyncio.gather. If every request refreshed on its own,
    # the second would replay the refresh token the first had rotated, and the
    # server would revoke the whole session as stolen.
    _sign_in(page, access="expired")

    results = await asyncio.gather(*(api_client.get_accounts() for _ in range(5)))

    assert gateway.refresh_calls == ["r-1"]
    assert all(r == [{"id": "acc-1"}] for r in results)
    assert auth.is_signed_in(page)


async def test_a_refused_refresh_signs_out_once(page, gateway):
    gateway.refresh_ok = False
    _sign_in(page, access="expired")

    await asyncio.gather(*(api_client.get_accounts() for _ in range(3)))

    assert not auth.is_signed_in(page)
    assert page.routes == ["/login"]  # once, not once per failed request


async def test_a_401_is_not_reported_as_an_outage(page, gateway):
    gateway.refresh_ok = False
    _sign_in(page, access="expired")

    with api_client.collect_failures() as failures:
        await api_client.get_accounts()

    assert failures == []


# --- Route guard -------------------------------------------------------------


@pytest.mark.parametrize("route", [r for r in VIEW_BUILDERS if r not in auth.PUBLIC_ROUTES])
def test_signed_out_every_screen_but_login_redirects(route):
    assert auth.redirect_for(route, signed_in=False) == "/login"


@pytest.mark.parametrize("route", sorted(auth.PUBLIC_ROUTES))
def test_signed_out_the_login_screen_is_shown(route):
    assert auth.redirect_for(route, signed_in=False) is None


@pytest.mark.parametrize("route", sorted(auth.PUBLIC_ROUTES))
def test_signed_in_the_login_screen_forwards_to_the_budget(route):
    assert auth.redirect_for(route, signed_in=True) == auth.SIGNED_IN_HOME


def test_signed_in_screens_are_shown():
    assert auth.redirect_for("/envelopes", signed_in=True) is None


def test_main_consults_the_guard():
    # The guard lives in main.route_change so no screen can skip it; make sure
    # it is actually called there (test_main.py, which would drive the real app,
    # cannot run on a machine without Windows Developer Mode).
    import inspect

    import main

    assert "auth.redirect_for(" in inspect.getsource(main.main)


def test_an_empty_store_is_signed_out():
    page = SimpleNamespace(session=SimpleNamespace(store=SessionStore()))
    assert not auth.is_signed_in(page)
    assert auth.access_token(page) is None
    auth.clear(page)  # clearing nothing is fine


# --- Login card --------------------------------------------------------------


def _fields(view):
    fields = [c for c in walk(view) if isinstance(c, ft.TextField)]
    return fields[0], fields[1]


def _visible_texts(view):
    return [c.value for c in walk(view) if isinstance(c, ft.Text) and c.visible and c.value]


async def _submit(view, label="Sign in"):
    button = find_button(view, label)
    await button.on_click(SimpleNamespace(control=button))


async def test_signing_in_stores_the_session_and_opens_the_budget(page, monkeypatch):
    calls = []

    async def fake_login(email, password):
        calls.append((email, password))
        return {"access_token": "a", "refresh_token": "r", "token_type": "bearer"}

    monkeypatch.setattr("views.login.login", fake_login)
    view = await VIEW_BUILDERS["/login"](page)
    email, password = _fields(view)
    email.value, password.value = "  Ola@Example.com ", "correct horse battery"

    await _submit(view)

    assert calls == [("Ola@Example.com", "correct horse battery")]
    assert auth.access_token(page) == "a"
    assert auth.signed_in_email(page) == "ola@example.com"
    assert page.routes == ["/dashboard"]
    assert password.value == ""


async def test_creating_an_account_opens_the_setup_checklist(page, monkeypatch):
    async def fake_register(email, password):
        return {"access_token": "a", "refresh_token": "r", "token_type": "bearer"}

    monkeypatch.setattr("views.login.register", fake_register)
    view = await VIEW_BUILDERS["/login"](page)
    toggle = find_button(view, "Create an account instead")
    toggle.on_click(SimpleNamespace(control=toggle))
    email, password = _fields(view)
    email.value, password.value = "ola@example.com", "correct horse battery"

    await _submit(view, "Create account")

    assert page.routes == ["/first-run"]


@pytest.mark.parametrize(
    ("result", "message"),
    [
        ({"error": "That email and password don't match."}, "That email and password don't match."),
        (None, "Can't reach Envelo right now - check your connection and try again."),
    ],
)
async def test_a_failed_sign_in_says_why_and_stays_put(page, monkeypatch, result, message):
    async def fake_login(email, password):
        return result

    monkeypatch.setattr("views.login.login", fake_login)
    view = await VIEW_BUILDERS["/login"](page)
    email, password = _fields(view)
    email.value, password.value = "ola@example.com", "wrong password!"

    await _submit(view)

    assert message in _visible_texts(view)
    assert not auth.is_signed_in(page)
    assert page.routes == []
    assert find_button(view, "Sign in") is not None  # label restored after the attempt


async def test_empty_fields_are_caught_before_calling_the_server(page, monkeypatch):
    async def fake_login(email, password):
        raise AssertionError("should not be called")

    monkeypatch.setattr("views.login.login", fake_login)
    view = await VIEW_BUILDERS["/login"](page)

    await _submit(view)

    assert "Enter your email and password." in _visible_texts(view)


async def test_a_second_click_while_signing_in_is_ignored(page, monkeypatch):
    release = asyncio.Event()
    calls = []

    async def slow_login(email, password):
        calls.append(email)
        await release.wait()
        return {"access_token": "a", "refresh_token": "r", "token_type": "bearer"}

    monkeypatch.setattr("views.login.login", slow_login)
    view = await VIEW_BUILDERS["/login"](page)
    email, password = _fields(view)
    email.value, password.value = "ola@example.com", "correct horse battery"
    button = find_button(view, "Sign in")

    first = asyncio.ensure_future(button.on_click(SimpleNamespace(control=button)))
    await asyncio.sleep(0)
    await button.on_click(SimpleNamespace(control=button))  # double click
    release.set()
    await first

    assert calls == ["ola@example.com"]


# --- Error messages from the gateway ----------------------------------------


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (401, {"detail": "Invalid email or password"}, "That email and password don't match."),
        (409, {"detail": "Email already registered"}, "An account with this email already exists. Sign in instead."),
        (422, {"detail": [{"loc": ["body", "password"], "msg": "too short"}]}, "Use a password of at least 12 characters."),
        (422, {"detail": [{"loc": ["body", "email"], "msg": "bad"}]}, "That doesn't look like an email address."),
    ],
)
async def test_gateway_refusals_become_sentences(monkeypatch, status, body, expected):
    class _Auth:
        async def post(self, url, json=None, **kwargs):
            return _Response(status, body)

    monkeypatch.setattr(api_client, "_client", lambda: _Auth())
    assert await api_client.login("ola@example.com", "whatever-password") == {"error": expected}
