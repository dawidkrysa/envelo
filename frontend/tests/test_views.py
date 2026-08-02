"""Unit tests for the view builders.

Each builder must return an ft.View for its own route without touching the
network or mutating anything - a stub stands in for the page.
"""

import asyncio
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
        last_task=None,
    )
    page.show_dialog = page.opened_dialogs.append
    page.pop_dialog = lambda: page.opened_dialogs.pop() if page.opened_dialogs else None

    session_data: dict = {}
    page.session = SimpleNamespace(get=session_data.get, set=session_data.__setitem__)

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
    """Same no-network contract as `stub_transactions_api` above, for `/envelopes`."""
    monkeypatch.setattr("views.envelopes.get_envelopes", _empty_list)
    monkeypatch.setattr("views.envelopes.get_category_groups", _empty_list)
    monkeypatch.setattr("views.envelopes.get_envelope_allocations", _empty_list)
    monkeypatch.setattr("views.envelopes.get_spent_by_envelope", _empty_map)
    monkeypatch.setattr("views.envelopes.get_to_assign", _zero)


@pytest.fixture(autouse=True)
def stub_dashboard_api(monkeypatch):
    """Same no-network contract as `stub_transactions_api` above, for `/dashboard`."""
    monkeypatch.setattr("views.dashboard.get_envelopes", _empty_list)
    monkeypatch.setattr("views.dashboard.get_envelope_allocations", _empty_list)
    monkeypatch.setattr("views.dashboard.get_transactions", _empty_list)
    monkeypatch.setattr("views.dashboard.get_payees", _empty_list)
    monkeypatch.setattr("views.dashboard.get_spent_by_envelope", _empty_map)
    monkeypatch.setattr("views.dashboard.get_to_assign", _zero)


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

    monkeypatch.setattr("views.envelopes.get_envelopes", fake_get_envelopes)
    monkeypatch.setattr("views.envelopes.get_category_groups", fake_get_category_groups)
    monkeypatch.setattr("views.envelopes.get_envelope_allocations", fake_get_envelope_allocations)
    monkeypatch.setattr("views.envelopes.get_spent_by_envelope", fake_get_spent_by_envelope)
    monkeypatch.setattr("views.envelopes.get_to_assign", fake_get_to_assign)

    view = await VIEW_BUILDERS["/envelopes"](stub_page())
    texts = [c.value for c in walk(view) if isinstance(c, ft.Text)]

    assert "Groceries" in texts
    assert f"{format_money(15)} over" in texts  # spent 65 - assigned 50 -> "over" state_label
    assert format_money(42.5) in texts  # "Left to assign" stat, from get_to_assign()


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

    monkeypatch.setattr("views.envelopes.get_envelopes", fake_get_envelopes)
    monkeypatch.setattr("views.envelopes.get_category_groups", fake_get_category_groups)
    monkeypatch.setattr("views.envelopes.get_envelope_allocations", fake_get_envelope_allocations)
    monkeypatch.setattr("views.envelopes.get_spent_by_envelope", fake_get_spent_by_envelope)
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

    monkeypatch.setattr("views.envelopes.get_envelopes", fake_get_envelopes)
    monkeypatch.setattr("views.envelopes.get_category_groups", fake_get_category_groups)
    monkeypatch.setattr("views.envelopes.get_envelope_allocations", fake_get_envelope_allocations)
    monkeypatch.setattr("views.envelopes.get_spent_by_envelope", fake_get_spent_by_envelope)
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

    monkeypatch.setattr("views.envelopes.get_envelopes", fake_get_envelopes)
    monkeypatch.setattr("views.envelopes.get_category_groups", fake_get_category_groups)
    monkeypatch.setattr("views.envelopes.get_envelope_allocations", fake_get_envelope_allocations)
    monkeypatch.setattr("views.envelopes.get_spent_by_envelope", fake_get_spent_by_envelope)
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

    monkeypatch.setattr("views.envelopes.get_envelopes", fake_get_envelopes)
    monkeypatch.setattr("views.envelopes.get_category_groups", fake_get_category_groups)
    monkeypatch.setattr("views.envelopes.get_envelope_allocations", fake_get_envelope_allocations)
    monkeypatch.setattr("views.envelopes.get_spent_by_envelope", fake_get_spent_by_envelope)
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

    monkeypatch.setattr("views.envelopes.get_envelopes", fake_get_envelopes)
    monkeypatch.setattr("views.envelopes.get_category_groups", fake_get_category_groups)
    monkeypatch.setattr("views.envelopes.get_envelope_allocations", fake_get_envelope_allocations)
    monkeypatch.setattr("views.envelopes.get_spent_by_envelope", fake_get_spent_by_envelope)
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

    monkeypatch.setattr("views.envelopes.get_envelopes", fake_get_envelopes)
    monkeypatch.setattr("views.envelopes.get_category_groups", fake_get_category_groups)
    monkeypatch.setattr("views.envelopes.get_envelope_allocations", fake_get_envelope_allocations)
    monkeypatch.setattr("views.envelopes.get_spent_by_envelope", fake_get_spent_by_envelope)
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
    assert page.session.get("selected_envelope_id") == "env-2"

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

    monkeypatch.setattr("views.envelopes.get_envelopes", fake_get_envelopes)
    monkeypatch.setattr("views.envelopes.get_category_groups", fake_get_category_groups)
    monkeypatch.setattr("views.envelopes.get_envelope_allocations", fake_get_envelope_allocations)
    monkeypatch.setattr("views.envelopes.get_spent_by_envelope", fake_get_spent_by_envelope)
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

    for name, fake in [
        ("get_envelopes", fake_get_envelopes),
        ("get_category_groups", fake_get_category_groups),
        ("get_envelope_allocations", fake_get_envelope_allocations),
        ("get_spent_by_envelope", fake_get_spent_by_envelope),
        ("get_to_assign", fake_get_to_assign),
        ("create_envelope_allocation", fake_create_envelope_allocation),
        ("update_envelope_allocation", fake_update_envelope_allocation),
        ("update_envelope", fake_update_envelope),
    ]:
        monkeypatch.setattr(f"views.envelopes.{name}", fake)
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
    from main import _restore_currency

    page = SimpleNamespace(shared_preferences=SimpleNamespace(get=lambda key: _async_return("gbp")))
    await _restore_currency(page)
    assert current_currency() == "gbp"
    assert CURRENCY_STORAGE_KEY  # the key both sides share


