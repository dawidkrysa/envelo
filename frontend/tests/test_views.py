"""Unit tests for the view builders.

Each builder must return an ft.View for its own route without touching the
network or mutating anything - a stub stands in for the page.
"""

from types import SimpleNamespace

import flet as ft
import pytest

from routing import VIEW_BUILDERS

DEMO_ROUTES = list(VIEW_BUILDERS)

DESKTOP_WIDTH = 1280
TABLET_WIDTH = 700
MOBILE_WIDTH = 390


def stub_page(width: float | None = DESKTOP_WIDTH) -> SimpleNamespace:
    page = SimpleNamespace(
        theme_mode=ft.ThemeMode.LIGHT,
        platform_brightness=ft.Brightness.LIGHT,
        width=width,
        navigate=lambda route: None,
        update=lambda: None,
        opened_dialogs=[],
    )
    page.show_dialog = page.opened_dialogs.append
    page.pop_dialog = lambda: page.opened_dialogs.pop() if page.opened_dialogs else None
    return page


def walk(control):
    """Depth-first walk over a control tree, following controls and slots."""
    yield control
    for child in list(getattr(control, "controls", None) or []):
        yield from walk(child)
    for slot in ("content", "title", "subtitle", "trailing", "leading"):
        child = getattr(control, slot, None)
        if isinstance(child, ft.Control):
            yield from walk(child)
    for action in list(getattr(control, "actions", None) or []):
        if isinstance(action, ft.Control):
            yield from walk(action)


def find_button(root, label: str) -> ft.Container | None:
    """Our buttons are Containers wrapping a Text label, not ft.*Button."""
    for c in walk(root):
        if isinstance(c, ft.Container) and getattr(c, "on_click", None) is not None:
            text = c.content
            if isinstance(text, ft.Text) and text.value == label:
                return c
    return None


async def _empty_list(*args, **kwargs) -> list:
    return []


@pytest.fixture(autouse=True)
def stub_transactions_api(monkeypatch):
    """`/transactions` fetches real data on build - stub it so this sweep never
    touches the network, per this module's own no-network contract above. Patched
    on `views.transactions`, not `api_client`, because that view does
    `from api_client import ...`, binding its own reference at import time."""
    monkeypatch.setattr("views.transactions.get_accounts", _empty_list)
    monkeypatch.setattr("views.transactions.get_payees", _empty_list)
    monkeypatch.setattr("views.transactions.get_envelopes", _empty_list)
    monkeypatch.setattr("views.transactions.get_transactions", _empty_list)


@pytest.mark.parametrize("route", DEMO_ROUTES)
async def test_builder_returns_view_for_its_route(route):
    view = await VIEW_BUILDERS[route](stub_page())
    assert isinstance(view, ft.View)
    assert view.route == route
    assert view.controls


@pytest.mark.parametrize("route", DEMO_ROUTES)
@pytest.mark.parametrize("width", [DESKTOP_WIDTH, TABLET_WIDTH, MOBILE_WIDTH])
async def test_views_never_inherit_flet_default_view_padding(route, width):
    """ft.View defaults to 10px padding/spacing, which insets the whole shell."""
    view = await VIEW_BUILDERS[route](stub_page(width))
    assert view.padding == 0
    assert view.spacing == 0


async def test_page_width_unknown_falls_back_to_desktop():
    """page.width is None until Flet measures the first frame."""
    from theme import layout_band

    assert layout_band(None) == "desktop"
    view = await VIEW_BUILDERS["/dashboard"](stub_page(None))
    assert isinstance(view, ft.View)


@pytest.mark.parametrize(
    "band_width",
    [(DESKTOP_WIDTH, "desktop", 244), (TABLET_WIDTH, "tablet", 74)],
)
async def test_main_screens_use_a_sidebar_on_desktop_and_tablet(band_width):
    width, band, expected_width = band_width
    from components.nav_rail import build_nav
    from theme import layout_band, palette

    assert layout_band(width) == band
    page = stub_page(width)
    nav = build_nav(palette(page), band, "dashboard", lambda r: None)
    assert isinstance(nav, ft.Container)
    assert nav.width == expected_width


async def test_main_screens_use_a_bottom_bar_on_mobile():
    from components.nav_rail import build_nav
    from theme import layout_band, palette

    assert layout_band(MOBILE_WIDTH) == "mobile"
    page = stub_page(MOBILE_WIDTH)
    nav = build_nav(palette(page), "mobile", "dashboard", lambda r: None)
    assert isinstance(nav, ft.Container)
    assert nav.height == 66


