"""Unit tests for the view builders.

Each builder must return an ft.View for its own route without touching the
network or mutating anything - a stub stands in for the page.
"""

import asyncio
from types import SimpleNamespace

import flet as ft
import pytest
from flet.messaging.session_store import SessionStore

import api_client
from currency import DEFAULT_CURRENCY, set_currency
from preferences import DEFAULT_ALERT_THRESHOLD, set_alert_threshold, set_dark_mode
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
        last_task=None,
    )
    page.show_dialog = page.opened_dialogs.append
    page.pop_dialog = lambda: page.opened_dialogs.pop() if page.opened_dialogs else None

    # Flet's own store, not a hand-rolled stand-in: the previous fake exposed
    # `get`/`set` directly on `page.session`, which the real `Session` does not
    # have (they live on `page.session.store`). Every test passed while both
    # "open this envelope" paths crashed in the running app. Using the real
    # class means the stub cannot drift from the API again.
    page.session = SimpleNamespace(store=SessionStore())

    def run_task(fn, *args):
        page.last_task = asyncio.ensure_future(fn(*args))
        return page.last_task

    page.run_task = run_task
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


async def _zero(*args, **kwargs) -> float:
    return 0


async def _empty_map(*args, **kwargs) -> dict:
    """`get_spent_by_envelope` returns `{envelope_id: spent}`, not a list."""
    return {}


async def _empty_page(*args, **kwargs) -> tuple[list, int]:
    """`get_transactions_page` returns one page plus the full match count."""
    return [], 0


@pytest.fixture(autouse=True)
def reset_preferences():
    """The currency and the alert threshold are module-level state (see
    `currency.py` and `preferences.py`), so a test that changes one otherwise
    hands it to whatever runs next.

    That started to matter when the threshold began driving `envelope_state()`:
    a leaked "warn me at 50%" would repaint envelopes amber in tests that never
    mention Settings, and the failure would land in whichever test happened to
    run afterwards.
    """
    yield
    set_currency(DEFAULT_CURRENCY)
    set_alert_threshold(DEFAULT_ALERT_THRESHOLD)
    set_dark_mode(False)


@pytest.fixture(autouse=True)
def stub_transactions_api(monkeypatch):
    """`/transactions` fetches real data on build - stub it so this sweep never
    touches the network, per this module's own no-network contract above. Patched
    on `views.transactions`, not `api_client`, because that view does
    `from api_client import ...`, binding its own reference at import time."""
    monkeypatch.setattr("views.transactions.get_accounts", _empty_list)
    monkeypatch.setattr("views.transactions.get_payees", _empty_list)
    monkeypatch.setattr("views.transactions.get_envelopes", _empty_list)
    monkeypatch.setattr("views.transactions.get_transactions_page", _empty_page)


@pytest.fixture(autouse=True)
def stub_envelopes_api(monkeypatch):
    """Same no-network contract as `stub_transactions_api` above, for
    `/envelopes`. The envelope-side reads come through
    `views.common.fetch_budget_snapshot()` now, so they are stubbed by
    `stub_shell_api` below rather than here."""
    monkeypatch.setattr("views.envelopes.get_to_assign", _zero)


@pytest.fixture(autouse=True)
def stub_dashboard_api(monkeypatch):
    """Same no-network contract as `stub_transactions_api` above, for `/dashboard`."""
    monkeypatch.setattr("views.dashboard.get_transactions_page", _empty_page)
    monkeypatch.setattr("views.dashboard.get_payees", _empty_list)
    monkeypatch.setattr("views.dashboard.get_to_assign", _zero)


@pytest.fixture(autouse=True)
def stub_shell_api(monkeypatch):
    """The four reads behind `common.fetch_budget_snapshot()` - the month's
    envelopes, assignments and spending, shared by every screen's nav rail.

    These were never stubbed before: the shell really did try the network in
    every test and got away with it because `api_client` turns a refused
    connection into an empty list. That is exactly the silence the Dashboard's
    offline banner now exists to break, so leaving it unstubbed would put the
    banner on screens under test."""
    monkeypatch.setattr("views.common.get_category_groups", _empty_list)
    monkeypatch.setattr("views.common.get_envelopes", _empty_list)
    monkeypatch.setattr("views.common.get_envelope_allocations", _empty_list)
    monkeypatch.setattr("views.common.get_spent_by_envelope", _empty_map)


async def _empty_forecast(*args, **kwargs) -> dict:
    """`get_forecast` hands back the server's own projection dict; `{}` is what it
    returns when the read fails, and what an unstubbed screen must not have to
    reach the network to find out."""
    return {}


@pytest.fixture(autouse=True)
def stub_forecast_api(monkeypatch):
    """Same no-network contract as `stub_transactions_api` above, for `/forecast`.
    `/alerts` needs nothing of its own - it computes from the shell's snapshot."""
    monkeypatch.setattr("views.forecast.get_forecast", _empty_forecast)


@pytest.fixture(autouse=True)
def stub_payees_api(monkeypatch):
    """Same no-network contract as `stub_transactions_api` above, for `/payees`."""
    monkeypatch.setattr("views.payees.get_payees", _empty_list)
    monkeypatch.setattr("views.payees.get_payee_stats", _empty_map)
    monkeypatch.setattr("views.payees.get_envelopes", _empty_list)


@pytest.fixture(autouse=True)
def stub_accounts_api(monkeypatch):
    """Same no-network contract as `stub_transactions_api` above, for `/accounts`."""
    monkeypatch.setattr("views.accounts.get_accounts", _empty_list)
    monkeypatch.setattr("views.accounts.get_account_balances", _empty_map)


@pytest.fixture(autouse=True)
def stub_rules_api(monkeypatch):
    """Same no-network contract as `stub_transactions_api` above, for `/rules`."""
    monkeypatch.setattr("views.rules.get_categorization_rules", _empty_list)
    monkeypatch.setattr("views.rules.get_envelopes", _empty_list)


@pytest.fixture(autouse=True)
def stub_first_run_api(monkeypatch):
    """Same no-network contract as `stub_transactions_api` above, for
    `/first-run`. Its three reads are its own: the screen has no nav rail, so it
    does not go through `views.common.fetch_budget_snapshot()`."""
    monkeypatch.setattr("views.first_run.get_accounts", _empty_list)
    monkeypatch.setattr("views.first_run.get_statements", _empty_list)
    monkeypatch.setattr("views.first_run.get_envelope_allocations", _empty_list)


_DETAIL_ENVELOPE = [{"id": "env-1", "name": "Groceries", "category_group_id": "cg-1", "target_amount": None}]


async def _one_envelope(*args, **kwargs) -> list:
    return list(_DETAIL_ENVELOPE)


@pytest.fixture(autouse=True)
def stub_envelope_detail_api(monkeypatch):
    """Same no-network contract as `stub_transactions_api` above, for
    `/envelopes/detail`. Returns one fake envelope (not an empty list) so the
    normal body renders instead of the "no envelopes yet" fallback branch -
    existing tests exercise its Move money / Edit envelope buttons."""
    monkeypatch.setattr("views.envelope_detail.get_envelopes", _one_envelope)
    monkeypatch.setattr("views.envelope_detail.get_category_groups", _empty_list)
    monkeypatch.setattr("views.envelope_detail.get_payees", _empty_list)
    monkeypatch.setattr("views.envelope_detail.get_accounts", _empty_list)
    monkeypatch.setattr("views.envelope_detail.get_envelope_allocations", _empty_list)
    monkeypatch.setattr("views.envelope_detail.get_transactions", _empty_list)
    monkeypatch.setattr("views.envelope_detail.get_spent_by_envelope", _empty_map)
    monkeypatch.setattr("views.envelope_detail.get_transactions_page", _empty_page)


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
        return list(state["transactions"]), len(state["transactions"])

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
    monkeypatch.setattr("views.transactions.get_transactions_page", fake_get_transactions)
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


async def test_envelope_list_uses_real_assigned_spent_and_flags_over_limit(monkeypatch):
    """Wiring regression test for issue #16: `assigned` must come from the
    *current month's* EnvelopeAllocation keyed by envelope_id (not the
    allocation's own id), and `spent` from summing this month's transactions
    with Decimal-as-string -> float conversion. Uses an over-limit envelope
    because its state_label directly encodes spent-assigned, so a stale or
    zeroed-out aggregation cannot pass this by accident."""
    from currency import format_money
    from utils import range_to_dates

    date_from, _ = range_to_dates("this")

    async def fake_get_envelopes():
        return [{"id": "env-1", "name": "Groceries", "category_group_id": "cg-1", "target_amount": None}]

    async def fake_get_category_groups():
        return [{"id": "cg-1", "name": "Everyday"}]

    async def fake_get_envelope_allocations(envelope_id=None):
        return [
            {
                "id": "alloc-1",
                "envelope_id": "env-1",
                "month": date_from.isoformat(),
                "assigned_amount": "50.00",
            }
        ]

    async def fake_get_spent_by_envelope(**kwargs):
        return {"env-1": 65.0}

    async def fake_get_to_assign():
        return 42.5

    monkeypatch.setattr("views.common.get_envelopes", fake_get_envelopes)
    monkeypatch.setattr("views.common.get_category_groups", fake_get_category_groups)
    monkeypatch.setattr("views.common.get_envelope_allocations", fake_get_envelope_allocations)
    monkeypatch.setattr("views.common.get_spent_by_envelope", fake_get_spent_by_envelope)
    monkeypatch.setattr("views.envelopes.get_to_assign", fake_get_to_assign)

    view = await VIEW_BUILDERS["/envelopes"](stub_page())
    texts = [c.value for c in walk(view) if isinstance(c, ft.Text)]

    assert "Groceries" in texts
    assert f"{format_money(15)} over" in texts  # spent 65 - assigned 50 -> "over" state_label
    assert format_money(42.5) in texts  # "Left to assign" stat, from get_to_assign()


async def test_ledger_keeps_assigned_monthly_while_left_carries_over(monkeypatch):
    """The heart of the rollover split. "Assigned" is an editable field that
    writes *this* month's allocation row, so it has to keep showing this month's
    amount - while "Left" counts what is really in the envelope, carry-over
    included. Rolling the two into one number would leave a field that displays
    a running total and saves a monthly one, wiping out the difference on the
    first edit."""
    from currency import format_amount_bare, format_money
    from utils import _shift_months, range_to_dates

    date_from, _ = range_to_dates("this")
    last_month = _shift_months(date_from, -1).isoformat()

    async def fake_get_envelopes():
        return [{"id": "env-1", "name": "Groceries", "category_group_id": "cg-1", "target_amount": None}]

    async def fake_get_category_groups():
        return [{"id": "cg-1", "name": "Everyday"}]

    async def fake_get_envelope_allocations(envelope_id=None):
        return [
            {"id": "a0", "envelope_id": "env-1", "month": last_month, "assigned_amount": "500.00"},
            {"id": "a1", "envelope_id": "env-1", "month": date_from.isoformat(), "assigned_amount": "100.00"},
        ]

    async def fake_get_spent_by_envelope(**kwargs):
        # 300 spent last month, 40 so far this month.
        return {"env-1": 40.0} if kwargs.get("date_from") is not None else {"env-1": 340.0}

    async def fake_get_to_assign():
        return 0.0

    monkeypatch.setattr("views.common.get_envelopes", fake_get_envelopes)
    monkeypatch.setattr("views.common.get_category_groups", fake_get_category_groups)
    monkeypatch.setattr("views.common.get_envelope_allocations", fake_get_envelope_allocations)
    monkeypatch.setattr("views.common.get_spent_by_envelope", fake_get_spent_by_envelope)
    monkeypatch.setattr("views.envelopes.get_to_assign", fake_get_to_assign)

    view = await VIEW_BUILDERS["/envelopes"](stub_page())
    texts = [c.value for c in walk(view) if isinstance(c, ft.Text)]
    fields = [c.value for c in walk(view) if isinstance(c, ft.TextField)]

    # This month's assignment, not the 600 assigned across both months.
    assert format_amount_bare(100) in fields
    # 200 carried over + 100 assigned - 40 spent.
    assert format_money(260) in texts
    # Not "over": 40 spent against 300 available is comfortably on track.
    assert not any("over" in (t or "") for t in texts)


async def test_inline_assign_edit_creates_allocation_when_none_exists_yet(monkeypatch):
    """Regression test for the allocation_by_envelope key bug from earlier
    in this session (was keyed by the allocation's own id instead of
    envelope_id) - if that regressed, this envelope would look like it
    already has an allocation and PUT would fire instead of POST."""
    calls = {"create": None, "update": None}

    async def fake_get_envelopes():
        return [{"id": "env-1", "name": "Groceries", "category_group_id": "cg-1", "target_amount": None}]

    async def fake_get_category_groups():
        return [{"id": "cg-1", "name": "Everyday"}]

    async def fake_get_envelope_allocations(envelope_id=None):
        return []

    async def fake_get_spent_by_envelope(**kwargs):
        return {}

    async def fake_get_to_assign():
        return 100.0

    async def fake_create_envelope_allocation(payload):
        calls["create"] = payload
        return {**payload, "id": "alloc-new"}

    async def fake_update_envelope_allocation(allocation_id, payload):
        calls["update"] = (allocation_id, payload)
        return {"id": allocation_id, **payload}

    monkeypatch.setattr("views.common.get_envelopes", fake_get_envelopes)
    monkeypatch.setattr("views.common.get_category_groups", fake_get_category_groups)
    monkeypatch.setattr("views.common.get_envelope_allocations", fake_get_envelope_allocations)
    monkeypatch.setattr("views.common.get_spent_by_envelope", fake_get_spent_by_envelope)
    monkeypatch.setattr("views.envelopes.get_to_assign", fake_get_to_assign)
    monkeypatch.setattr("views.envelopes.create_envelope_allocation", fake_create_envelope_allocation)
    monkeypatch.setattr("views.envelopes.update_envelope_allocation", fake_update_envelope_allocation)

    page = stub_page()
    view = await VIEW_BUILDERS["/envelopes"](page)

    field = next(c for c in walk(view) if isinstance(c, ft.TextField) and c.on_blur is not None)
    field.value = "60,00"
    field.on_blur(SimpleNamespace(control=field))
    await page.last_task

    assert calls["update"] is None
    assert calls["create"]["envelope_id"] == "env-1"
    assert calls["create"]["assigned_amount"] == "60.00"


async def test_fill_all_to_target_updates_existing_allocation(monkeypatch):
    from utils import range_to_dates

    date_from, _ = range_to_dates("this")
    calls = {"update": None, "create": None}

    async def fake_get_envelopes():
        return [{"id": "env-1", "name": "Groceries", "category_group_id": "cg-1", "target_amount": "80.00"}]

    async def fake_get_category_groups():
        return [{"id": "cg-1", "name": "Everyday"}]

    async def fake_get_envelope_allocations(envelope_id=None):
        return [{"id": "alloc-1", "envelope_id": "env-1", "month": date_from.isoformat(), "assigned_amount": "20.00"}]

    async def fake_get_spent_by_envelope(**kwargs):
        return {}

    async def fake_get_to_assign():
        return 50.0

    async def fake_update_envelope_allocation(allocation_id, payload):
        calls["update"] = (allocation_id, payload)
        return {"id": allocation_id, **payload}

    async def fake_create_envelope_allocation(payload):
        calls["create"] = payload
        return {**payload, "id": "alloc-new"}

    monkeypatch.setattr("views.common.get_envelopes", fake_get_envelopes)
    monkeypatch.setattr("views.common.get_category_groups", fake_get_category_groups)
    monkeypatch.setattr("views.common.get_envelope_allocations", fake_get_envelope_allocations)
    monkeypatch.setattr("views.common.get_spent_by_envelope", fake_get_spent_by_envelope)
    monkeypatch.setattr("views.envelopes.get_to_assign", fake_get_to_assign)
    monkeypatch.setattr("views.envelopes.update_envelope_allocation", fake_update_envelope_allocation)
    monkeypatch.setattr("views.envelopes.create_envelope_allocation", fake_create_envelope_allocation)

    page = stub_page()
    view = await VIEW_BUILDERS["/envelopes"](page)

    button = find_button(view, "Fill all to target")
    assert button is not None
    button.on_click(SimpleNamespace(control=button))
    await page.last_task

    assert calls["create"] is None
    assert calls["update"] == ("alloc-1", {"assigned_amount": "80.00"})


