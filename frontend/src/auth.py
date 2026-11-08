"""Who is signed in, for this browser session.

Tokens live in `page.session.store` - one store per connected browser tab - and
nowhere else:

- Not on the shared `httpx.AsyncClient` in `api_client`: that client is one per
  event loop, and in flet-web every session shares the loop, so a header set on
  it would go out with *everyone's* requests.
- Not in `page.shared_preferences`: on the web that is the browser's
  localStorage, readable by any script that ever runs on the page. Signing in
  again after closing the tab is the price of not handing the refresh token -
  a 30-day credential - to an XSS.

`api_client` reads them through `current_page()`, i.e. `ft.context.page`, which
Flet sets before it runs any event handler and which tasks inherit. That avoids
threading `page` through every API function and every view that calls one -
and if it is ever missing, the request simply goes out unauthenticated and comes
back 401: a loud failure, never someone else's data.
"""

import asyncio

import flet as ft

# Routes reachable without signing in. "/" renders the login screen too.
PUBLIC_ROUTES = frozenset({"/", "/login"})
SIGNED_IN_HOME = "/dashboard"

_TOKENS_KEY = "auth.tokens"
_REFRESH_LOCK_KEY = "auth.refresh_lock"


def redirect_for(route: str, signed_in: bool) -> str | None:
    """Where `route` should send this session instead, or `None` to show it.

    Signed out, every screen but the login one sends you to it - they all read
    the API, which would answer them with nothing but 401s. Signed in, the login
    screen forwards to the budget: "/" is the bottom of every view stack, so
    without this, backing out of the dashboard would look like being signed out.
    """
    if not signed_in and route not in PUBLIC_ROUTES:
        return "/login"
    if signed_in and route in PUBLIC_ROUTES:
        return SIGNED_IN_HOME
    return None


def current_page() -> ft.Page | None:
    """The page whose event is being handled, or `None` outside a Flet callback
    (unit tests, module import)."""
    try:
        return ft.context.page
    except RuntimeError:
        return None


def _store(page):
    return page.session.store if page is not None else None


def _tokens(page) -> dict:
    store = _store(page)
    return (store.get(_TOKENS_KEY) if store is not None else None) or {}


def access_token(page) -> str | None:
    return _tokens(page).get("access_token")


def refresh_token(page) -> str | None:
    return _tokens(page).get("refresh_token")


def signed_in_email(page) -> str | None:
    return _tokens(page).get("email")


def is_signed_in(page) -> bool:
    # A refresh token is what makes a session resumable: an expired access token
    # alone is not "signed out", it is fifteen minutes old.
    return refresh_token(page) is not None


def store_tokens(page, pair: dict, email: str | None = None) -> None:
    """Keep a token pair from /auth/login, /register or /refresh. `email` is kept
    from the previous pair when not given - refresh does not repeat it."""
    store = _store(page)
    if store is None:
        return
    store.set(
        _TOKENS_KEY,
        {
            "access_token": pair["access_token"],
            "refresh_token": pair["refresh_token"],
            "email": email if email is not None else signed_in_email(page),
        },
    )


def clear(page) -> None:
    """End the session: the tokens *and* everything else in the session store.

    All of it belongs to whoever was signed in - the envelope they last opened,
    an unfinished setup checklist, a collapsed sidebar. Keeping it would hand
    it to the next person who signs in on this tab.
    """
    store = _store(page)
    if store is not None:
        store.clear()


def refresh_lock(page) -> asyncio.Lock:
    """One lock per session, so concurrent 401s refresh once between them.

    Screens fetch with `asyncio.gather`, so an expired access token makes five
    requests fail at the same moment. If each refreshed on its own, the second
    would present the refresh token the first had just rotated - which the
    server treats as a stolen token and answers by revoking the whole session.
    """
    store = _store(page)
    lock = store.get(_REFRESH_LOCK_KEY)
    if lock is None:
        lock = asyncio.Lock()
        store.set(_REFRESH_LOCK_KEY, lock)
    return lock
