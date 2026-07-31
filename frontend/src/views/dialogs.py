"""Modal dialogs - Assign money / Move money / Add envelope / Add category
group / Add rule / Add account / Add transaction. Confirm is a stub that just
closes the dialog for all of these except "Add transaction" (no data is
actually assigned/moved/created) - that one reads the form back out and calls
the API; see `_parse_amount`/`_parse_date`/`new_transaction_dialog` below.
"""

import re
from collections.abc import Awaitable, Callable
from datetime import date

import flet as ft

import api_client
from components.modal_dialog import ModalField, build_modal
from mock_data import all_envelopes
from theme import palette, text_style

_TEXT_STYLE = "height:40px;padding:0 12px;background:var(--sf);border:1px solid var(--line);border-radius:9px;font:400 13.5px/1 'IBM Plex Sans',sans-serif"

_AMOUNT_RE = re.compile(r"^-?\d+(\.\d{1,2})?$")


def _envelope_options() -> list[tuple[str, str]]:
    return [(e.id, f"{e.group_name} · {e.name}") for e in all_envelopes()]


def _close(page: ft.Page):
    def handler(e: ft.ControlEvent) -> None:
        page.pop_dialog()

    return handler


def assign_dialog(page: ft.Page) -> ft.AlertDialog:
    p = palette(page)
    close = _close(page)
    dialog, _ = build_modal(
        p,
        title="Assign money",
        subtitle='Move money out of "left to assign" into an envelope.',
        fields=[
            ModalField("Envelope", "select", options=_envelope_options()),
            ModalField("Amount to assign", "input", placeholder="0,00", amount_style=True, hint="You have 137,40 € left to assign."),
        ],
        cta_label="Assign",
        preview=("Left to assign afterwards", "137,40 €"),
        on_close=close,
        on_confirm=close,
    )
    return dialog


def move_dialog(page: ft.Page) -> ft.AlertDialog:
    p = palette(page)
    close = _close(page)
    opts = _envelope_options()
    dialog, _ = build_modal(
        p,
        title="Move money",
        subtitle="Take from one envelope and give it to another. Nothing leaves your budget.",
        fields=[
            ModalField("From", "select", options=opts),
            ModalField("To", "select", options=opts),
            ModalField("Amount", "input", placeholder="0,00", amount_style=True),
        ],
        cta_label="Move money",
        preview=("After the move, this envelope will have", "0,00 €"),
        on_close=close,
        on_confirm=close,
    )
    return dialog


def new_envelope_dialog(page: ft.Page) -> ft.AlertDialog:
    p = palette(page)
    close = _close(page)
    from mock_data import GROUPS

    dialog, _ = build_modal(
        p,
        title="Add envelope",
        subtitle="Envelopes hold the money you plan to spend on one thing.",
        fields=[
            ModalField("Name", "input", placeholder="e.g. Pharmacy"),
            ModalField("Category group", "select", options=[(g.id, g.name) for g in GROUPS]),
            ModalField("Monthly target (optional)", "input", placeholder="0,00", hint="Envelo will suggest filling to this amount each month."),
        ],
        cta_label="Add envelope",
        on_close=close,
        on_confirm=close,
    )
    return dialog


def new_group_dialog(page: ft.Page) -> ft.AlertDialog:
    p = palette(page)
    close = _close(page)
    dialog, _ = build_modal(
        p,
        title="Add category group",
        subtitle="Groups organise envelopes on the budget screen.",
        fields=[ModalField("Group name", "input", placeholder="e.g. Household", hint="Groups keep the envelope list scannable.")],
        cta_label="Add group",
        on_close=close,
        on_confirm=close,
    )
    return dialog


def new_rule_dialog(page: ft.Page) -> ft.AlertDialog:
    p = palette(page)
    close = _close(page)
    dialog, _ = build_modal(
        p,
        title="Add rule",
        subtitle="Rules categorize matching transactions the moment you import them.",
        fields=[
            ModalField("When", "select", options=[("payee", "Payee contains"), ("desc", "Description contains"), ("amount", "Amount equals")]),
            ModalField("Pattern", "input", placeholder="e.g. Albert Heijn", hint="Not case-sensitive. Rules run top to bottom."),
            ModalField("Put it in", "select", options=_envelope_options()),
        ],
        cta_label="Add rule",
        on_close=close,
        on_confirm=close,
    )
    return dialog


