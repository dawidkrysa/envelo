"""Modal dialogs - Assign money / Move money / Add envelope / Add category
group / Add rule / Add account / Add transaction. Presentation only: Confirm
just closes the dialog, per the brief (no data is actually assigned, moved or
created).
"""

import flet as ft

from components.modal_dialog import ModalField, build_modal
from mock_data import ACCOUNTS, all_envelopes
from theme import palette

_TEXT_STYLE = "height:40px;padding:0 12px;background:var(--sf);border:1px solid var(--line);border-radius:9px;font:400 13.5px/1 'IBM Plex Sans',sans-serif"


def _envelope_options() -> list[tuple[str, str]]:
    return [(e.id, f"{e.group_name} · {e.name}") for e in all_envelopes()]


def _close(page: ft.Page):
    def handler(e: ft.ControlEvent) -> None:
        page.pop_dialog()

    return handler


def assign_dialog(page: ft.Page) -> ft.AlertDialog:
    p = palette(page)
    close = _close(page)
    return build_modal(
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


def move_dialog(page: ft.Page) -> ft.AlertDialog:
    p = palette(page)
    close = _close(page)
    opts = _envelope_options()
    return build_modal(
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


def new_envelope_dialog(page: ft.Page) -> ft.AlertDialog:
    p = palette(page)
    close = _close(page)
    from mock_data import GROUPS

    return build_modal(
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


def new_group_dialog(page: ft.Page) -> ft.AlertDialog:
    p = palette(page)
    close = _close(page)
    return build_modal(
        p,
        title="Add category group",
        subtitle="Groups organise envelopes on the budget screen.",
        fields=[ModalField("Group name", "input", placeholder="e.g. Household", hint="Groups keep the envelope list scannable.")],
        cta_label="Add group",
        on_close=close,
        on_confirm=close,
    )


def new_rule_dialog(page: ft.Page) -> ft.AlertDialog:
    p = palette(page)
    close = _close(page)
    return build_modal(
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


def new_account_dialog(page: ft.Page) -> ft.AlertDialog:
    p = palette(page)
    close = _close(page)
    return build_modal(
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


def new_transaction_dialog(page: ft.Page) -> ft.AlertDialog:
    p = palette(page)
    close = _close(page)
    return build_modal(
        p,
        title="Add transaction",
        subtitle='Entered by hand — it will be badged "manual".',
        fields=[
            ModalField("Payee", "input", placeholder="Start typing — Albert Heijn, Jumbo…", hint="Autocompletes from your payee list."),
            ModalField("Envelope", "select", options=_envelope_options()),
            ModalField("Account", "select", options=[(a, a) for a in ACCOUNTS]),
            ModalField("Amount", "input", placeholder="0,00", amount_style=True),
            ModalField("Date", "input", placeholder="2026-07-24"),
        ],
        cta_label="Save transaction",
        on_close=close,
        on_confirm=close,
    )
