from types import SimpleNamespace

import flet as ft
import pytest

from utils import parse_amount, parse_date
from views.dialogs import new_transaction_dialog


def _stub_page() -> SimpleNamespace:
    page = SimpleNamespace(
        theme_mode=ft.ThemeMode.LIGHT,
        platform_brightness=ft.Brightness.LIGHT,
        width=1280,
        opened_dialogs=[],
    )
    page.show_dialog = page.opened_dialogs.append
    page.pop_dialog = lambda: page.opened_dialogs.pop() if page.opened_dialogs else None
    page.update = lambda: None
    return page


def _walk(control):
    yield control
    for child in list(getattr(control, "controls", None) or []):
        yield from _walk(child)
    for slot in ("content", "title", "subtitle"):
        child = getattr(control, slot, None)
        if isinstance(child, ft.Control):
            yield from _walk(child)


def _field_control(dialog: ft.AlertDialog, label: str) -> ft.Control:
    """Field wrapper columns are [label_field(label.upper()), control, hint?] -
    find the labeled column, then the TextField/Dropdown inside it (nested one
    level deeper for a "date" field, which wraps its TextField + a calendar
    icon in a Row) - the same object `handle_confirm`'s closure reads from."""
    for c in _walk(dialog):
        if isinstance(c, ft.Column) and len(c.controls) >= 2:
            first = c.controls[0]
            if isinstance(first, ft.Text) and first.value == label.upper():
                for inner in _walk(c.controls[1]):
                    if isinstance(inner, (ft.TextField, ft.Dropdown)):
                        return inner
    raise AssertionError(f"no field labeled {label!r} found in dialog")


# `parse_amount` itself is covered in tests/test_utils.py. What matters here is
# that each dialog applies its own rule on top of it: zero parses fine now (an
# envelope can be un-assigned), so any dialog for which zero is meaningless has
# to reject it explicitly.
@pytest.mark.parametrize("raw", ["0", "0,00"])
def test_parse_amount_accepts_zero_so_dialogs_must_guard_it(raw):
    assert parse_amount(raw) is not None
    assert float(parse_amount(raw)) == 0


def test_parse_date_accepts_iso_format():
    assert parse_date("2026-07-24") == "2026-07-24"


@pytest.mark.parametrize("raw", ["", "24-07-2026", "2026/07/24", "not a date"])
def test_parse_date_rejects_invalid_input(raw):
    assert parse_date(raw) is None


_ACCOUNTS = [{"id": "acc-1", "name": "Checking", "currency": "EUR"}]
_ENVELOPES = [{"id": "env-1", "name": "Groceries"}]
_PAYEES = [{"id": "pay-1", "name": "Albert Heijn"}]


async def test_confirm_creates_transaction_closes_dialog_and_refreshes(monkeypatch):
    calls = {"payload": None, "refreshed": False}

    async def fake_create_transaction(payload):
        calls["payload"] = payload
        return {"id": "tx-new"}

    async def fake_on_created():
        calls["refreshed"] = True

    monkeypatch.setattr("api_client.create_transaction", fake_create_transaction)

    page = _stub_page()
    dialog = new_transaction_dialog(
        page, accounts=_ACCOUNTS, envelopes=_ENVELOPES, payees=_PAYEES, on_created=fake_on_created
    )
    page.show_dialog(dialog)

    _field_control(dialog, "Account").value = "acc-1"
    _field_control(dialog, "Envelope").value = "env-1"
    _field_control(dialog, "Payee").value = "Albert Heijn"
    _field_control(dialog, "Amount").value = "-42,50"
    _field_control(dialog, "Date").value = "2026-07-24"

    confirm = dialog.actions[1].on_click
    await confirm(SimpleNamespace(control=dialog.actions[1]))

    assert calls["payload"] == {
        "account_id": "acc-1",
        "envelope_id": "env-1",
        "payee_id": "pay-1",
        "amount": "-42.50",
        "currency": "EUR",
        "transaction_date": "2026-07-24",
        "categorization_source": "manual",
    }
    assert calls["refreshed"] is True
    assert page.opened_dialogs == []


async def _noop():
    pass


async def test_confirm_matches_existing_payee_case_insensitively_without_creating(monkeypatch):
    create_calls = []

    async def fake_create_payee(name):
        create_calls.append(name)
        return {"id": "should-not-be-used"}

    async def fake_create_transaction(payload):
        return {"id": "tx-new"}

    monkeypatch.setattr("api_client.create_payee", fake_create_payee)
    monkeypatch.setattr("api_client.create_transaction", fake_create_transaction)

    page = _stub_page()
    dialog = new_transaction_dialog(
        page, accounts=_ACCOUNTS, envelopes=_ENVELOPES, payees=_PAYEES, on_created=_noop
    )
    page.show_dialog(dialog)

    _field_control(dialog, "Account").value = "acc-1"
    _field_control(dialog, "Payee").value = "albert heijn"  # different case, same name
    _field_control(dialog, "Amount").value = "10"
    _field_control(dialog, "Date").value = "2026-07-24"

    confirm = dialog.actions[1].on_click
    await confirm(SimpleNamespace(control=dialog.actions[1]))

    assert create_calls == []


async def test_confirm_creates_a_new_payee_when_no_existing_match(monkeypatch):
    async def fake_create_payee(name):
        assert name == "New Shop"
        return {"id": "pay-new"}

    calls = {"payload": None}

    async def fake_create_transaction(payload):
        calls["payload"] = payload
        return {"id": "tx-new"}

    monkeypatch.setattr("api_client.create_payee", fake_create_payee)
    monkeypatch.setattr("api_client.create_transaction", fake_create_transaction)

    page = _stub_page()
    dialog = new_transaction_dialog(
        page, accounts=_ACCOUNTS, envelopes=_ENVELOPES, payees=_PAYEES, on_created=_noop
    )
    page.show_dialog(dialog)

    _field_control(dialog, "Account").value = "acc-1"
    _field_control(dialog, "Payee").value = "New Shop"
    _field_control(dialog, "Amount").value = "10"
    _field_control(dialog, "Date").value = "2026-07-24"

    confirm = dialog.actions[1].on_click
    await confirm(SimpleNamespace(control=dialog.actions[1]))

    assert calls["payload"]["payee_id"] == "pay-new"


async def test_confirm_blocks_submission_on_invalid_amount(monkeypatch):
    called = {"create": False}

    async def fake_create_transaction(payload):
        called["create"] = True
        return {"id": "tx-new"}

    monkeypatch.setattr("api_client.create_transaction", fake_create_transaction)

    page = _stub_page()

    async def fake_on_created():
        pass

    dialog = new_transaction_dialog(
        page, accounts=_ACCOUNTS, envelopes=_ENVELOPES, payees=_PAYEES, on_created=fake_on_created
    )
    page.show_dialog(dialog)

    _field_control(dialog, "Account").value = "acc-1"
    _field_control(dialog, "Amount").value = "0"
    _field_control(dialog, "Date").value = "2026-07-24"

    confirm = dialog.actions[1].on_click
    await confirm(SimpleNamespace(control=dialog.actions[1]))

    assert called["create"] is False
    assert page.opened_dialogs == [dialog]
    error_text = next(c for c in _walk(dialog) if isinstance(c, ft.Text) and "non-zero" in c.value.lower())
    assert error_text.value