async def test_add_envelope_dialog_creates_and_refreshes(monkeypatch):
    calls = {"create": None}

    async def fake_get_envelopes():
        return []

    async def fake_get_category_groups():
        return [{"id": "cg-1", "name": "Everyday"}]

    async def fake_get_envelope_allocations(envelope_id=None):
        return []

    async def fake_get_spent_by_envelope(**kwargs):
        return {}

    async def fake_get_to_assign():
        return 0.0

    async def fake_create_envelope(payload):
        calls["create"] = payload
        return {**payload, "id": "env-new"}

    monkeypatch.setattr("views.common.get_envelopes", fake_get_envelopes)
    monkeypatch.setattr("views.common.get_category_groups", fake_get_category_groups)
    monkeypatch.setattr("views.common.get_envelope_allocations", fake_get_envelope_allocations)
    monkeypatch.setattr("views.common.get_spent_by_envelope", fake_get_spent_by_envelope)
    monkeypatch.setattr("views.envelopes.get_to_assign", fake_get_to_assign)
    monkeypatch.setattr("api_client.create_envelope", fake_create_envelope)

    page = stub_page()
    view = await VIEW_BUILDERS["/envelopes"](page)
    button = find_button(view, "Add envelope")
    assert button is not None
    button.on_click(SimpleNamespace(control=button))
    dialog = page.opened_dialogs[0]

    _dialog_field(dialog, "Name").value = "Pharmacy"
    _dialog_field(dialog, "Category group").value = "cg-1"

    confirm = dialog.actions[1].on_click
    await confirm(SimpleNamespace(control=dialog.actions[1]))

    assert calls["create"] == {"category_group_id": "cg-1", "name": "Pharmacy", "target_amount": None}
    assert page.opened_dialogs == []


async def test_move_money_dialog_transfers_and_refreshes(monkeypatch):
    calls = {"transfer": None}

    async def fake_get_envelopes():
        return [
            {"id": "env-1", "name": "Groceries", "category_group_id": "cg-1", "target_amount": None},
            {"id": "env-2", "name": "Fun", "category_group_id": "cg-1", "target_amount": None},
        ]

    async def fake_get_category_groups():
        return [{"id": "cg-1", "name": "Everyday"}]

    async def fake_get_envelope_allocations(envelope_id=None):
        return []

    async def fake_get_spent_by_envelope(**kwargs):
        return {}

    async def fake_get_to_assign():
        return 0.0

    async def fake_transfer(payload):
        calls["transfer"] = payload
        return [{"id": "a1", **payload}, {"id": "a2", **payload}]

    monkeypatch.setattr("views.common.get_envelopes", fake_get_envelopes)
    monkeypatch.setattr("views.common.get_category_groups", fake_get_category_groups)
    monkeypatch.setattr("views.common.get_envelope_allocations", fake_get_envelope_allocations)
    monkeypatch.setattr("views.common.get_spent_by_envelope", fake_get_spent_by_envelope)
    monkeypatch.setattr("views.envelopes.get_to_assign", fake_get_to_assign)
    monkeypatch.setattr("api_client.transfer_envelope_allocation", fake_transfer)

    page = stub_page()
    view = await VIEW_BUILDERS["/envelopes"](page)
    button = find_button(view, "Move money")
    assert button is not None
    button.on_click(SimpleNamespace(control=button))
    dialog = page.opened_dialogs[0]

    _dialog_field(dialog, "From").value = "env-1"
    _dialog_field(dialog, "To").value = "env-2"
    _dialog_field(dialog, "Amount").value = "40,00"

    confirm = dialog.actions[1].on_click
    await confirm(SimpleNamespace(control=dialog.actions[1]))

    assert calls["transfer"]["from_envelope_id"] == "env-1"
    assert calls["transfer"]["to_envelope_id"] == "env-2"
    assert calls["transfer"]["amount"] == "40.00"
    assert page.opened_dialogs == []


async def test_assign_money_dialog_sets_absolute_amount(monkeypatch):
    """`assign_dialog` sets an absolute value, same as every other
    assign-amount action on this screen - typing an amount replaces
    whatever was already assigned, it doesn't add to it."""
    from utils import range_to_dates

    date_from, _ = range_to_dates("this")
    calls = {"update": None, "create": None}

    async def fake_get_envelopes():
        return [{"id": "env-1", "name": "Groceries", "category_group_id": "cg-1", "target_amount": None}]

    async def fake_get_category_groups():
        return [{"id": "cg-1", "name": "Everyday"}]

    async def fake_get_envelope_allocations(envelope_id=None):
        return [{"id": "alloc-1", "envelope_id": "env-1", "month": date_from.isoformat(), "assigned_amount": "20.00"}]

    async def fake_get_spent_by_envelope(**kwargs):
        return {}

    async def fake_get_to_assign():
        return 100.0

    async def fake_update_envelope_allocation(allocation_id, payload):
        calls["update"] = (allocation_id, payload)
        return {"id": allocation_id, **payload}

    async def fake_create_envelope_allocation(payload):
        calls["create"] = payload
        return {**payload, "id": "alloc-new"}

    monkeypatch.setattr("views.common.get_envelopes", fake_get_envelopes)
    monkeypatch.setattr("views.common.get_category_groups", fake_get_category_groups)
    monkeypatch.setattr("views.common.get_envelope_allocations", fake_get_envelope_allocations)
    monkeypatch.setattr("views.common.get_spent_by_envelope", fake_get_spent_by_envelope)
    monkeypatch.setattr("views.envelopes.get_to_assign", fake_get_to_assign)
    monkeypatch.setattr("views.envelopes.update_envelope_allocation", fake_update_envelope_allocation)
    monkeypatch.setattr("views.envelopes.create_envelope_allocation", fake_create_envelope_allocation)

    page = stub_page()
    view = await VIEW_BUILDERS["/envelopes"](page)

    def _has_label(control, label):
        return any(isinstance(c, ft.Text) and c.value == label for c in walk(control))

    stat_container = next(
        c
        for c in walk(view)
        if isinstance(c, ft.Container) and c.on_click is not None and _has_label(c, "LEFT TO ASSIGN")
    )
    stat_container.on_click(SimpleNamespace(control=stat_container))
    dialog = page.opened_dialogs[0]

    _dialog_field(dialog, "Envelope").value = "env-1"
    _dialog_field(dialog, "Amount to assign").value = "30,00"

    confirm = dialog.actions[1].on_click
    await confirm(SimpleNamespace(control=dialog.actions[1]))

    assert calls["create"] is None
    assert calls["update"] == ("alloc-1", {"assigned_amount": "30.00"})


async def test_clicking_an_envelope_navigates_to_its_own_detail_page(monkeypatch):
    """Regression test for the bug this fixes: every envelope's detail link
    used to lead to the same hardcoded mock envelope regardless of which one
    was clicked, because routing had no way to carry an id across the
    navigate() call."""
    envelopes_data = [
        {"id": "env-1", "name": "Groceries", "category_group_id": "cg-1", "target_amount": None},
        {"id": "env-2", "name": "Fun money", "category_group_id": "cg-1", "target_amount": None},
    ]

    async def fake_get_envelopes():
        return envelopes_data

    async def fake_get_category_groups():
        return [{"id": "cg-1", "name": "Everyday"}]

    async def fake_get_envelope_allocations(envelope_id=None):
        return []

    async def fake_get_spent_by_envelope(**kwargs):
        return {}

    async def fake_get_to_assign():
        return 0.0

    async def fake_get_payees():
        return []

    async def fake_get_accounts():
        return []

    monkeypatch.setattr("views.common.get_envelopes", fake_get_envelopes)
    monkeypatch.setattr("views.common.get_category_groups", fake_get_category_groups)
    monkeypatch.setattr("views.common.get_envelope_allocations", fake_get_envelope_allocations)
    monkeypatch.setattr("views.common.get_spent_by_envelope", fake_get_spent_by_envelope)
    monkeypatch.setattr("views.envelopes.get_to_assign", fake_get_to_assign)
    monkeypatch.setattr("views.envelope_detail.get_envelopes", fake_get_envelopes)
    monkeypatch.setattr("views.envelope_detail.get_category_groups", fake_get_category_groups)
    monkeypatch.setattr("views.envelope_detail.get_payees", fake_get_payees)
    monkeypatch.setattr("views.envelope_detail.get_accounts", fake_get_accounts)
    monkeypatch.setattr("views.envelope_detail.get_envelope_allocations", fake_get_envelope_allocations)
    # The detail screen still lists transactions, it just no longer sums them.
    monkeypatch.setattr("views.envelope_detail.get_transactions", _empty_list)
    monkeypatch.setattr("views.envelope_detail.get_spent_by_envelope", fake_get_spent_by_envelope)

    page = stub_page()
    list_view = await VIEW_BUILDERS["/envelopes"](page)

    row = find_button(list_view, "Fun money")
    assert row is not None
    row.on_click(SimpleNamespace(control=row))
    assert page.session.store.get("selected_envelope_id") == "env-2"

    detail_view = await VIEW_BUILDERS["/envelopes/detail"](page)
    title_texts = [c.value for c in walk(detail_view) if isinstance(c, ft.Text)]
    assert "Fun money" in title_texts
    assert "Groceries" not in title_texts


async def test_add_category_group_dialog_creates_with_next_sort_order(monkeypatch):
    calls = {"create": None}

    async def fake_get_envelopes():
        return []

    async def fake_get_category_groups():
        return [{"id": "cg-1", "name": "Everyday"}, {"id": "cg-2", "name": "Fixed costs"}]

    async def fake_get_envelope_allocations(envelope_id=None):
        return []

    async def fake_get_spent_by_envelope(**kwargs):
        return {}

    async def fake_get_to_assign():
        return 0.0

    async def fake_create_category_group(payload):
        calls["create"] = payload
        return {**payload, "id": "cg-new"}

    monkeypatch.setattr("views.common.get_envelopes", fake_get_envelopes)
    monkeypatch.setattr("views.common.get_category_groups", fake_get_category_groups)
    monkeypatch.setattr("views.common.get_envelope_allocations", fake_get_envelope_allocations)
    monkeypatch.setattr("views.common.get_spent_by_envelope", fake_get_spent_by_envelope)
    monkeypatch.setattr("views.envelopes.get_to_assign", fake_get_to_assign)
    monkeypatch.setattr("api_client.create_category_group", fake_create_category_group)

    page = stub_page()
    view = await VIEW_BUILDERS["/envelopes"](page)

    button = find_button(view, "+ Add category group")
    assert button is not None
    button.on_click(SimpleNamespace(control=button))
    dialog = page.opened_dialogs[0]

    _dialog_field(dialog, "Group name").value = "Household"
    confirm = dialog.actions[1].on_click
    await confirm(SimpleNamespace(control=dialog.actions[1]))

    assert calls["create"] == {"name": "Household", "sort_order": 2}
    assert page.opened_dialogs == []


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


# --- Envelopes: drag & drop between groups, inline amount editing -----------
#
# These cover the four failures reported against the Envelopes screen: an
# envelope could not be moved between category groups at all, and the inline
# Assigned field looked dead (zero was discarded, a stray keystroke was silently
# swallowed, and every blur rebuilt the table under the user's cursor).


def _stub_envelopes_api(monkeypatch, *, envelopes, category_groups, allocations=(), spent=None, to_assign=100.0):
    """Point every API call `views/envelopes.py` makes at in-memory data and
    record the writes. Returns the recorder."""
    calls: dict = {"create": None, "update": None, "envelope": None}

    async def fake_get_envelopes():
        return list(envelopes)

    async def fake_get_category_groups():
        return list(category_groups)

    async def fake_get_envelope_allocations(envelope_id=None):
        return list(allocations)

    async def fake_get_spent_by_envelope(**kwargs):
        return dict(spent or {})

    async def fake_get_to_assign():
        return to_assign

    async def fake_create_envelope_allocation(payload):
        calls["create"] = payload
        return {**payload, "id": "alloc-new"}

    async def fake_update_envelope_allocation(allocation_id, payload):
        calls["update"] = (allocation_id, payload)
        return {"id": allocation_id, **payload}

    async def fake_update_envelope(envelope_id, payload):
        calls["envelope"] = (envelope_id, payload)
        return {"id": envelope_id, **payload}

    # The reads live on `views.common` (the screen gets them through
    # `fetch_budget_snapshot()`, shared with the nav rail); the writes are still
    # `views/envelopes.py`'s own.
    for module, name, fake in [
        ("common", "get_envelopes", fake_get_envelopes),
        ("common", "get_category_groups", fake_get_category_groups),
        ("common", "get_envelope_allocations", fake_get_envelope_allocations),
        ("common", "get_spent_by_envelope", fake_get_spent_by_envelope),
        ("envelopes", "get_to_assign", fake_get_to_assign),
        ("envelopes", "create_envelope_allocation", fake_create_envelope_allocation),
        ("envelopes", "update_envelope_allocation", fake_update_envelope_allocation),
        ("envelopes", "update_envelope", fake_update_envelope),
    ]:
        monkeypatch.setattr(f"views.{module}.{name}", fake)
    return calls


def _two_groups(monkeypatch, **kwargs):
    return _stub_envelopes_api(
        monkeypatch,
        envelopes=[{"id": "env-1", "name": "Groceries", "category_group_id": "cg-1", "target_amount": None}],
        category_groups=[{"id": "cg-1", "name": "Everyday"}, {"id": "cg-2", "name": "Fun"}],
        **kwargs,
    )


def _drop_target_for(view, group_name: str) -> ft.DragTarget:
    """The group section that accepts dropped envelopes, found by the group name
    rendered inside it - safer than indexing into the rendered order."""
    for control in walk(view):
        if isinstance(control, ft.DragTarget):
            texts = [c.value for c in walk(control) if isinstance(c, ft.Text)]
            if any(group_name in (t or "") for t in texts):
                return control
    raise AssertionError(f"no drop target for group {group_name!r}")


def _assign_field(view) -> ft.TextField:
    return next(c for c in walk(view) if isinstance(c, ft.TextField) and c.on_blur is not None)


async def test_dropping_an_envelope_on_another_group_reassigns_it(monkeypatch):
    calls = _two_groups(monkeypatch)
    page = stub_page()
    view = await VIEW_BUILDERS["/envelopes"](page)

    target = _drop_target_for(view, "Fun")
    target.on_accept(SimpleNamespace(src=SimpleNamespace(data="env-1")))
    await page.last_task

    assert calls["envelope"] == ("env-1", {"category_group_id": "cg-2"})


async def test_dropping_an_envelope_back_on_its_own_group_writes_nothing(monkeypatch):
    calls = _two_groups(monkeypatch)
    page = stub_page()
    view = await VIEW_BUILDERS["/envelopes"](page)

    _drop_target_for(view, "Everyday").on_accept(SimpleNamespace(src=SimpleNamespace(data="env-1")))

    assert calls["envelope"] is None
    assert page.last_task is None