def new_account_dialog(page: ft.Page) -> ft.AlertDialog:
    p = palette(page)
    close = _close(page)
    dialog, _ = build_modal(
        p,
        title="Add account",
        subtitle="Where your money actually sits. Statements are imported into an account.",
        fields=[
            ModalField("Name", "input", placeholder="e.g. ING Checking"),
            ModalField("Type", "select", options=[("checking", "Checking"), ("savings", "Savings"), ("credit", "Credit card"), ("cash", "Cash")]),
            ModalField(
                "Currency",
                "select",
                options=[("EUR", "Euro (EUR)"), ("USD", "US dollar (USD)"), ("GBP", "Pound (GBP)"), ("PLN", "Złoty (PLN)")],
            ),
        ],
        cta_label="Add account",
        on_close=close,
        on_confirm=close,
    )
    return dialog


def _parse_amount(raw: str) -> str | None:
    """EU-style ("42,50", "-42,50") -> a numeric string pydantic's Decimal can
    parse ("42.50"), or None if empty/malformed/zero."""
    text = raw.strip()
    if not text:
        return None
    text = text.replace(".", "").replace(",", ".")
    if not _AMOUNT_RE.match(text):
        return None
    if float(text) == 0:
        return None
    return text


def _parse_date(raw: str) -> str | None:
    text = raw.strip()
    try:
        date.fromisoformat(text)
    except ValueError:
        return None
    return text


def new_transaction_dialog(
    page: ft.Page,
    *,
    accounts: list[dict],
    envelopes: list[dict],
    payees: list[dict],
    on_created: Callable[[], Awaitable[None]],
) -> ft.AlertDialog:
    p = palette(page)
    close = _close(page)

    account_options = [(a["id"], a["name"]) for a in accounts]
    envelope_options = [(e["id"], e["name"]) for e in envelopes]
    currency_by_account = {a["id"]: a["currency"] for a in accounts}

    error_text = ft.Text("", style=text_style(12, 500, p.over_ink))

    async def _resolve_payee_id(name: str) -> str | None:
        """Match an existing payee by name (case-insensitive) instead of always
        creating a new one - `POST /budget/payees` has no dedupe of its own."""
        match = next((pe for pe in payees if pe["name"].lower() == name.lower()), None)
        if match is not None:
            return match["id"]
        created = await api_client.create_payee(name)
        return created["id"] if created is not None else None

    async def handle_confirm(e: ft.ControlEvent) -> None:
        error_text.value = ""

        account_id = controls["Account"].value
        if not account_id:
            error_text.value = "Add an account first."
            page.update()
            return

        amount = _parse_amount(controls["Amount"].value)
        if amount is None:
            error_text.value = "Enter a valid, non-zero amount, e.g. 42,50."
            page.update()
            return

        transaction_date = _parse_date(controls["Date"].value)
        if transaction_date is None:
            error_text.value = "Use YYYY-MM-DD format for the date."
            page.update()
            return

        payee_id = None
        payee_text = controls["Payee"].value.strip()
        if payee_text:
            payee_id = await _resolve_payee_id(payee_text)
            if payee_id is None:
                error_text.value = "Couldn't save that payee — try again."
                page.update()
                return

        payload = {
            "account_id": account_id,
            "envelope_id": controls["Envelope"].value or None,
            "payee_id": payee_id,
            "amount": amount,
            "currency": currency_by_account[account_id],
            "transaction_date": transaction_date,
            "categorization_source": "manual",
        }
        result = await api_client.create_transaction(payload)
        if result is None:
            error_text.value = "Couldn't save — try again."
            page.update()
            return

        page.pop_dialog()
        await on_created()

    dialog, controls = build_modal(
        p,
        title="Add transaction",
        subtitle='Entered by hand — it will be badged "manual".',
        fields=[
            ModalField(
                "Payee", "input", placeholder="Start typing — Albert Heijn, Jumbo…", hint="Matches an existing payee, or adds a new one."
            ),
            ModalField("Envelope", "select", options=envelope_options),
            ModalField("Account", "select", options=account_options),
            ModalField("Amount", "input", placeholder="0,00"),
            ModalField("Date", "date", value=date.today().isoformat()),
        ],
        cta_label="Save transaction",
        extra=error_text,
        page=page,
        on_close=close,
        on_confirm=handle_confirm,
    )
    return dialog