@pytest.mark.parametrize(
    ("route", "label"),
    [
        ("/envelopes", "Add envelope"),
        ("/envelopes", "Move money"),
        ("/envelopes/detail", "Move money"),
        ("/envelopes/detail", "Edit envelope"),
        ("/rules", "Add rule"),
        ("/accounts", "Add account"),
        ("/transactions", "Add transaction"),
    ],
)
async def test_action_buttons_open_a_dialog(route, label):
    page = stub_page()
    view = await VIEW_BUILDERS[route](page)
    button = find_button(view, label)
    assert button is not None, f"no button labeled {label!r} on {route}"
    button.on_click(SimpleNamespace(control=button))
    assert len(page.opened_dialogs) == 1
    dialog = page.opened_dialogs[0]
    assert isinstance(dialog, ft.AlertDialog)
    # Cancel (the first action) dismisses it again.
    dialog.actions[0].on_click(None)
    assert page.opened_dialogs == []


def _dialog_field(dialog: ft.AlertDialog, label: str) -> ft.Control:
    """Same lookup as tests/test_dialogs.py's helper of the same purpose -
    finds the labeled field's TextField/Dropdown, nested one level deeper for
    a "date" field's Row(TextField, calendar-icon)."""
    for c in walk(dialog):
        if isinstance(c, ft.Column) and len(c.controls) >= 2:
            first = c.controls[0]
            if isinstance(first, ft.Text) and first.value == label.upper():
                for inner in walk(c.controls[1]):
                    if isinstance(inner, (ft.TextField, ft.Dropdown)):
                        return inner
    raise AssertionError(f"no field labeled {label!r} found in dialog")


async def test_new_payee_resolves_by_name_after_add_transaction_refresh(monkeypatch):
    """Regression test: creating a transaction with a brand-new payee used to
    still show "Unknown" in the list afterwards, because `refresh_transactions`
    re-fetched transactions but not payees, so `payees_by_id` stayed the stale
    snapshot from the initial page load and never contained the just-created
    payee's id."""
    accounts = [{"id": "acc-1", "name": "Checking", "currency": "EUR"}]
    state = {"payees": [], "transactions": []}

    async def fake_get_accounts():
        return accounts

    async def fake_get_envelopes():
        return []

    async def fake_get_payees():
        return list(state["payees"])

    async def fake_get_transactions(**kwargs):
        return list(state["transactions"])

    async def fake_create_payee(name):
        payee = {"id": "pay-new", "name": name}
        state["payees"].append(payee)
        return payee

    async def fake_create_transaction(payload):
        tx = {**payload, "id": "tx-new"}
        state["transactions"].append(tx)
        return tx

    monkeypatch.setattr("views.transactions.get_accounts", fake_get_accounts)
    monkeypatch.setattr("views.transactions.get_envelopes", fake_get_envelopes)
    monkeypatch.setattr("views.transactions.get_payees", fake_get_payees)
    monkeypatch.setattr("views.transactions.get_transactions", fake_get_transactions)
    monkeypatch.setattr("api_client.create_payee", fake_create_payee)
    monkeypatch.setattr("api_client.create_transaction", fake_create_transaction)

    page = stub_page()
    page.update = lambda: None
    view = await VIEW_BUILDERS["/transactions"](page)
    button = find_button(view, "Add transaction")
    button.on_click(SimpleNamespace(control=button))
    dialog = page.opened_dialogs[0]

    _dialog_field(dialog, "Account").value = "acc-1"
    _dialog_field(dialog, "Payee").value = "Brand New Payee"
    _dialog_field(dialog, "Amount").value = "10"
    _dialog_field(dialog, "Date").value = "2026-07-24"

    confirm = dialog.actions[1].on_click
    await confirm(SimpleNamespace(control=dialog.actions[1]))

    assert page.opened_dialogs == []
    payee_texts = [c.value for c in walk(view) if isinstance(c, ft.Text)]
    assert "Brand New Payee" in payee_texts
    assert "Unknown" not in payee_texts


async def test_login_alt_link_toggles_between_sign_in_and_register():
    view = await VIEW_BUILDERS["/login"](stub_page())
    title = next(c for c in walk(view) if isinstance(c, ft.Text) and c.value == "Welcome back")
    alt = find_button(view, "Create an account instead")
    assert alt is not None
    alt.on_click(SimpleNamespace(control=alt))
    assert title.value == "Create your account"
    alt.on_click(SimpleNamespace(control=alt))
    assert title.value == "Welcome back"


async def test_settings_threshold_slider_updates_its_own_label():
    view = await VIEW_BUILDERS["/settings"](stub_page())
    slider = next(c for c in walk(view) if isinstance(c, ft.Slider))
    label = next(c for c in walk(view) if isinstance(c, ft.Text) and c.value == "80%")
    slider.on_change(SimpleNamespace(control=SimpleNamespace(value=95)))
    assert label.value == "95%"