async def test_deleting_an_envelope_warns_what_happens_to_its_transactions(monkeypatch):
    """Deleting is allowed even when the envelope has history - the server
    uncategorises those transactions rather than refusing - so the confirmation
    has to say so before the user commits to it, not after."""

    async def fake_page(**kwargs):
        return [], 12

    monkeypatch.setattr("views.envelope_detail.get_transactions_page", fake_page)

    page = stub_page()
    view = await VIEW_BUILDERS["/envelopes/detail"](page)

    button = find_button(view, "Delete envelope")
    assert button is not None
    button.on_click(SimpleNamespace(control=button))

    dialog = page.opened_dialogs[0]
    texts = " ".join(c.value or "" for c in walk(dialog) if isinstance(c, ft.Text))
    assert "12 transactions" in texts
    assert "uncategorised" in texts
    assert "to assign" in texts


async def test_delete_confirmation_stays_plain_for_an_untouched_envelope(monkeypatch):
    """Nothing to warn about when the envelope has no transactions."""
    page = stub_page()
    view = await VIEW_BUILDERS["/envelopes/detail"](page)

    button = find_button(view, "Delete envelope")
    button.on_click(SimpleNamespace(control=button))

    dialog = page.opened_dialogs[0]
    texts = " ".join(c.value or "" for c in walk(dialog) if isinstance(c, ft.Text))
    assert "uncategorised" not in texts
    assert "can't be undone" in texts


async def test_hovering_a_group_outlines_it_without_tinting_its_envelopes(monkeypatch):
    """The drop zone used to be filled with `ok_fill`, which tinted every row in
    the group green - it read as "all of these are selected" while only the one
    under the cursor was moving. An outline makes the same promise about where
    the envelope lands without saying anything about the rows."""
    _two_groups(monkeypatch)
    page = stub_page()
    view = await VIEW_BUILDERS["/envelopes"](page)

    target = _drop_target_for(view, "Fun")
    target.on_will_accept(SimpleNamespace(src=SimpleNamespace(data="env-1")))

    holder = target.content
    assert holder.bgcolor is None, "the group must not be filled"
    assert holder.border is not None
    assert holder.border.top.color != "transparent"


async def test_hovering_an_envelopes_own_group_does_not_light_up(monkeypatch):
    """Dropping back where it already is is a documented no-op, so promising a
    move there is a lie the highlight should not tell."""
    _two_groups(monkeypatch)
    page = stub_page()
    view = await VIEW_BUILDERS["/envelopes"](page)

    target = _drop_target_for(view, "Everyday")  # env-1 already lives in cg-1
    target.on_will_accept(SimpleNamespace(src=SimpleNamespace(data="env-1")))

    assert target.content.border.top.color == "transparent"


async def test_every_ledger_row_offers_a_drag_handle(monkeypatch):
    """The handle is the drag source, not the row: a Draggable around the row
    would fight the assign/target text fields for the same gesture."""
    _two_groups(monkeypatch)
    view = await VIEW_BUILDERS["/envelopes"](stub_page())

    draggables = [c for c in walk(view) if isinstance(c, ft.Draggable)]
    assert [d.data for d in draggables] == ["env-1"]
    assert not any(isinstance(c, ft.TextField) for d in draggables for c in walk(d))


async def test_inline_assign_edit_accepts_zero(monkeypatch):
    """Typing 0 is how an envelope is un-assigned. It used to be dropped by
    `parse_amount`, which is what "changing Assigned does nothing" meant."""
    from utils import range_to_dates

    month = range_to_dates("this")[0].isoformat()
    calls = _two_groups(
        monkeypatch,
        allocations=[{"id": "alloc-1", "envelope_id": "env-1", "month": month, "assigned_amount": "50.00"}],
    )
    page = stub_page()
    view = await VIEW_BUILDERS["/envelopes"](page)

    field = _assign_field(view)
    field.value = "0"
    field.on_blur(SimpleNamespace(control=field))
    await page.last_task

    assert calls["update"] == ("alloc-1", {"assigned_amount": "0.00"})


async def test_inline_assign_edit_skips_an_unchanged_value(monkeypatch):
    """Tabbing through the ledger without editing anything used to fire a write
    plus a full re-fetch per field."""
    calls = _two_groups(monkeypatch)
    page = stub_page()
    view = await VIEW_BUILDERS["/envelopes"](page)

    field = _assign_field(view)
    field.on_blur(SimpleNamespace(control=field))  # value untouched

    assert calls["create"] is None
    assert calls["update"] is None
    assert page.last_task is None


async def test_inline_assign_edit_restores_the_stored_value_on_garbage(monkeypatch):
    calls = _two_groups(monkeypatch)
    page = stub_page()
    view = await VIEW_BUILDERS["/envelopes"](page)

    field = _assign_field(view)
    field.value = "not a number"
    field.on_blur(SimpleNamespace(control=field))

    assert calls["create"] is None
    assert field.value == "0,00"


async def test_inline_assign_edit_keeps_the_text_fields_alive(monkeypatch):
    """The regression behind "editing two envelopes in a row does nothing": the
    old code re-fetched and rebuilt the whole tab on every blur, replacing the
    field the user had just tabbed into - and with it their focus and keystrokes.
    The fields must be the *same objects* after a save."""
    _two_groups(monkeypatch)
    page = stub_page()
    view = await VIEW_BUILDERS["/envelopes"](page)

    before = [id(c) for c in walk(view) if isinstance(c, ft.TextField)]
    field = _assign_field(view)
    field.value = "60,00"
    field.on_blur(SimpleNamespace(control=field))
    await page.last_task

    after = [id(c) for c in walk(view) if isinstance(c, ft.TextField)]
    assert before == after


async def test_inline_assign_edit_updates_the_row_totals_in_place(monkeypatch):
    """...but everything derived from the amount still has to catch up."""
    from currency import format_money

    _two_groups(monkeypatch)
    page = stub_page()
    view = await VIEW_BUILDERS["/envelopes"](page)

    field = _assign_field(view)
    field.value = "60,00"
    field.on_blur(SimpleNamespace(control=field))
    await page.last_task

    texts = [c.value for c in walk(view) if isinstance(c, ft.Text)]
    assert format_money(60) in texts  # LEFT column: assigned 60 - spent 0


# --- Settings: the currency selector actually does something ----------------


def _currency_dropdown(view) -> ft.Dropdown:
    return next(
        c
        for c in walk(view)
        if isinstance(c, ft.Dropdown) and any(o.key == "pln" for o in (c.options or []))
    )


async def test_currency_selector_switches_and_persists(monkeypatch):
    """It used to render its default value and be wired to nothing at all."""
    from currency import CURRENCY_STORAGE_KEY, current_currency

    stored: dict = {}
    rebuilt: list = []

    page = stub_page()
    page.shared_preferences = SimpleNamespace(
        set=lambda key, value: _async_return(stored.__setitem__(key, value) or True),
        get=lambda key: _async_return(stored.get(key)),
    )

    async def on_route_change(e):
        rebuilt.append(e)

    page.on_route_change = on_route_change

    view = await VIEW_BUILDERS["/settings"](page)
    dropdown = _currency_dropdown(view)
    assert dropdown.value == current_currency() == "pln"

    await dropdown.on_select(SimpleNamespace(control=SimpleNamespace(value="usd")))

    assert current_currency() == "usd"
    assert stored == {CURRENCY_STORAGE_KEY: "usd"}
    # Amounts are formatted once at build time, so the route has to be rebuilt
    # for the change to reach anything already on screen.
    assert len(rebuilt) == 1


async def test_currency_options_are_offered_in_the_currency_registry_order():
    view = await VIEW_BUILDERS["/settings"](stub_page())
    from currency import CURRENCIES

    assert [o.key for o in _currency_dropdown(view).options] == list(CURRENCIES)


async def test_saved_currency_is_restored_before_anything_renders():
    """`main()` has to apply it before the first route change - every screen bakes
    its formatted amounts in at build time."""
    from currency import CURRENCY_STORAGE_KEY, current_currency
    from main import _restore_preferences

    page = SimpleNamespace(shared_preferences=SimpleNamespace(get=lambda key: _async_return("gbp")))
    await _restore_preferences(page)
    assert current_currency() == "gbp"
    assert CURRENCY_STORAGE_KEY  # the key both sides share


async def test_unreadable_currency_preference_does_not_block_startup():
    from currency import current_currency
    from main import _restore_preferences

    set_currency("usd")

    async def boom(key):
        raise RuntimeError("shared preferences unavailable")

    await _restore_preferences(SimpleNamespace(shared_preferences=SimpleNamespace(get=boom)))
    assert current_currency() == DEFAULT_CURRENCY


def _async_return(value):
    async def coro():
        return value

    return coro()


async def test_inline_assign_edit_sees_its_own_previous_edit(monkeypatch):
    """The dirty check has to read the stored amount at event time. An inline
    edit deliberately does not rebuild the row, so a value captured when the row
    was built goes stale after the first save - and editing back to the amount
    the field originally showed would then be silently dropped."""
    from utils import range_to_dates

    month = range_to_dates("this")[0].isoformat()
    calls = _two_groups(
        monkeypatch,
        allocations=[{"id": "alloc-1", "envelope_id": "env-1", "month": month, "assigned_amount": "100.00"}],
    )
    page = stub_page()
    view = await VIEW_BUILDERS["/envelopes"](page)

    field = _assign_field(view)
    field.value = "60,00"
    field.on_blur(SimpleNamespace(control=field))
    await page.last_task
    assert calls["update"] == ("alloc-1", {"assigned_amount": "60.00"})

    # Back to the original amount: still a change as far as the server knows.
    calls["update"] = None
    field.value = "100,00"
    field.on_blur(SimpleNamespace(control=field))
    await page.last_task
    assert calls["update"] == ("alloc-1", {"assigned_amount": "100.00"})


async def test_inline_assign_edit_canonicalises_what_you_typed(monkeypatch):
    """`60` is the same amount as `60,00` - no write, but the column should not
    be left ragged either."""
    from utils import range_to_dates

    month = range_to_dates("this")[0].isoformat()
    calls = _two_groups(
        monkeypatch,
        allocations=[{"id": "alloc-1", "envelope_id": "env-1", "month": month, "assigned_amount": "60.00"}],
    )
    page = stub_page()
    view = await VIEW_BUILDERS["/envelopes"](page)

    field = _assign_field(view)
    field.value = "60"
    field.on_blur(SimpleNamespace(control=field))

    assert calls["update"] is None
    assert field.value == "60,00"


async def test_sort_dropdown_keeps_showing_the_selected_mode(monkeypatch):
    """Changing the sort re-renders the toolbar, so the dropdown's value has to
    come from the screen's state. Hardcoding it meant the sort was applied but
    the control snapped back to "group order"."""
    _two_groups(monkeypatch)
    view = await VIEW_BUILDERS["/envelopes"](stub_page())

    dropdown = next(
        c for c in walk(view) if isinstance(c, ft.Dropdown) and any(o.key == "used" for o in (c.options or []))
    )
    dropdown.on_select(SimpleNamespace(control=SimpleNamespace(value="used")))

    rebuilt = next(
        c for c in walk(view) if isinstance(c, ft.Dropdown) and any(o.key == "used" for o in (c.options or []))
    )
    assert rebuilt.value == "used"


async def test_toolbar_controls_share_one_height(monkeypatch):
    """A Material dropdown will not render below 48px however small `height` is,
    so the button beside it has to name the same number or they never line up."""
    _two_groups(monkeypatch)
    view = await VIEW_BUILDERS["/envelopes"](stub_page())

    button = find_button(view, "Needs attention only")
    dropdown = next(
        c for c in walk(view) if isinstance(c, ft.Dropdown) and any(o.key == "used" for o in (c.options or []))
    )
    assert button is not None
    assert button.height == dropdown.height >= 48


@pytest.mark.parametrize("route", ["/transactions", "/envelopes"])
async def test_filter_rows_keep_selects_and_inputs_on_one_height(route):
    """Material will not draw a dropdown below 48px however small a height it is
    given, so anything standing next to one has to name `theme.CONTROL_HEIGHT`
    too - otherwise the row silently sits on two baselines."""
    from theme import CONTROL_HEIGHT

    view = await VIEW_BUILDERS[route](stub_page())
    heights = {
        c.height
        for c in walk(view)
        if isinstance(c, ft.Dropdown) or (isinstance(c, ft.TextField) and c.on_blur is None)
    }
    assert heights <= {CONTROL_HEIGHT}


async def test_dialog_fields_are_all_the_same_size():
    """A dialog mixing selects and text inputs (Add transaction has both, plus a
    date field) should read as one stack of identically sized fields."""
    from theme import CONTROL_HEIGHT

    page = stub_page()
    view = await VIEW_BUILDERS["/transactions"](page)
    button = find_button(view, "Add transaction")
    button.on_click(SimpleNamespace(control=button))
    dialog = page.opened_dialogs[0]

    fields = [c for c in walk(dialog) if isinstance(c, (ft.Dropdown, ft.TextField))]
    assert fields
    assert {c.height for c in fields} == {CONTROL_HEIGHT}


# --- Dashboard: real data, no mocks ----------------------------------------


def _stub_dashboard(
    monkeypatch,
    *,
    envelopes,
    allocations=(),
    transactions=(),
    payees=(),
    spent=None,
    spent_this_month=None,
    to_assign=0.0,
    category_groups=(),
    page_calls=None,
):
    """The envelope-side reads are patched on `views.common`, not
    `views.dashboard`: the screen gets them through
    `common.fetch_budget_snapshot()`, which it shares with the nav rail so the
    two don't fetch the same month twice.

    `transactions` is what the *server* would return for the latest-rows page -
    already ordered newest-first - because the screen no longer re-sorts it.
    Pass `page_calls` a list to capture the kwargs it was asked for.

    `spent` is the cumulative figure (everything up to the end of this month);
    `spent_this_month` is the narrower one, and defaults to `spent` for the
    common case where a test only has this month's data. The snapshot asks for
    both and tells them apart by whether `date_from` was given.
    """

    async def _envelopes():
        return list(envelopes)

    async def _allocations(envelope_id=None):
        return list(allocations)

    async def _groups():
        return list(category_groups)

    async def _transactions_page(**kwargs):
        if page_calls is not None:
            page_calls.append(kwargs)
        rows = list(transactions)
        return rows[: kwargs.get("limit", len(rows))], len(rows)

    async def _payees():
        return list(payees)

    async def _spent(**kwargs):
        if kwargs.get("date_from") is None:
            return dict(spent or {})
        return dict(spent or {} if spent_this_month is None else spent_this_month)

    async def _to_assign():
        return to_assign

    monkeypatch.setattr("views.common.get_spent_by_envelope", _spent)
    monkeypatch.setattr("views.common.get_envelopes", _envelopes)
    monkeypatch.setattr("views.common.get_envelope_allocations", _allocations)
    monkeypatch.setattr("views.common.get_category_groups", _groups)
    monkeypatch.setattr("views.dashboard.get_transactions_page", _transactions_page)
    monkeypatch.setattr("views.dashboard.get_payees", _payees)
    monkeypatch.setattr("views.dashboard.get_to_assign", _to_assign)


def _this_month(day: int = 5) -> str:
    from utils import range_to_dates

    return range_to_dates("this")[0].replace(day=day).isoformat()