async def test_unreadable_currency_preference_does_not_block_startup():
    from currency import DEFAULT_CURRENCY, current_currency, set_currency
    from main import _restore_currency

    set_currency("usd")

    async def boom(key):
        raise RuntimeError("shared preferences unavailable")

    await _restore_currency(SimpleNamespace(shared_preferences=SimpleNamespace(get=boom)))
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


def _stub_dashboard(monkeypatch, *, envelopes, allocations=(), transactions=(), payees=(), spent=None, to_assign=0.0):
    async def _envelopes():
        return list(envelopes)

    async def _allocations(envelope_id=None):
        return list(allocations)

    async def _transactions(**kwargs):
        return list(transactions)

    async def _payees():
        return list(payees)

    async def _spent(**kwargs):
        return dict(spent or {})

    async def _to_assign():
        return to_assign

    monkeypatch.setattr("views.dashboard.get_spent_by_envelope", _spent)
    monkeypatch.setattr("views.dashboard.get_envelopes", _envelopes)
    monkeypatch.setattr("views.dashboard.get_envelope_allocations", _allocations)
    monkeypatch.setattr("views.dashboard.get_transactions", _transactions)
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
        transactions=[
            {
                "id": "old",
                "envelope_id": "env-1",
                "payee_id": "p1",
                "account_id": "a",
                "amount": "-10.00",
                "transaction_date": "2026-01-02",
                "categorization_source": "rule",
            },
            {
                "id": "new",
                "envelope_id": "env-1",
                "payee_id": "p2",
                "account_id": "a",
                "amount": "-20.00",
                "transaction_date": "2026-08-01",
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

    assert page.session.get("selected_envelope_id") == "env-9"
    assert routed == ["/envelopes/detail"]


async def test_dashboard_survives_a_completely_empty_budget(monkeypatch):
    _stub_dashboard(monkeypatch, envelopes=[])
    view = await VIEW_BUILDERS["/dashboard"](stub_page())
    texts = [c.value for c in walk(view) if isinstance(c, ft.Text)]
    assert "Nothing spent this month yet." in texts
    assert "No transactions imported yet." in texts


async def test_sidebar_attention_badge_counts_real_envelopes(monkeypatch):
    """It was `len(attention_envelopes())` over the static mock, so the badge
    showed the same number forever, right next to real group totals."""
    from theme import palette
    from views.common import category_group_nav

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
    items, attention = await category_group_nav(palette(page), page)

    assert len(items) == 1
    assert attention == 1  # Groceries is over; Rent is untouched


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