async def test_dashboard_safe_to_spend_sums_real_envelopes_and_to_assign(monkeypatch):
    """Was `sum(...) - 750 + POOL` over the static mock. The 750 approximated
    "rent and savings are set aside", which nothing in the data model expresses."""
    from currency import format_money

    month = _this_month(1)
    _stub_dashboard(
        monkeypatch,
        envelopes=[
            {"id": "env-1", "name": "Groceries", "category_group_id": "cg-1", "target_amount": None},
            {"id": "env-2", "name": "Rent", "category_group_id": "cg-1", "target_amount": None},
        ],
        allocations=[
            {"id": "a1", "envelope_id": "env-1", "month": month, "assigned_amount": "100.00"},
            {"id": "a2", "envelope_id": "env-2", "month": month, "assigned_amount": "200.00"},
        ],
        transactions=[
            {
                "id": "t1",
                "envelope_id": "env-1",
                "payee_id": "p1",
                "account_id": "acc-1",
                "amount": "-30.00",
                "transaction_date": month,
                "categorization_source": "rule",
            }
        ],
        payees=[{"id": "p1", "name": "Biedronka"}],
        spent={"env-1": 30.0},
        to_assign=25.0,
    )

    view = await VIEW_BUILDERS["/dashboard"](stub_page())
    texts = [c.value for c in walk(view) if isinstance(c, ft.Text)]
    # (100 - 30) + 200 still in envelopes, + 25 not yet assigned.
    assert format_money(295) in texts


async def test_dashboard_overspent_envelope_does_not_offset_safe_to_spend(monkeypatch):
    """An overspent envelope contributes 0, not a negative: netting it off would
    hide the overspend inside a single reassuring number."""
    from currency import format_money

    month = _this_month(1)
    _stub_dashboard(
        monkeypatch,
        envelopes=[
            {"id": "env-1", "name": "Groceries", "category_group_id": "cg-1", "target_amount": None},
            {"id": "env-2", "name": "Fun", "category_group_id": "cg-1", "target_amount": None},
        ],
        allocations=[
            {"id": "a1", "envelope_id": "env-1", "month": month, "assigned_amount": "100.00"},
            {"id": "a2", "envelope_id": "env-2", "month": month, "assigned_amount": "10.00"},
        ],
        transactions=[
            {
                "id": "t1",
                "envelope_id": "env-2",
                "payee_id": "p1",
                "account_id": "a",
                "amount": "-60.00",
                "transaction_date": month,
                "categorization_source": "rule",
            }
        ],
        payees=[{"id": "p1", "name": "Empik"}],
        spent={"env-2": 60.0},
    )

    view = await VIEW_BUILDERS["/dashboard"](stub_page())
    texts = [c.value for c in walk(view) if isinstance(c, ft.Text)]
    assert format_money(100) in texts  # not 50
    assert any("Fun is" in (t or "") and "over its plan" in (t or "") for t in texts)


async def test_dashboard_lists_the_latest_transactions_with_resolved_names(monkeypatch):
    _stub_dashboard(
        monkeypatch,
        envelopes=[{"id": "env-1", "name": "Groceries", "category_group_id": "cg-1", "target_amount": None}],
        # Newest first, as the server returns them.
        transactions=[
            {
                "id": "new",
                "envelope_id": "env-1",
                "payee_id": "p2",
                "account_id": "a",
                "amount": "-20.00",
                "transaction_date": "2026-08-01",
                "categorization_source": "rule",
            },
            {
                "id": "old",
                "envelope_id": "env-1",
                "payee_id": "p1",
                "account_id": "a",
                "amount": "-10.00",
                "transaction_date": "2026-01-02",
                "categorization_source": "rule",
            },
        ],
        payees=[{"id": "p1", "name": "Biedronka"}, {"id": "p2", "name": "Żabka"}],
    )

    view = await VIEW_BUILDERS["/dashboard"](stub_page())
    texts = [c.value for c in walk(view) if isinstance(c, ft.Text)]
    assert "Żabka" in texts
    # Payee and envelope ids are resolved to names, never shown raw.
    assert not any("p2" == t or "env-1" == t for t in texts)


def _last_month(day: int = 1) -> str:
    from utils import _shift_months, range_to_dates

    return _shift_months(range_to_dates("this")[0], -1).replace(day=day).isoformat()


async def test_dashboard_carries_last_months_leftover_into_this_month(monkeypatch):
    """Money assigned in a past month and never spent is still in the envelope.

    It used to be counted nowhere: the envelope reset to this month's own
    assignment, while `to_assign` had already subtracted the old one - so every
    month that passed pushed "Safe to spend" further below the truth."""
    from currency import format_money

    _stub_dashboard(
        monkeypatch,
        envelopes=[{"id": "env-1", "name": "Groceries", "category_group_id": "cg-1", "target_amount": None}],
        allocations=[
            {"id": "a1", "envelope_id": "env-1", "month": _last_month(), "assigned_amount": "500.00"},
            {"id": "a2", "envelope_id": "env-1", "month": _this_month(1), "assigned_amount": "500.00"},
        ],
        spent={"env-1": 300.0},  # all of it last month
        spent_this_month={},
    )

    view = await VIEW_BUILDERS["/dashboard"](stub_page())
    texts = [c.value for c in walk(view) if isinstance(c, ft.Text)]
    # 1000 assigned across the two months, 300 of it spent.
    assert format_money(700) in texts


async def test_dashboard_ranks_busiest_envelopes_by_this_month(monkeypatch):
    """"Busiest" is about what moved recently, so a big lifetime total must not
    outrank an envelope that is actually being used right now."""
    _stub_dashboard(
        monkeypatch,
        envelopes=[
            {"id": "env-1", "name": "Old favourite", "category_group_id": "cg-1", "target_amount": None},
            {"id": "env-2", "name": "Busy now", "category_group_id": "cg-1", "target_amount": None},
        ],
        allocations=[
            {"id": "a1", "envelope_id": "env-1", "month": _this_month(1), "assigned_amount": "900.00"},
            {"id": "a2", "envelope_id": "env-2", "month": _this_month(1), "assigned_amount": "900.00"},
        ],
        spent={"env-1": 800.0, "env-2": 50.0},
        spent_this_month={"env-2": 50.0},
    )

    view = await VIEW_BUILDERS["/dashboard"](stub_page())
    texts = [c.value for c in walk(view) if isinstance(c, ft.Text)]
    assert "Busy now" in texts
    assert "Old favourite" not in texts


async def test_dashboard_and_its_nav_rail_share_one_fetch(monkeypatch):
    """The nav rail is chrome built independently of the screen inside it, so it
    used to fetch the month's envelopes/assignments/spending a second time."""
    calls: list[str] = []

    async def _counted():
        calls.append("envelopes")
        return []

    _stub_dashboard(monkeypatch, envelopes=[])
    monkeypatch.setattr("views.common.get_envelopes", _counted)

    await VIEW_BUILDERS["/dashboard"](stub_page())

    assert len(calls) == 1


async def test_dashboard_asks_the_server_for_only_the_rows_it_shows(monkeypatch):
    """It used to pull up to 100 transactions to render four, then re-sort them
    by date alone - breaking ties differently from the Transactions screen."""
    from views.dashboard import _MAX_ROWS

    calls: list[dict] = []
    _stub_dashboard(monkeypatch, envelopes=[], page_calls=calls)

    await VIEW_BUILDERS["/dashboard"](stub_page())

    assert calls == [{"limit": _MAX_ROWS}]


async def test_dashboard_rows_open_the_envelope_they_name(monkeypatch):
    """The mock version navigated to the detail page without setting the session
    id, so every row opened whichever envelope was selected last."""
    month = _this_month(1)
    _stub_dashboard(
        monkeypatch,
        envelopes=[{"id": "env-9", "name": "Groceries", "category_group_id": "cg-1", "target_amount": None}],
        allocations=[{"id": "a1", "envelope_id": "env-9", "month": month, "assigned_amount": "100.00"}],
        transactions=[
            {
                "id": "t1",
                "envelope_id": "env-9",
                "payee_id": "p1",
                "account_id": "a",
                "amount": "-30.00",
                "transaction_date": month,
                "categorization_source": "rule",
            }
        ],
        payees=[{"id": "p1", "name": "Biedronka"}],
        spent={"env-9": 30.0},
    )

    routed: list[str] = []
    page = stub_page()
    page.navigate = routed.append
    view = await VIEW_BUILDERS["/dashboard"](page)

    row = next(
        c
        for c in walk(view)
        if isinstance(c, ft.Container)
        and getattr(c, "on_click", None) is not None
        and any(isinstance(t, ft.Text) and t.value == "Groceries" for t in walk(c))
    )
    row.on_click(SimpleNamespace(control=row))

    assert page.session.store.get("selected_envelope_id") == "env-9"
    assert routed == ["/envelopes/detail"]


async def test_dashboard_survives_a_completely_empty_budget(monkeypatch):
    _stub_dashboard(monkeypatch, envelopes=[])
    view = await VIEW_BUILDERS["/dashboard"](stub_page())
    texts = [c.value for c in walk(view) if isinstance(c, ft.Text)]
    assert "Nothing spent this month yet." in texts
    assert "No transactions imported yet." in texts
    # An empty budget is not an outage, and must not be reported as one.
    assert not any("Couldn't reach the server" in (t or "") for t in texts)


async def test_dashboard_says_so_when_the_server_is_unreachable(monkeypatch):
    """An unreachable gateway used to render a confident "0,00 zł safe to spend"
    over empty cards - indistinguishable from a budget with nothing in it."""
    import httpx

    async def _boom(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    _stub_dashboard(monkeypatch, envelopes=[])
    monkeypatch.setattr("api_client._client", lambda: SimpleNamespace(get=_boom))
    # Straight through `api_client`, so the real except/`_note_failure` path runs.
    monkeypatch.setattr("views.dashboard.get_to_assign", api_client.get_to_assign)

    view = await VIEW_BUILDERS["/dashboard"](stub_page())
    texts = [c.value for c in walk(view) if isinstance(c, ft.Text)]
    assert any("Couldn't reach the server" in (t or "") for t in texts)


async def test_dashboard_empty_list_from_a_404_is_not_an_outage(monkeypatch):
    """The gateway answers "no rows" with 404 on its list endpoints, so counting
    404s as failures would put an outage banner over every empty budget."""
    import httpx

    async def _not_found(*args, **kwargs):
        request = httpx.Request("GET", "http://test/budget/payees")
        raise httpx.HTTPStatusError("nope", request=request, response=httpx.Response(404, request=request))

    _stub_dashboard(monkeypatch, envelopes=[])
    monkeypatch.setattr("api_client._client", lambda: SimpleNamespace(get=_not_found))
    monkeypatch.setattr("views.dashboard.get_payees", api_client.get_payees)

    view = await VIEW_BUILDERS["/dashboard"](stub_page())
    texts = [c.value for c in walk(view) if isinstance(c, ft.Text)]
    assert not any("Couldn't reach the server" in (t or "") for t in texts)


async def test_dashboard_keeps_the_latest_transactions_on_a_phone(monkeypatch):
    """The card used to be dropped below tablet width, which took "what just left
    my account" off the screen it matters most on."""
    _stub_dashboard(
        monkeypatch,
        envelopes=[{"id": "env-1", "name": "Groceries", "category_group_id": "cg-1", "target_amount": None}],
        transactions=[
            {
                "id": "t1",
                "envelope_id": "env-1",
                "payee_id": "p1",
                "account_id": "a",
                "amount": "-20.00",
                "transaction_date": _this_month(3),
                "categorization_source": "rule",
            }
        ],
        payees=[{"id": "p1", "name": "Żabka"}],
    )

    view = await VIEW_BUILDERS["/dashboard"](stub_page(MOBILE_WIDTH))
    texts = [c.value for c in walk(view) if isinstance(c, ft.Text)]
    assert "LATEST TRANSACTIONS" in texts
    assert "Żabka" in texts


async def test_sidebar_attention_badge_counts_real_envelopes(monkeypatch):
    """It was `len(attention_envelopes())` over the static mock, so the badge
    showed the same number forever, right next to real group totals."""
    from theme import palette
    from views.common import category_group_nav, fetch_budget_snapshot

    month = _this_month(1)

    async def _groups():
        return [{"id": "cg-1", "name": "Everyday"}]

    async def _envelopes():
        return [
            {"id": "env-1", "name": "Groceries", "category_group_id": "cg-1", "target_amount": None},
            {"id": "env-2", "name": "Rent", "category_group_id": "cg-1", "target_amount": None},
        ]

    async def _allocations(envelope_id=None):
        return [
            {"id": "a1", "envelope_id": "env-1", "month": month, "assigned_amount": "10.00"},
            {"id": "a2", "envelope_id": "env-2", "month": month, "assigned_amount": "500.00"},
        ]

    async def _spent(**kwargs):
        return {"env-1": 60.0}

    monkeypatch.setattr("views.common.get_spent_by_envelope", _spent)
    monkeypatch.setattr("views.common.get_category_groups", _groups)
    monkeypatch.setattr("views.common.get_envelopes", _envelopes)
    monkeypatch.setattr("views.common.get_envelope_allocations", _allocations)

    page = stub_page()
    items, attention = category_group_nav(palette(page), page, await fetch_budget_snapshot())

    assert len(items) == 1
    assert attention == 1  # Groceries is over; Rent is untouched


# --- Forecast: the projection is the server's, and this screen renders it ----


def _stub_forecast(monkeypatch, *, forecast, envelopes=(), category_groups=()):
    """`envelopes`/`category_groups` are the shell snapshot's - the Forecast screen
    only needs them for names, since the forecast itself speaks in ids.

    The projection is never derived here: whatever `forecast` says is what the
    screen must show, which is the whole reason the endpoint exists.
    """

    async def _forecast(month=None, as_of=None):
        return dict(forecast)

    async def _envelopes():
        return list(envelopes)

    async def _groups():
        return list(category_groups)

    monkeypatch.setattr("views.forecast.get_forecast", _forecast)
    monkeypatch.setattr("views.common.get_envelopes", _envelopes)
    monkeypatch.setattr("views.common.get_category_groups", _groups)


_TWO_ENVELOPES = [
    {"id": "env-1", "name": "Groceries", "category_group_id": "cg-1", "target_amount": None},
    {"id": "env-2", "name": "Hobbies", "category_group_id": "cg-1", "target_amount": None},
]


def _forecast_payload(**overrides) -> dict:
    payload = {
        "month": _this_month(1),
        "as_of": _this_month(15),
        "elapsed_fraction": "0.4839",
        "method": "linear-pace",
        "funded_total": "300.00",
        "spent_total": "200.00",
        "projected_total": "413.30",
        "category_groups": [
            {"category_group_id": "cg-1", "funded": "300.00", "spent": "200.00", "projected": "413.30"}
        ],
        "envelopes": [
            {
                "envelope_id": "env-1",
                "category_group_id": "cg-1",
                "carried_over": "0.00",
                "assigned": "100.00",
                "funded": "100.00",
                "spent": "90.00",
                "projected": "186.00",
            },
            {
                "envelope_id": "env-2",
                "category_group_id": "cg-1",
                "carried_over": "0.00",
                "assigned": "200.00",
                "funded": "200.00",
                "spent": "110.00",
                "projected": "227.30",
            },
        ],
    }
    payload.update(overrides)
    return payload


async def test_forecast_shows_the_projection_the_server_sent(monkeypatch):
    """It used to pace the mock's spending itself, with a hardcoded 31-day month.
    The numbers now arrive computed, so a real predictive model can replace the
    estimator without this screen changing."""
    from currency import format_money

    _stub_forecast(
        monkeypatch,
        forecast=_forecast_payload(),
        envelopes=_TWO_ENVELOPES,
        category_groups=[{"id": "cg-1", "name": "Everyday"}],
    )

    view = await VIEW_BUILDERS["/forecast"](stub_page())
    texts = [c.value for c in walk(view) if isinstance(c, ft.Text)]

    assert format_money(413.30) in texts  # projected, verbatim
    assert format_money(300.00) in texts  # what the envelopes hold
    assert format_money(113.30) in texts  # the difference between the two


async def test_forecast_compares_against_what_the_envelopes_hold(monkeypatch):
    """The baseline is `funded`, not this month's assignment - and the legend has
    to say so. It read "Assigned", which stopped being the comparison the moment
    envelopes started carrying money over."""
    _stub_forecast(
        monkeypatch,
        forecast=_forecast_payload(),
        envelopes=_TWO_ENVELOPES,
        category_groups=[{"id": "cg-1", "name": "Everyday"}],
    )

    view = await VIEW_BUILDERS["/forecast"](stub_page())
    texts = [c.value for c in walk(view) if isinstance(c, ft.Text)]

    assert "Available" in texts
    assert "Assigned" not in texts


async def test_forecast_legend_names_the_real_end_of_the_month(monkeypatch):
    """"Projected by the 31st" was hardcoded - a date February does not have."""
    from dates import month_end_label

    _stub_forecast(
        monkeypatch,
        forecast=_forecast_payload(),
        envelopes=_TWO_ENVELOPES,
        category_groups=[{"id": "cg-1", "name": "Everyday"}],
    )

    view = await VIEW_BUILDERS["/forecast"](stub_page())
    texts = [c.value for c in walk(view) if isinstance(c, ft.Text)]

    assert f"Projected by {month_end_label()}" in texts


async def test_forecast_says_which_estimator_produced_it(monkeypatch):
    """A straight-line guess presented without explanation invites more
    confidence than it has earned."""
    _stub_forecast(
        monkeypatch,
        forecast=_forecast_payload(),
        envelopes=_TWO_ENVELOPES,
        category_groups=[{"id": "cg-1", "name": "Everyday"}],
    )

    view = await VIEW_BUILDERS["/forecast"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert any("Straight-line pace" in t for t in texts)


async def test_forecast_describes_an_estimator_it_has_never_heard_of(monkeypatch):
    """New estimators will appear in `method`; an unrecognised one must be named,
    not silently dropped as if the projection came from nowhere."""
    _stub_forecast(
        monkeypatch,
        forecast=_forecast_payload(method="seasonal-v2"),
        envelopes=_TWO_ENVELOPES,
        category_groups=[{"id": "cg-1", "name": "Everyday"}],
    )

    view = await VIEW_BUILDERS["/forecast"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert any('Estimated by "seasonal-v2"' in t for t in texts)


async def test_forecast_keeps_the_servers_ranking(monkeypatch):
    """Most at risk first, as ordered by whatever produced the projection. A
    client re-sorting by its own rule would overrule a model that has a view on
    which risk matters."""
    # Deliberately contradicts what a client-side "sort by overshoot" would do:
    # Groceries leads the payload while overshooting by 20, Hobbies follows while
    # overshooting by 100. Only a screen that keeps the server's order passes.
    _stub_forecast(
        monkeypatch,
        forecast=_forecast_payload(
            envelopes=[
                {
                    "envelope_id": "env-1",
                    "category_group_id": "cg-1",
                    "carried_over": "0.00",
                    "assigned": "100.00",
                    "funded": "100.00",
                    "spent": "60.00",
                    "projected": "120.00",
                },
                {
                    "envelope_id": "env-2",
                    "category_group_id": "cg-1",
                    "carried_over": "0.00",
                    "assigned": "200.00",
                    "funded": "200.00",
                    "spent": "150.00",
                    "projected": "300.00",
                },
            ]
        ),
        envelopes=_TWO_ENVELOPES,
        category_groups=[{"id": "cg-1", "name": "Everyday"}],
    )

    view = await VIEW_BUILDERS["/forecast"](stub_page())
    names = [c.value for c in walk(view) if isinstance(c, ft.Text) and c.value in {"Groceries", "Hobbies"}]

    assert names == ["Groceries", "Hobbies"]


async def test_forecast_only_flags_envelopes_projected_past_what_they_hold(monkeypatch):
    """An envelope carrying last month's money over is not trending over just
    because this month's assignment is small."""
    _stub_forecast(
        monkeypatch,
        forecast=_forecast_payload(
            envelopes=[
                {
                    "envelope_id": "env-1",
                    "category_group_id": "cg-1",
                    "carried_over": "400.00",
                    "assigned": "50.00",
                    "funded": "450.00",
                    "spent": "90.00",
                    "projected": "186.00",
                }
            ]
        ),
        envelopes=_TWO_ENVELOPES,
        category_groups=[{"id": "cg-1", "name": "Everyday"}],
    )

    view = await VIEW_BUILDERS["/forecast"](stub_page())
    texts = [c.value for c in walk(view) if isinstance(c, ft.Text)]

    assert "Nothing is trending over its plan." in texts
    assert "Groceries" not in texts


async def test_forecast_rows_open_the_envelope_they_name(monkeypatch):
    """Every "trending over" row navigated to `/envelopes/detail` without setting
    the session id, so all of them opened whichever envelope was looked at last."""
    _stub_forecast(
        monkeypatch,
        forecast=_forecast_payload(),
        envelopes=_TWO_ENVELOPES,
        category_groups=[{"id": "cg-1", "name": "Everyday"}],
    )

    routed: list[str] = []
    page = stub_page()
    page.navigate = routed.append
    view = await VIEW_BUILDERS["/forecast"](page)

    row = next(
        c
        for c in walk(view)
        if isinstance(c, ft.Container)
        and getattr(c, "on_click", None) is not None
        and any(isinstance(t, ft.Text) and t.value == "Hobbies" for t in walk(c))
    )
    row.on_click(SimpleNamespace(control=row))

    assert page.session.store.get("selected_envelope_id") == "env-2"
    assert routed == ["/envelopes/detail"]


async def test_forecast_survives_an_empty_budget(monkeypatch):
    _stub_forecast(monkeypatch, forecast={})

    view = await VIEW_BUILDERS["/forecast"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert "No category groups yet — there is nothing to project." in texts
    assert not any("Couldn't reach the server" in t for t in texts)


async def test_forecast_says_so_when_the_server_is_unreachable(monkeypatch):
    """A projection built from part of the data is not a projection, and 0,00 zł
    "projected spending" over an empty chart looks like good news."""
    import httpx

    async def _boom(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("api_client._client", lambda: SimpleNamespace(get=_boom))
    # Straight through `api_client`, so the real except/`_note_failure` path runs.
    monkeypatch.setattr("views.forecast.get_forecast", api_client.get_forecast)

    view = await VIEW_BUILDERS["/forecast"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert any("Couldn't reach the server" in t for t in texts)


# --- Alerts: computed from the envelopes, not read from a log ----------------


def _stub_alerts(monkeypatch, *, envelopes, allocations=(), spent=None, spent_this_month=None, category_groups=()):
    """Alerts has no reads of its own: it works entirely off the shell snapshot it
    already shares with the nav rail."""

    async def _envelopes():
        return list(envelopes)

    async def _allocations(envelope_id=None):
        return list(allocations)

    async def _groups():
        return list(category_groups)

    async def _spent(**kwargs):
        if kwargs.get("date_from") is None:
            return dict(spent or {})
        return dict(spent or {} if spent_this_month is None else spent_this_month)

    monkeypatch.setattr("views.common.get_envelopes", _envelopes)
    monkeypatch.setattr("views.common.get_envelope_allocations", _allocations)
    monkeypatch.setattr("views.common.get_category_groups", _groups)
    monkeypatch.setattr("views.common.get_spent_by_envelope", _spent)


async def test_alerts_are_worked_out_from_real_envelopes(monkeypatch):
    """Was six fixed rows with invented timestamps. Groceries is over, Hobbies is
    at 90% - both facts the data actually supports."""
    from currency import format_money

    month = _this_month(1)
    _stub_alerts(
        monkeypatch,
        envelopes=_TWO_ENVELOPES,
        allocations=[
            {"id": "a1", "envelope_id": "env-1", "month": month, "assigned_amount": "100.00"},
            {"id": "a2", "envelope_id": "env-2", "month": month, "assigned_amount": "200.00"},
        ],
        spent={"env-1": 130.0, "env-2": 180.0},
        category_groups=[{"id": "cg-1", "name": "Everyday"}],
    )

    view = await VIEW_BUILDERS["/alerts"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert f"Groceries is {format_money(30)} over its plan" in texts
    assert any(t.startswith("Hobbies is at 90%") for t in texts)
    # The group name comes from the snapshot, which used to leave it empty.
    assert any(t.startswith("Everyday · ") for t in texts)


async def test_alerts_put_the_overspent_envelopes_first(monkeypatch):
    month = _this_month(1)
    _stub_alerts(
        monkeypatch,
        envelopes=_TWO_ENVELOPES,
        allocations=[
            {"id": "a1", "envelope_id": "env-1", "month": month, "assigned_amount": "100.00"},
            {"id": "a2", "envelope_id": "env-2", "month": month, "assigned_amount": "200.00"},
        ],
        # Hobbies is nearly gone; Groceries is genuinely over.
        spent={"env-1": 130.0, "env-2": 198.0},
        category_groups=[{"id": "cg-1", "name": "Everyday"}],
    )

    view = await VIEW_BUILDERS["/alerts"](stub_page())
    titles = [
        c.value
        for c in walk(view)
        if isinstance(c, ft.Text) and (c.value or "").startswith(("Groceries is", "Hobbies is"))
    ]

    assert titles[0].startswith("Groceries is")


async def test_alerts_do_not_flag_an_envelope_living_off_last_months_money(monkeypatch):
    """Assigned 10 this month but carrying 400 over: 90 spent is 22% of what it
    holds, not 900% of what it was topped up with."""
    month = _this_month(1)
    last = _last_month(1)
    _stub_alerts(
        monkeypatch,
        envelopes=[_TWO_ENVELOPES[0]],
        allocations=[
            {"id": "a0", "envelope_id": "env-1", "month": last, "assigned_amount": "400.00"},
            {"id": "a1", "envelope_id": "env-1", "month": month, "assigned_amount": "10.00"},
        ],
        spent={"env-1": 90.0},
        spent_this_month={"env-1": 90.0},
        category_groups=[{"id": "cg-1", "name": "Everyday"}],
    )

    view = await VIEW_BUILDERS["/alerts"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert "Nothing needs attention — every envelope is inside what it holds." in texts


async def test_alerts_never_claim_a_notification_was_sent(monkeypatch):
    """The mock's meta line read "sent by email". Nothing in this app sends
    anything, and there is no delivery history to read from."""
    month = _this_month(1)
    _stub_alerts(
        monkeypatch,
        envelopes=_TWO_ENVELOPES,
        allocations=[
            {"id": "a1", "envelope_id": "env-1", "month": month, "assigned_amount": "100.00"},
            {"id": "a2", "envelope_id": "env-2", "month": month, "assigned_amount": "200.00"},
        ],
        spent={"env-1": 130.0, "env-2": 180.0},
        category_groups=[{"id": "cg-1", "name": "Everyday"}],
    )

    view = await VIEW_BUILDERS["/alerts"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert not any("sent by email" in t for t in texts)


async def test_alerts_state_the_threshold_from_settings(monkeypatch):
    """The subtitle used to hardcode 80 next to a separately hardcoded 0.8, and
    neither had anything to do with the Settings slider."""
    set_alert_threshold(60)
    _stub_alerts(monkeypatch, envelopes=[])

    view = await VIEW_BUILDERS["/alerts"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert any("Heads-up at 60%" in t for t in texts)
    assert not any("Heads-up at 80%" in t for t in texts)


def _stub_alerts_at_65_percent(monkeypatch):
    """One envelope with 130 of 200 spent - 65%, either side of the threshold
    depending on what the user chose."""
    month = _this_month(1)
    _stub_alerts(
        monkeypatch,
        envelopes=[_TWO_ENVELOPES[1]],
        allocations=[{"id": "a2", "envelope_id": "env-2", "month": month, "assigned_amount": "200.00"}],
        spent={"env-2": 130.0},
        category_groups=[{"id": "cg-1", "name": "Everyday"}],
    )


async def test_lowering_the_threshold_flags_an_envelope_that_was_fine(monkeypatch):
    """The point of the setting: at 80% this envelope is on track, at 60% it is
    worth a heads-up. The slider used to move and change nothing anywhere."""
    set_alert_threshold(60)
    _stub_alerts_at_65_percent(monkeypatch)

    view = await VIEW_BUILDERS["/alerts"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert any(t.startswith("Hobbies is at 65%") for t in texts)


async def test_the_same_envelope_is_quiet_at_the_default_threshold(monkeypatch):
    """The other half of the test above - without it, "flagged at 60%" could just
    mean "flagged always"."""
    set_alert_threshold(DEFAULT_ALERT_THRESHOLD)
    _stub_alerts_at_65_percent(monkeypatch)

    view = await VIEW_BUILDERS["/alerts"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert "Nothing needs attention — every envelope is inside what it holds." in texts


async def test_the_threshold_also_moves_the_sidebar_attention_badge(monkeypatch):
    """Every warning in the app comes through `envelope_state()`, so the setting
    has to reach the nav rail too - a screen saying "needs attention" beside a
    badge counting on a different threshold would contradict itself."""
    from theme import palette
    from views.common import category_group_nav, fetch_budget_snapshot

    _stub_alerts_at_65_percent(monkeypatch)
    page = stub_page()

    set_alert_threshold(DEFAULT_ALERT_THRESHOLD)
    _, quiet = category_group_nav(palette(page), page, await fetch_budget_snapshot())

    set_alert_threshold(60)
    _, flagged = category_group_nav(palette(page), page, await fetch_budget_snapshot())

    assert (quiet, flagged) == (0, 1)


def _threshold_slider(view) -> ft.Slider:
    return next(c for c in walk(view) if isinstance(c, ft.Slider))


async def test_threshold_slider_persists_and_rebuilds(monkeypatch):
    """It used to keep its value in a local dict that nothing else ever read."""
    from preferences import ALERT_THRESHOLD_STORAGE_KEY, alert_threshold

    stored: dict = {}
    rebuilt: list = []

    page = stub_page()
    page.shared_preferences = SimpleNamespace(
        set=lambda key, value: _async_return(stored.__setitem__(key, value) or True),
        get=lambda key: _async_return(stored.get(key)),
    )

    async def on_route_change(e):
        rebuilt.append(e)

    page.on_route_change = on_route_change

    view = await VIEW_BUILDERS["/settings"](page)
    slider = _threshold_slider(view)
    assert slider.value == DEFAULT_ALERT_THRESHOLD

    await slider.on_change_end(SimpleNamespace(control=SimpleNamespace(value=65.0)))

    assert alert_threshold() == 65
    assert stored == {ALERT_THRESHOLD_STORAGE_KEY: 65}
    # Envelope states are resolved at build time, so the route has to be rebuilt
    # for a new threshold to reach anything already on screen.
    assert len(rebuilt) == 1


async def test_dragging_the_threshold_slider_does_not_commit_every_step():
    """`on_change` fires ten times across a drag; committing each one would write
    to shared preferences and rebuild the whole route ten times."""
    from preferences import alert_threshold

    page = stub_page()
    view = await VIEW_BUILDERS["/settings"](page)
    slider = _threshold_slider(view)

    slider.on_change(SimpleNamespace(control=SimpleNamespace(value=55.0)))

    assert alert_threshold() == DEFAULT_ALERT_THRESHOLD
    assert any(isinstance(c, ft.Text) and c.value == "55%" for c in walk(view))


async def test_dark_mode_survives_a_reload(monkeypatch):
    """It was the one Settings control that looked like it worked and did not:
    `apply_theme()` set light unconditionally at startup, so choosing dark got
    you a white screen every time you came back."""
    from preferences import DARK_MODE_STORAGE_KEY, dark_mode, set_dark_mode
    from theme import apply_theme

    stored: dict = {}
    page = stub_page()
    page.shared_preferences = SimpleNamespace(
        set=lambda key, value: _async_return(stored.__setitem__(key, value) or True),
        get=lambda key: _async_return(stored.get(key)),
    )
    page.on_route_change = None

    view = await VIEW_BUILDERS["/settings"](page)
    toggle = next(c for c in walk(view) if isinstance(c, ft.Switch))
    await toggle.on_change(SimpleNamespace(control=SimpleNamespace(value=True)))

    assert stored == {DARK_MODE_STORAGE_KEY: True}

    # A fresh start reads it back and paints dark before the first route change.
    set_dark_mode(False)
    from main import _restore_preferences

    fresh = SimpleNamespace(shared_preferences=SimpleNamespace(get=lambda key: _async_return(stored.get(key))))
    await _restore_preferences(fresh)
    assert dark_mode() is True

    painted = stub_page()
    apply_theme(painted)
    assert painted.theme_mode == ft.ThemeMode.DARK


async def test_the_notification_picker_does_not_offer_a_channel_that_does_not_exist():
    """Envelo has no mailer, no webhook worker and no queue, so "Email" and
    "Webhook" both named something that cannot happen - in a control that also
    persisted nothing."""
    view = await VIEW_BUILDERS["/settings"](stub_page())

    picker = next(
        c
        for c in walk(view)
        if isinstance(c, ft.Dropdown) and any(o.key in {"none", "email", "webhook"} for o in (c.options or []))
    )
    assert picker.disabled is True
    assert [o.key for o in picker.options] == ["none"]


async def test_settings_does_not_greet_a_user_that_does_not_exist():
    """The eyebrow read "Dawid Krysa · dawid@envelo.local" - a name and an
    address that exist nowhere. There is no user entity behind the API."""
    view = await VIEW_BUILDERS["/settings"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert not any("@" in t for t in texts)


async def test_sign_out_does_not_promise_a_password_prompt():
    """There is no auth: the login screen accepts anything and this button only
    navigates."""
    view = await VIEW_BUILDERS["/settings"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert not any("password" in t.lower() for t in texts)


async def test_saved_threshold_is_restored_before_anything_renders():
    """Same reason the currency is: envelope states - and the colors that follow
    from them - are resolved at build time, so this has to happen in `main()`
    before the first route change."""
    from main import _restore_preferences
    from preferences import ALERT_THRESHOLD_STORAGE_KEY, alert_threshold

    stored = {ALERT_THRESHOLD_STORAGE_KEY: 55}
    page = SimpleNamespace(
        shared_preferences=SimpleNamespace(get=lambda key: _async_return(stored.get(key)))
    )

    await _restore_preferences(page)

    assert alert_threshold() == 55


async def test_a_nonsense_stored_threshold_falls_back_instead_of_breaking(monkeypatch):
    """The value can be missing, stale or hand-edited. A threshold of 0 would
    paint every envelope amber forever, and a string would raise."""
    from main import _restore_preferences
    from preferences import ALERT_THRESHOLD_STORAGE_KEY, MIN_ALERT_THRESHOLD, alert_threshold

    for value, expected in (("not a number", DEFAULT_ALERT_THRESHOLD), (0, MIN_ALERT_THRESHOLD), (None, DEFAULT_ALERT_THRESHOLD)):
        page = SimpleNamespace(
            shared_preferences=SimpleNamespace(
                get=lambda key, v=value: _async_return(v if key == ALERT_THRESHOLD_STORAGE_KEY else None)
            )
        )
        await _restore_preferences(page)
        assert alert_threshold() == expected


async def test_alert_rows_open_the_envelope_they_name(monkeypatch):
    month = _this_month(1)
    _stub_alerts(
        monkeypatch,
        envelopes=_TWO_ENVELOPES,
        allocations=[{"id": "a2", "envelope_id": "env-2", "month": month, "assigned_amount": "200.00"}],
        spent={"env-2": 250.0},
        category_groups=[{"id": "cg-1", "name": "Everyday"}],
    )

    routed: list[str] = []
    page = stub_page()
    page.navigate = routed.append
    view = await VIEW_BUILDERS["/alerts"](page)

    open_button = find_button(view, "Open")
    assert open_button is not None
    open_button.on_click(SimpleNamespace(control=open_button))

    assert page.session.store.get("selected_envelope_id") == "env-2"
    assert routed == ["/envelopes/detail"]


async def test_alerts_and_their_nav_rail_share_one_fetch(monkeypatch):
    """Same snapshot as the shell: the screen is envelope-shaped, so it hands its
    own to `app_shell` rather than letting the nav fetch the month twice."""
    calls: list[str] = []

    async def _counted():
        calls.append("envelopes")
        return []

    _stub_alerts(monkeypatch, envelopes=[])
    monkeypatch.setattr("views.common.get_envelopes", _counted)

    await VIEW_BUILDERS["/alerts"](stub_page())

    assert len(calls) == 1


# --- Payees: history the database counted, plus Rename and Merge that work ---


def _stub_payees(monkeypatch, *, payees, stats=None, envelopes=()):
    state = {"payees": list(payees), "stats": dict(stats or {})}

    async def _payees():
        return list(state["payees"])

    async def _stats():
        return dict(state["stats"])

    async def _envelopes():
        return list(envelopes)

    monkeypatch.setattr("views.payees.get_payees", _payees)
    monkeypatch.setattr("views.payees.get_payee_stats", _stats)
    monkeypatch.setattr("views.payees.get_envelopes", _envelopes)
    return state


_BIEDRONKA = {"id": "p1", "name": "Biedronka"}
_DUPLICATE = {"id": "p2", "name": "BIEDRONKA 1234"}


async def test_payees_show_the_history_the_database_counted(monkeypatch):
    """Was seven fixed rows with invented counts and totals."""
    _stub_payees(
        monkeypatch,
        payees=[_BIEDRONKA],
        stats={
            "p1": {
                "total": "-1842.55",
                "transaction_count": 46,
                "last_transaction_date": "2026-07-23",
                "top_envelope_id": "env-1",
            }
        },
        envelopes=[{"id": "env-1", "name": "Groceries", "category_group_id": "cg-1", "target_amount": None}],
    )

    view = await VIEW_BUILDERS["/payees"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert "Biedronka" in texts
    assert any("46 transactions · last on 23 July 2026" in t for t in texts)
    assert "Groceries" in texts


async def test_a_payee_that_pays_you_is_not_shown_as_spending(monkeypatch):
    """The mock rendered `format_money(-total)`, which turned an employer or a
    refund into an expense. The total is signed and shown as it is."""
    from currency import format_money

    _stub_payees(
        monkeypatch,
        payees=[{"id": "p9", "name": "Kestrel BV"}],
        stats={"p9": {"total": "3180.00", "transaction_count": 1, "last_transaction_date": "2026-07-15"}},
    )

    page = stub_page()
    view = await VIEW_BUILDERS["/payees"](page)
    from theme import palette

    amount = next(c for c in walk(view) if isinstance(c, ft.Text) and c.value == format_money(3180))
    assert amount.style.color == palette(page).ok_ink


async def test_a_payee_nobody_has_filed_reads_as_uncategorized(monkeypatch):
    _stub_payees(
        monkeypatch,
        payees=[_BIEDRONKA],
        stats={"p1": {"total": "-10.00", "transaction_count": 1, "top_envelope_id": None}},
    )

    view = await VIEW_BUILDERS["/payees"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert "Uncategorized" in texts


async def test_a_payee_with_no_transactions_says_so(monkeypatch):
    _stub_payees(monkeypatch, payees=[_BIEDRONKA], stats={"p1": {"total": "0", "transaction_count": 0}})

    view = await VIEW_BUILDERS["/payees"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert "no transactions yet" in texts


async def test_payees_are_listed_busiest_first(monkeypatch):
    """The ones worth renaming or merging are the ones that keep arriving."""
    _stub_payees(
        monkeypatch,
        payees=[{"id": "p1", "name": "Rzadki"}, {"id": "p2", "name": "Czesty"}],
        stats={"p1": {"transaction_count": 2, "total": "0"}, "p2": {"transaction_count": 40, "total": "0"}},
    )

    view = await VIEW_BUILDERS["/payees"](stub_page())
    names = [c.value for c in walk(view) if isinstance(c, ft.Text) and c.value in {"Rzadki", "Czesty"}]

    assert names == ["Czesty", "Rzadki"]


async def test_history_hands_the_payee_to_the_transactions_search(monkeypatch):
    """It used to navigate to an unfiltered list, which answered nothing."""
    from views.common import PREFILL_SEARCH_KEY

    _stub_payees(monkeypatch, payees=[_BIEDRONKA], stats={"p1": {"total": "0", "transaction_count": 1}})

    routed: list[str] = []
    page = stub_page()
    page.navigate = routed.append
    view = await VIEW_BUILDERS["/payees"](page)

    find_button(view, "History").on_click(SimpleNamespace(control=None))

    assert page.session.store.get(PREFILL_SEARCH_KEY) == "Biedronka"
    assert routed == ["/transactions"]


async def test_transactions_pick_up_a_handed_over_search_once(monkeypatch):
    """And widen the range: a payee last seen in May, opened in August, would
    otherwise land on "This month" and read "No transactions match"."""
    from views.common import PREFILL_SEARCH_KEY

    calls: list[dict] = []

    async def _page(**kwargs):
        calls.append(kwargs)
        return [], 0

    monkeypatch.setattr("views.transactions.get_transactions_page", _page)

    page = stub_page()
    page.session.store.set(PREFILL_SEARCH_KEY, "Biedronka")
    view = await VIEW_BUILDERS["/transactions"](page)

    assert calls[0]["search"] == "Biedronka"
    assert any(isinstance(c, ft.TextField) and c.value == "Biedronka" for c in walk(view))
    # Consumed, so it does not reappear on every later visit to the screen.
    assert page.session.store.get(PREFILL_SEARCH_KEY) is None

    calls.clear()
    await VIEW_BUILDERS["/transactions"](stub_page())
    assert calls[0]["search"] == ""


async def test_renaming_a_payee_saves_and_refreshes(monkeypatch):
    state = _stub_payees(monkeypatch, payees=[_BIEDRONKA], stats={"p1": {"total": "0", "transaction_count": 1}})
    updated: list[tuple] = []

    async def _update(payee_id, payload):
        updated.append((payee_id, payload))
        state["payees"] = [{"id": payee_id, **payload}]
        return {"id": payee_id, **payload}

    monkeypatch.setattr("api_client.update_payee", _update)

    page = stub_page()
    view = await VIEW_BUILDERS["/payees"](page)
    find_button(view, "Rename").on_click(SimpleNamespace(control=None))
    dialog = page.opened_dialogs[0]

    assert _dialog_field(dialog, "Name").value == "Biedronka"
    _dialog_field(dialog, "Name").value = "Biedronka Sp. z o.o."
    await dialog.actions[1].on_click(SimpleNamespace(control=None))

    assert updated == [("p1", {"name": "Biedronka Sp. z o.o."})]
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]
    assert "Biedronka Sp. z o.o." in texts


async def test_merging_offers_every_payee_except_the_one_being_merged(monkeypatch):
    """Merging a payee into itself would delete it and repoint its transactions
    at a row that no longer exists."""
    _stub_payees(
        monkeypatch,
        payees=[_BIEDRONKA, _DUPLICATE],
        stats={"p1": {"total": "0", "transaction_count": 5}, "p2": {"total": "0", "transaction_count": 1}},
    )

    page = stub_page()
    view = await VIEW_BUILDERS["/payees"](page)
    # Busiest first, so the second row's Merge belongs to the duplicate.
    merge_buttons = [
        c
        for c in walk(view)
        if isinstance(c, ft.Container)
        and isinstance(c.content, ft.Text)
        and c.content.value == "Merge"
    ]
    merge_buttons[1].on_click(SimpleNamespace(control=None))
    dialog = page.opened_dialogs[0]

    options = [o.key for o in _dialog_field(dialog, "Merge into").options]
    assert options == ["p1"]


async def test_merging_folds_one_payee_into_another(monkeypatch):
    state = _stub_payees(
        monkeypatch,
        payees=[_BIEDRONKA, _DUPLICATE],
        stats={"p1": {"total": "0", "transaction_count": 5}, "p2": {"total": "0", "transaction_count": 1}},
    )
    merged: list[tuple] = []

    async def _merge(from_id, into_id):
        merged.append((from_id, into_id))
        state["payees"] = [_BIEDRONKA]
        return _BIEDRONKA

    monkeypatch.setattr("api_client.merge_payees", _merge)

    page = stub_page()
    view = await VIEW_BUILDERS["/payees"](page)
    merge_buttons = [
        c
        for c in walk(view)
        if isinstance(c, ft.Container)
        and isinstance(c.content, ft.Text)
        and c.content.value == "Merge"
    ]
    merge_buttons[1].on_click(SimpleNamespace(control=None))
    dialog = page.opened_dialogs[0]

    _dialog_field(dialog, "Merge into").value = "p1"
    await dialog.actions[1].on_click(SimpleNamespace(control=None))

    assert merged == [("p2", "p1")]
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]
    assert "BIEDRONKA 1234" not in texts


async def test_payees_empty_state(monkeypatch):
    _stub_payees(monkeypatch, payees=[])

    view = await VIEW_BUILDERS["/payees"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert any(t.startswith("No payees yet.") for t in texts)


async def test_payees_say_so_when_the_server_is_unreachable(monkeypatch):
    import httpx

    async def _boom(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("api_client._client", lambda: SimpleNamespace(get=_boom))
    # Straight through `api_client`, so the real except/`_note_failure` path runs.
    monkeypatch.setattr("views.payees.get_payee_stats", api_client.get_payee_stats)

    view = await VIEW_BUILDERS["/payees"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert any("Couldn't reach the server" in t for t in texts)


# --- Accounts: balances the database summed, in each account's own currency --


def _stub_accounts(monkeypatch, *, accounts, balances=None):
    state = {"accounts": list(accounts), "balances": dict(balances or {})}

    async def _accounts():
        return list(state["accounts"])

    async def _balances():
        return dict(state["balances"])

    monkeypatch.setattr("views.accounts.get_accounts", _accounts)
    monkeypatch.setattr("views.accounts.get_account_balances", _balances)
    return state


_AN_ING = {"id": "acc-1", "name": "ING Checking", "type": "checking", "currency": "PLN"}
_A_CARD = {"id": "acc-2", "name": "Revolut", "type": "credit_card", "currency": "PLN"}


async def test_accounts_show_the_balance_the_database_summed(monkeypatch):
    """Was a fixed 2 418,62 zł per account in `mock_data.ACCOUNTS_LIST`."""
    _stub_accounts(
        monkeypatch,
        accounts=[_AN_ING],
        balances={"acc-1": {"balance": "2418.62", "transaction_count": 142, "last_imported_at": "2026-07-24T09:00:00"}},
    )

    view = await VIEW_BUILDERS["/accounts"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert any("2" in t and "418,62 PLN" in t for t in texts)
    assert any("142 transactions" in t for t in texts)
    assert any("last import 24 July" in t for t in texts)


async def test_an_account_reports_its_own_currency_not_the_display_one(monkeypatch):
    """`currency.py` is how *this reader* likes to see money; `accounts.currency`
    is what the account holds. Formatting a EUR balance as złoty would be a
    different number, not a different formatting."""
    set_currency("pln")
    _stub_accounts(
        monkeypatch,
        accounts=[{"id": "acc-9", "name": "Wise", "type": "checking", "currency": "EUR"}],
        balances={"acc-9": {"balance": "100.00", "transaction_count": 1}},
    )

    view = await VIEW_BUILDERS["/accounts"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert any("100,00 EUR" in t for t in texts)
    assert not any("zł" in t for t in texts)


async def test_a_negative_balance_is_shown_as_owed(monkeypatch):
    _stub_accounts(
        monkeypatch,
        accounts=[_A_CARD],
        balances={"acc-2": {"balance": "-318.44", "transaction_count": 12}},
    )

    page = stub_page()
    view = await VIEW_BUILDERS["/accounts"](page)
    from theme import palette

    # The card's headline amount, not the header eyebrow that also names it.
    amount = next(
        c
        for c in walk(view)
        if isinstance(c, ft.Text) and "318,44 PLN" in (c.value or "") and c.style.size == 26
    )
    assert amount.style.color == palette(page).over_ink


async def test_an_account_with_no_history_says_so(monkeypatch):
    _stub_accounts(
        monkeypatch,
        accounts=[_AN_ING],
        balances={"acc-1": {"balance": "0", "transaction_count": 0, "last_imported_at": None}},
    )

    view = await VIEW_BUILDERS["/accounts"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert any("0 transactions · no imports yet" in t for t in texts)


async def test_the_total_is_only_claimed_within_one_currency(monkeypatch):
    """The mock added four balances and called it a total. Across currencies that
    is a number that is not money in any of them."""
    _stub_accounts(
        monkeypatch,
        accounts=[_AN_ING, {"id": "acc-9", "name": "Wise", "type": "checking", "currency": "EUR"}],
        balances={"acc-1": {"balance": "100.00"}, "acc-9": {"balance": "50.00"}},
    )

    view = await VIEW_BUILDERS["/accounts"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert "2 ACCOUNTS IN 2 CURRENCIES" in texts
    assert not any("150" in t for t in texts)


async def test_one_currency_still_gets_a_total(monkeypatch):
    _stub_accounts(
        monkeypatch,
        accounts=[_AN_ING, _A_CARD],
        balances={"acc-1": {"balance": "100.00"}, "acc-2": {"balance": "-30.00"}},
    )

    view = await VIEW_BUILDERS["/accounts"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert "70,00 PLN ACROSS 2 ACCOUNTS" in texts


async def test_adding_an_account_saves_it_and_refreshes(monkeypatch):
    state = _stub_accounts(monkeypatch, accounts=[])
    created: list[dict] = []

    async def _create(payload):
        created.append(payload)
        state["accounts"] = [{"id": "acc-new", **payload}]
        return {"id": "acc-new", **payload}

    monkeypatch.setattr("api_client.create_account", _create)

    page = stub_page()
    view = await VIEW_BUILDERS["/accounts"](page)
    find_button(view, "Add account").on_click(SimpleNamespace(control=None))
    dialog = page.opened_dialogs[0]

    _dialog_field(dialog, "Name").value = " Cash "
    _dialog_field(dialog, "Type").value = "cash"
    _dialog_field(dialog, "Currency").value = "PLN"
    await dialog.actions[1].on_click(SimpleNamespace(control=None))

    assert created == [{"name": "Cash", "type": "cash", "currency": "PLN"}]
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]
    assert "Cash" in texts


async def test_the_account_dialog_offers_the_type_the_api_accepts(monkeypatch):
    """The stub offered "credit", which is not a value of the API's `AccountType`
    enum - picking it would have been a 422 the moment this was wired up."""
    from views.dialogs import ACCOUNT_TYPES

    assert dict(ACCOUNT_TYPES)["credit_card"] == "Credit card"
    assert "credit" not in dict(ACCOUNT_TYPES)


async def test_editing_an_account_prefills_it_and_updates(monkeypatch):
    state = _stub_accounts(monkeypatch, accounts=[_AN_ING], balances={"acc-1": {"balance": "10.00"}})
    updated: list[tuple] = []

    async def _update(account_id, payload):
        updated.append((account_id, payload))
        state["accounts"] = [{"id": account_id, **payload}]
        return {"id": account_id, **payload}

    monkeypatch.setattr("api_client.update_account", _update)

    page = stub_page()
    view = await VIEW_BUILDERS["/accounts"](page)
    find_button(view, "Edit").on_click(SimpleNamespace(control=None))
    dialog = page.opened_dialogs[0]

    assert _dialog_field(dialog, "Name").value == "ING Checking"
    assert _dialog_field(dialog, "Type").value == "checking"

    _dialog_field(dialog, "Name").value = "ING Główne"
    await dialog.actions[1].on_click(SimpleNamespace(control=None))

    assert updated == [("acc-1", {"name": "ING Główne", "type": "checking", "currency": "PLN"})]


async def test_accounts_empty_state(monkeypatch):
    _stub_accounts(monkeypatch, accounts=[])

    view = await VIEW_BUILDERS["/accounts"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert any(t.startswith("No accounts yet.") for t in texts)


async def test_accounts_say_so_when_the_server_is_unreachable(monkeypatch):
    """An unreachable server renders every account at 0,00, which on this screen
    reads as "your money is gone" rather than "we could not ask"."""
    import httpx

    async def _boom(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("api_client._client", lambda: SimpleNamespace(get=_boom))
    # Straight through `api_client`, so the real except/`_note_failure` path runs.
    monkeypatch.setattr("views.accounts.get_account_balances", api_client.get_account_balances)

    view = await VIEW_BUILDERS["/accounts"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert any("Couldn't reach the server" in t for t in texts)


# --- Rules: a screen that described a feature the backend did not have -------


_RULE_ENVELOPES = [
    {"id": "env-1", "name": "Groceries", "category_group_id": "cg-1", "target_amount": None},
    {"id": "env-2", "name": "Transport", "category_group_id": "cg-1", "target_amount": None},
]


def _stub_rules(monkeypatch, *, rules, envelopes=_RULE_ENVELOPES):
    state = {"rules": list(rules)}

    async def _rules():
        return list(state["rules"])

    async def _envelopes():
        return list(envelopes)

    monkeypatch.setattr("views.rules.get_categorization_rules", _rules)
    monkeypatch.setattr("views.rules.get_envelopes", _envelopes)
    return state


async def test_rules_list_the_real_rules_with_their_envelope_names(monkeypatch):
    """Was six fixed rows naming envelopes that did not exist in the database."""
    _stub_rules(monkeypatch, rules=[{"id": "r1", "envelope_id": "env-2", "phrase": "Orlen"}])

    view = await VIEW_BUILDERS["/rules"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert "Orlen" in texts
    assert "Transport" in texts


async def test_rules_are_shown_in_the_order_that_settles_a_tie(monkeypatch):
    """The mock numbered rows 1..n beside "applied top to bottom", implying a
    precedence the server does not have. The longest matching phrase wins, so
    that is the order shown - and there is no numbering to imply otherwise."""
    _stub_rules(
        monkeypatch,
        rules=[
            {"id": "r1", "envelope_id": "env-1", "phrase": "Bie"},
            {"id": "r2", "envelope_id": "env-1", "phrase": "Biedronka Sp"},
            {"id": "r3", "envelope_id": "env-1", "phrase": "Biedronka"},
        ],
    )

    view = await VIEW_BUILDERS["/rules"](stub_page())
    phrases = [c.value for c in walk(view) if isinstance(c, ft.Text) and c.value in {"Bie", "Biedronka", "Biedronka Sp"}]

    assert phrases == ["Biedronka Sp", "Biedronka", "Bie"]


async def test_rules_no_longer_claim_a_match_count(monkeypatch):
    """Nothing records which rule filed which transaction, so "46 matches" was
    either invented or a different question wearing the same label."""
    _stub_rules(monkeypatch, rules=[{"id": "r1", "envelope_id": "env-1", "phrase": "Biedronka"}])

    view = await VIEW_BUILDERS["/rules"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert not any("match" in t.lower() and "wins" not in t.lower() for t in texts)


async def test_the_rules_header_no_longer_promises_an_order(monkeypatch):
    _stub_rules(monkeypatch, rules=[])

    view = await VIEW_BUILDERS["/rules"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert not any("TOP TO BOTTOM" in t for t in texts)
    assert "LONGEST MATCH WINS" in texts


async def test_rules_empty_state_says_what_a_rule_would_do(monkeypatch):
    _stub_rules(monkeypatch, rules=[])

    view = await VIEW_BUILDERS["/rules"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert any(t.startswith("No rules yet.") for t in texts)


async def test_a_rule_pointing_at_a_deleted_envelope_still_renders(monkeypatch):
    """Deleting an envelope drops its rules, but a rule can still outlive its
    envelope between one screen's fetch and the next - and a KeyError here would
    take the whole screen down."""
    _stub_rules(monkeypatch, rules=[{"id": "r1", "envelope_id": "gone", "phrase": "Biedronka"}])

    view = await VIEW_BUILDERS["/rules"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert "Deleted envelope" in texts


async def test_the_rule_dialog_offers_only_the_condition_the_matcher_supports(monkeypatch):
    """It used to offer "Payee contains" / "Description contains" / "Amount
    equals" against a model with one `phrase` column - two could never be saved,
    and the one that could was matched against the description."""
    _stub_rules(monkeypatch, rules=[])

    page = stub_page()
    view = await VIEW_BUILDERS["/rules"](page)
    find_button(view, "Add rule").on_click(SimpleNamespace(control=None))
    dialog = page.opened_dialogs[0]

    labels = [c.value for c in walk(dialog) if isinstance(c, ft.Text) and (c.value or "").isupper()]
    assert "PAYEE CONTAINS" in labels
    assert "PUT IT IN" in labels
    assert not any("DESCRIPTION" in ln or "AMOUNT" in ln for ln in labels)


async def test_adding_a_rule_saves_it_and_refreshes(monkeypatch):
    state = _stub_rules(monkeypatch, rules=[])
    created: list[dict] = []

    async def _create(payload):
        created.append(payload)
        state["rules"] = [{"id": "r9", **payload}]
        return {"id": "r9", **payload}

    monkeypatch.setattr("api_client.create_categorization_rule", _create)

    page = stub_page()
    view = await VIEW_BUILDERS["/rules"](page)
    find_button(view, "Add rule").on_click(SimpleNamespace(control=None))
    dialog = page.opened_dialogs[0]

    _dialog_field(dialog, "Payee contains").value = "  Biedronka  "
    _dialog_field(dialog, "Put it in").value = "env-1"
    await dialog.actions[1].on_click(SimpleNamespace(control=None))

    assert created == [{"envelope_id": "env-1", "phrase": "Biedronka"}]
    # Refetched, not patched in place: the list has to agree with the server.
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]
    assert "Biedronka" in texts


async def test_a_rule_needs_both_a_phrase_and_an_envelope(monkeypatch):
    _stub_rules(monkeypatch, rules=[])
    calls: list[dict] = []

    async def _create(payload):
        calls.append(payload)
        return {"id": "r9", **payload}

    monkeypatch.setattr("api_client.create_categorization_rule", _create)

    page = stub_page()
    view = await VIEW_BUILDERS["/rules"](page)
    find_button(view, "Add rule").on_click(SimpleNamespace(control=None))
    dialog = page.opened_dialogs[0]

    _dialog_field(dialog, "Payee contains").value = "   "
    _dialog_field(dialog, "Put it in").value = "env-1"
    await dialog.actions[1].on_click(SimpleNamespace(control=None))

    assert calls == []
    assert page.opened_dialogs  # still open, with an error to read


async def test_editing_a_rule_prefills_it_and_updates(monkeypatch):
    state = _stub_rules(monkeypatch, rules=[{"id": "r1", "envelope_id": "env-1", "phrase": "Biedronka"}])
    updated: list[tuple] = []

    async def _update(rule_id, payload):
        updated.append((rule_id, payload))
        state["rules"] = [{"id": rule_id, **payload}]
        return {"id": rule_id, **payload}

    monkeypatch.setattr("api_client.update_categorization_rule", _update)

    page = stub_page()
    view = await VIEW_BUILDERS["/rules"](page)
    find_button(view, "Edit").on_click(SimpleNamespace(control=None))
    dialog = page.opened_dialogs[0]

    assert _dialog_field(dialog, "Payee contains").value == "Biedronka"
    assert _dialog_field(dialog, "Put it in").value == "env-1"

    _dialog_field(dialog, "Put it in").value = "env-2"
    await dialog.actions[1].on_click(SimpleNamespace(control=None))

    assert updated == [("r1", {"envelope_id": "env-2", "phrase": "Biedronka"})]


async def test_deleting_a_rule_asks_first_and_says_what_survives(monkeypatch):
    state = _stub_rules(monkeypatch, rules=[{"id": "r1", "envelope_id": "env-1", "phrase": "Biedronka"}])
    deleted: list[str] = []

    async def _delete(rule_id):
        deleted.append(rule_id)
        state["rules"] = []
        return {"id": rule_id}

    monkeypatch.setattr("views.rules.delete_categorization_rule", _delete)

    page = stub_page()
    view = await VIEW_BUILDERS["/rules"](page)
    find_button(view, "Delete").on_click(SimpleNamespace(control=None))
    dialog = page.opened_dialogs[0]

    messages = [c.value or "" for c in walk(dialog) if isinstance(c, ft.Text)]
    assert any("keep their envelope" in m for m in messages)

    assert deleted == []  # nothing happens until it is confirmed
    await dialog.actions[1].on_click(SimpleNamespace(control=None))

    assert deleted == ["r1"]
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]
    assert "Biedronka" not in texts


async def test_rules_say_so_when_the_server_is_unreachable(monkeypatch):
    import httpx

    async def _boom(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("api_client._client", lambda: SimpleNamespace(get=_boom))
    # Straight through `api_client`, so the real except/`_note_failure` path runs.
    monkeypatch.setattr("views.rules.get_categorization_rules", api_client.get_categorization_rules)

    view = await VIEW_BUILDERS["/rules"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert any("Couldn't reach the server" in t for t in texts)


async def test_no_rules_is_not_an_outage(monkeypatch):
    """The gateway answers "no rules" with 404, which must not raise a banner."""
    import httpx

    async def _not_found(*args, **kwargs):
        request = httpx.Request("GET", "http://test/budget/categorization-rules")
        raise httpx.HTTPStatusError("nope", request=request, response=httpx.Response(404, request=request))

    monkeypatch.setattr("api_client._client", lambda: SimpleNamespace(get=_not_found))
    monkeypatch.setattr("views.rules.get_categorization_rules", api_client.get_categorization_rules)

    view = await VIEW_BUILDERS["/rules"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert not any("Couldn't reach the server" in t for t in texts)
    assert any(t.startswith("No rules yet.") for t in texts)


# --- First run: a checklist that reads the budget instead of declaring it ----


def _stub_first_run(monkeypatch, *, accounts=(), statements=(), allocations=()):
    async def _accounts():
        return list(accounts)

    async def _statements(account_id=None):
        return list(statements)

    async def _allocations(envelope_id=None):
        return list(allocations)

    monkeypatch.setattr("views.first_run.get_accounts", _accounts)
    monkeypatch.setattr("views.first_run.get_statements", _statements)
    monkeypatch.setattr("views.first_run.get_envelope_allocations", _allocations)


_AN_ACCOUNT = [{"id": "acc-1", "name": "ING", "currency": "PLN"}]
_A_STATEMENT = [{"id": "st-1", "account_id": "acc-1", "filename": "jan.csv", "imported_at": "2026-08-01T10:00:00"}]


def _is_primary(page, button: ft.Container) -> bool:
    from theme import palette

    return button.bgcolor == palette(page).brand


async def test_first_run_starts_at_step_one_on_an_empty_budget(monkeypatch):
    _stub_first_run(monkeypatch)

    view = await VIEW_BUILDERS["/first-run"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert "STEP 1 OF 3" in texts  # the eyebrow renders uppercase


async def test_first_run_points_at_the_step_you_are_actually_on(monkeypatch):
    """It said "Step 1 of 3" forever, with step 1 ticked - so the one screen whose
    entire job is telling you where you are, could not."""
    _stub_first_run(monkeypatch, accounts=_AN_ACCOUNT)

    view = await VIEW_BUILDERS["/first-run"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert "STEP 2 OF 3" in texts


async def test_first_run_highlights_the_next_step_not_the_finished_ones(monkeypatch):
    """The mock gave the primary button to *completed* steps, so the screen
    shouted loudest about what you had already done."""
    _stub_first_run(monkeypatch, accounts=_AN_ACCOUNT)

    page = stub_page()
    view = await VIEW_BUILDERS["/first-run"](page)

    assert _is_primary(page, find_button(view, "Import"))
    assert not _is_primary(page, find_button(view, "Add account"))


async def test_assigning_money_this_month_finishes_the_last_step(monkeypatch):
    _stub_first_run(
        monkeypatch,
        accounts=_AN_ACCOUNT,
        statements=_A_STATEMENT,
        allocations=[{"id": "a1", "envelope_id": "env-1", "month": _this_month(1), "assigned_amount": "200.00"}],
    )

    page = stub_page()
    view = await VIEW_BUILDERS["/first-run"](page)
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert "ALL SET" in texts
    # A finished checklist with no way out is a dead end - the mock could never
    # reach this state, so it never needed one.
    assert find_button(view, "Open your budget") is not None


async def test_an_envelope_with_nothing_in_it_is_not_money_with_a_job(monkeypatch):
    """A 0,00 allocation row means an envelope was created, not funded."""
    _stub_first_run(
        monkeypatch,
        accounts=_AN_ACCOUNT,
        statements=_A_STATEMENT,
        allocations=[{"id": "a1", "envelope_id": "env-1", "month": _this_month(1), "assigned_amount": "0"}],
    )

    view = await VIEW_BUILDERS["/first-run"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert "STEP 3 OF 3" in texts


async def test_last_months_assignment_does_not_finish_this_months_step(monkeypatch):
    """The step asks for *this month's* money to have a job."""
    _stub_first_run(
        monkeypatch,
        accounts=_AN_ACCOUNT,
        statements=_A_STATEMENT,
        allocations=[{"id": "a1", "envelope_id": "env-1", "month": _last_month(1), "assigned_amount": "500.00"}],
    )

    view = await VIEW_BUILDERS["/first-run"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert "STEP 3 OF 3" in texts


async def test_first_run_says_so_when_the_server_is_unreachable(monkeypatch):
    """Every step reads as undone when nothing can be fetched, and on this screen
    that invites setting an already-working budget up a second time."""
    import httpx

    async def _boom(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("api_client._client", lambda: SimpleNamespace(get=_boom))
    # Straight through `api_client`, so the real except/`_note_failure` path runs.
    monkeypatch.setattr("views.first_run.get_accounts", api_client.get_accounts)

    view = await VIEW_BUILDERS["/first-run"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert any("Couldn't reach the server" in t for t in texts)


async def test_an_empty_budget_is_not_an_outage(monkeypatch):
    _stub_first_run(monkeypatch)

    view = await VIEW_BUILDERS["/first-run"](stub_page())
    texts = [c.value or "" for c in walk(view) if isinstance(c, ft.Text)]

    assert not any("Couldn't reach the server" in t for t in texts)


# --- Transactions: refreshing a filter must not make the table jump ---------


def _stub_transactions(monkeypatch, rows):
    async def _payees():
        return [{"id": "p1", "name": "Biedronka"}]

    async def _accounts():
        return [{"id": "acc-1", "name": "ING", "currency": "PLN"}]

    async def _envelopes():
        return [{"id": "env-1", "name": "Groceries", "category_group_id": "cg-1", "target_amount": None}]

    async def _transactions(**kwargs):
        return list(rows), len(rows)

    monkeypatch.setattr("views.transactions.get_payees", _payees)
    monkeypatch.setattr("views.transactions.get_accounts", _accounts)
    monkeypatch.setattr("views.transactions.get_envelopes", _envelopes)
    monkeypatch.setattr("views.transactions.get_transactions_page", _transactions)


_TX_ROW = {
    "id": "t1",
    "envelope_id": "env-1",
    "payee_id": "p1",
    "account_id": "acc-1",
    "amount": "-30.00",
    "transaction_date": "2026-08-01",
    "categorization_source": "rule",
}


def _list_holder(view) -> ft.Container:
    """The panel the table lives in - the only container that animates opacity."""
    return next(
        c for c in walk(view) if isinstance(c, ft.Container) and getattr(c, "animate_opacity", None) is not None
    )


def _range_dropdown(view) -> ft.Dropdown:
    return next(
        c for c in walk(view) if isinstance(c, ft.Dropdown) and any(o.key == "last3" for o in (c.options or []))
    )


async def test_filter_refresh_dims_the_table_instead_of_swapping_it(monkeypatch):
    """The reported jump: the old code replaced the table with a fixed 6-row
    skeleton, so a longer table collapsed and grew back inside a frame or two.
    Against a fast API the rows must stay mounted the whole time - only the
    opacity changes, so nothing on the page moves."""
    _stub_transactions(monkeypatch, [_TX_ROW])
    page = stub_page()
    view = await VIEW_BUILDERS["/transactions"](page)
    holder = _list_holder(view)

    def showing_real_rows() -> bool:
        return any(isinstance(c, ft.Text) and c.value == "Biedronka" for c in walk(holder))

    snapshots: list[tuple[float, bool]] = []
    page.update = lambda: snapshots.append((holder.opacity, showing_real_rows()))

    _range_dropdown(view).on_select(SimpleNamespace(control=SimpleNamespace(value="last3")))
    await page.last_task

    assert snapshots, "refresh never repainted"
    assert all(real for _, real in snapshots), "the table was swapped out mid-refresh"
    assert snapshots[0][0] < 1, "the table was never dimmed"
    assert holder.opacity == 1


async def test_a_slow_refresh_still_falls_back_to_a_skeleton(monkeypatch):
    """Dimming alone reads as frozen once a fetch takes real time, so the
    skeleton is kept for that case - just gated behind a delay."""
    _stub_transactions(monkeypatch, [_TX_ROW])
    monkeypatch.setattr("views.transactions._SKELETON_AFTER_S", 0.01)

    # A fetch that actually takes time. Instant stubs are not enough: they finish
    # inside the single loop iteration `asyncio.wait` yields for, so the timeout
    # is never reached - which is precisely the fast path the other test covers.
    async def _slow_transactions(**kwargs):
        await asyncio.sleep(0.05)
        return [_TX_ROW], 1

    monkeypatch.setattr("views.transactions.get_transactions_page", _slow_transactions)

    page = stub_page()
    view = await VIEW_BUILDERS["/transactions"](page)
    holder = _list_holder(view)

    seen_skeleton = False

    def on_update():
        nonlocal seen_skeleton
        if not any(isinstance(c, ft.Text) and c.value == "Biedronka" for c in walk(holder)):
            seen_skeleton = True

    page.update = on_update

    _range_dropdown(view).on_select(SimpleNamespace(control=SimpleNamespace(value="last3")))
    await page.last_task

    assert seen_skeleton
    assert holder.opacity == 1


async def test_the_skeleton_keeps_the_table_header_and_row_count(monkeypatch):
    """A skeleton of a different size is its own jump. It carries the real header
    and as many rows as were on screen."""
    from theme import palette
    from views.transactions import _loading_rows, _table_columns

    p = palette(stub_page())
    skeleton = _loading_rows(p, "desktop", count=9)
    labels = [c.value for c in walk(skeleton) if isinstance(c, ft.Text)]

    assert labels == [label.upper() for label, _, _ in _table_columns("desktop")]
    placeholder_rows = [c for c in walk(skeleton) if isinstance(c, ft.Container) and c.border is not None]
    assert len(placeholder_rows) >= 9


async def test_transactions_first_load_honours_the_range_dropdown(monkeypatch):
    """The screen must not open in a state its own controls contradict.

    It used to load with a bare `get_transactions()` while the range dropdown
    already read "This month", so the table showed every transaction ever - and
    the first touch of *any* filter applied the date range as a side effect,
    making the account dropdown look like it also changed the period."""
    from utils import range_to_dates

    calls: list[dict] = []

    async def _recording_transactions(**kwargs):
        calls.append(kwargs)
        return [], 0

    _stub_transactions(monkeypatch, [])
    monkeypatch.setattr("views.transactions.get_transactions_page", _recording_transactions)

    view = await VIEW_BUILDERS["/transactions"](stub_page())

    date_from, date_to = range_to_dates("this")
    assert calls, "no transactions were fetched on load"
    assert calls[0]["date_from"] == date_from
    assert calls[0]["date_to"] == date_to
    assert _range_dropdown(view).value == "this"


async def test_changing_one_filter_leaves_the_others_alone(monkeypatch):
    """Picking an account must not quietly move the date range too - the two
    fetches now come from one code path, so they cannot drift."""
    calls: list[dict] = []

    async def _recording_transactions(**kwargs):
        calls.append(kwargs)
        return [], 0

    _stub_transactions(monkeypatch, [])
    monkeypatch.setattr("views.transactions.get_transactions_page", _recording_transactions)

    page = stub_page()
    view = await VIEW_BUILDERS["/transactions"](page)
    _range_dropdown(view).on_select(SimpleNamespace(control=SimpleNamespace(value="year")))
    await page.last_task

    account = next(
        c for c in walk(view) if isinstance(c, ft.Dropdown) and any(o.key == "acc-1" for o in (c.options or []))
    )
    account.on_select(SimpleNamespace(control=SimpleNamespace(value="acc-1")))
    await page.last_task

    assert calls[-1]["account_id"] == "acc-1"
    # The range picked earlier survives the account change.
    assert calls[-1]["date_from"] == calls[-2]["date_from"]


# --- Transactions: pagination ----------------------------------------------


def _stub_paged_transactions(monkeypatch, total: int):
    """A server holding `total` rows, handing out one page at a time."""
    rows = [
        {
            "id": f"t{i}",
            "envelope_id": "env-1",
            "payee_id": "p1",
            "account_id": "acc-1",
            "amount": "-1.00",
            "transaction_date": "2026-08-01",
            "categorization_source": "rule",
        }
        for i in range(total)
    ]
    calls: list[dict] = []

    async def _page(**kwargs):
        calls.append(kwargs)
        skip, limit = kwargs.get("skip", 0), kwargs.get("limit", 50)
        return rows[skip : skip + limit], total

    _stub_transactions(monkeypatch, [])
    monkeypatch.setattr("views.transactions.get_transactions_page", _page)
    return calls


def _summary(view) -> str:
    """The count line above the table. Matched on its wording rather than its
    position, so it survives layout changes - hence the several shapes it can
    take (a page range, a search result, or nothing at all)."""
    wordings = ("transactions", "on this page", "No transactions")
    return next(
        (
            c.value
            for c in walk(view)
            if isinstance(c, ft.Text) and any(w in (c.value or "") for w in wordings)
        ),
        "",
    )


async def test_summary_reports_the_real_total_not_the_page_size(monkeypatch):
    """The reported bug: with 410 matches the screen said "100 of 100", which
    reads as "that is everything" while 76% of the data was missing. The total
    now comes from the server's X-Total-Count."""
    from views.transactions import _PAGE_SIZE

    _stub_paged_transactions(monkeypatch, total=410)
    view = await VIEW_BUILDERS["/transactions"](stub_page())

    assert _summary(view) == f"1–{_PAGE_SIZE} of 410 transactions"


async def test_paging_forward_asks_for_the_next_slice(monkeypatch):
    from views.transactions import _PAGE_SIZE

    calls = _stub_paged_transactions(monkeypatch, total=120)
    page = stub_page()
    view = await VIEW_BUILDERS["/transactions"](page)

    find_button(view, "Next →").on_click(SimpleNamespace(control=None))
    await page.last_task

    assert calls[-1]["skip"] == _PAGE_SIZE
    assert _summary(view) == f"{_PAGE_SIZE + 1}–{2 * _PAGE_SIZE} of 120 transactions"


async def test_the_pager_stops_at_both_ends(monkeypatch):
    _stub_paged_transactions(monkeypatch, total=120)
    page = stub_page()
    view = await VIEW_BUILDERS["/transactions"](page)

    # First page: Previous is disabled, so it carries no handler at all.
    assert find_button(view, "← Previous") is None
    assert find_button(view, "Next →") is not None

    for _ in range(5):  # more clicks than there are pages
        button = find_button(view, "Next →")
        if button is None:
            break
        button.on_click(SimpleNamespace(control=None))
        await page.last_task

    assert find_button(view, "Next →") is None  # last page
    assert _summary(view) == "101–120 of 120 transactions"


async def test_no_pager_when_everything_fits_on_one_page(monkeypatch):
    _stub_paged_transactions(monkeypatch, total=12)
    view = await VIEW_BUILDERS["/transactions"](stub_page())

    assert find_button(view, "Next →") is None
    assert find_button(view, "← Previous") is None
    assert _summary(view) == "1–12 of 12 transactions"


async def test_changing_a_filter_returns_to_the_first_page(monkeypatch):
    """Narrowing the results while on page 3 would land past the end of the new
    result set, which looks exactly like "the filter matched nothing"."""
    calls = _stub_paged_transactions(monkeypatch, total=200)
    page = stub_page()
    view = await VIEW_BUILDERS["/transactions"](page)

    find_button(view, "Next →").on_click(SimpleNamespace(control=None))
    await page.last_task
    assert calls[-1]["skip"] > 0

    _range_dropdown(view).on_select(SimpleNamespace(control=SimpleNamespace(value="year")))
    await page.last_task
    assert calls[-1]["skip"] == 0


async def test_search_is_sent_to_the_server_not_applied_to_the_page(monkeypatch):
    """The reported bug: search only looked at the 50 rows already loaded, so it
    answered "which of these match" instead of "which of my transactions match"."""
    calls = _stub_paged_transactions(monkeypatch, total=410)
    monkeypatch.setattr("views.transactions._SEARCH_DEBOUNCE_S", 0)
    page = stub_page()
    view = await VIEW_BUILDERS["/transactions"](page)

    search = next(c for c in walk(view) if isinstance(c, ft.TextField) and c.on_change is not None)
    search.on_change(SimpleNamespace(control=SimpleNamespace(value="Biedronka")))
    await page.last_task

    assert calls[-1]["search"] == "Biedronka"


async def test_searching_returns_to_the_first_page(monkeypatch):
    calls = _stub_paged_transactions(monkeypatch, total=410)
    monkeypatch.setattr("views.transactions._SEARCH_DEBOUNCE_S", 0)
    page = stub_page()
    view = await VIEW_BUILDERS["/transactions"](page)

    find_button(view, "Next →").on_click(SimpleNamespace(control=None))
    await page.last_task
    assert calls[-1]["skip"] > 0

    search = next(c for c in walk(view) if isinstance(c, ft.TextField) and c.on_change is not None)
    search.on_change(SimpleNamespace(control=SimpleNamespace(value="Lidl")))
    await page.last_task
    assert calls[-1]["skip"] == 0


async def test_typing_fires_one_search_not_one_per_keystroke(monkeypatch):
    """`on_change` fires per character and each search is now a round trip, so a
    six-letter payee name would be six queries, five of them already obsolete."""
    calls = _stub_paged_transactions(monkeypatch, total=410)
    page = stub_page()
    view = await VIEW_BUILDERS["/transactions"](page)
    before = len(calls)

    search = next(c for c in walk(view) if isinstance(c, ft.TextField) and c.on_change is not None)
    tasks = []
    for typed in ["L", "Li", "Lid", "Lidl"]:
        search.on_change(SimpleNamespace(control=SimpleNamespace(value=typed)))
        tasks.append(page.last_task)
    await asyncio.gather(*tasks)

    searched = [c for c in calls[before:] if c.get("search")]
    assert len(searched) == 1
    assert searched[0]["search"] == "Lidl"
