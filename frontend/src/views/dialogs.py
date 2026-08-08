"""Modal dialogs - Assign money / Move money / Add-or-edit envelope / Add
transaction / Add-or-edit rule read the form back out and call the API on
confirm. Add category group and Add account are still stubs (Confirm just
closes) - not wired to the backend yet. See `utils.parse_amount`/
`utils.parse_date` for the shared field-parsing helpers.
"""

from collections.abc import Awaitable, Callable
from datetime import date

import flet as ft

import api_client
from components.button import danger_button
from components.modal_dialog import ModalField, build_modal
from currency import format_money
from theme import palette, text_style
from utils import parse_amount, parse_date, range_to_dates

_TEXT_STYLE = "height:40px;padding:0 12px;background:var(--sf);border:1px solid var(--line);border-radius:9px;font:400 13.5px/1 'IBM Plex Sans',sans-serif"


def _close(page: ft.Page):
    def handler(e: ft.ControlEvent) -> None:
        page.pop_dialog()

    return handler


def assign_dialog(
    page: ft.Page,
    *,
    envelopes: list[dict] | None = None,
    to_assign: float = 0,
    on_assign: Callable[[str, float], Awaitable[None]] | None = None,
    envelope_id: str | None = None,
    current_amount: float | None = None,
) -> ft.AlertDialog:
    """Sets this month's assigned amount for one envelope to an absolute
    value - same "set" semantics as the other assign-amount actions on the
    Envelopes screen (inline edit, Fill all to target, Reset, ...); the
    caller's `on_assign` receives the new absolute amount, not a delta."""
    p = palette(page)
    close = _close(page)
    opts = [(e["id"], e["name"]) for e in (envelopes or [])]
    error_text = ft.Text("", style=text_style(12, 500, p.over_ink))
    amount_value = f"{current_amount:.2f}".replace(".", ",") if current_amount else ""

    async def handle_confirm(e: ft.ControlEvent) -> None:
        error_text.value = ""

        selected_id = controls["Envelope"].value
        if not selected_id:
            error_text.value = "Pick an envelope."
            page.update()
            return

        amount = parse_amount(controls["Amount to assign"].value)
        if amount is None or float(amount) <= 0:
            error_text.value = "Enter a positive amount, e.g. 42,50."
            page.update()
            return

        page.pop_dialog()
        if on_assign is not None:
            await on_assign(selected_id, float(amount))

    dialog, controls = build_modal(
        p,
        title="Assign money",
        subtitle="Set this envelope's assigned amount for this month.",
        fields=[
            ModalField("Envelope", "select", options=opts, value=envelope_id or ""),
            ModalField(
                "Amount to assign",
                "input",
                placeholder="0,00",
                value=amount_value,
                hint=f"You have {format_money(to_assign)} left to assign.",
            ),
        ],
        cta_label="Assign",
        extra=error_text,
        page=page,
        on_close=close,
        on_confirm=handle_confirm,
    )
    return dialog


def move_dialog(
    page: ft.Page,
    *,
    envelopes: list[dict] | None = None,
    on_moved: Callable[[], Awaitable[None]] | None = None,
    from_id: str | None = None,
    to_id: str | None = None,
    amount: float | None = None,
) -> ft.AlertDialog:
    p = palette(page)
    close = _close(page)
    opts = [(e["id"], e["name"]) for e in (envelopes or [])]
    error_text = ft.Text("", style=text_style(12, 500, p.over_ink))

    def _options_excluding(excluded_id: str | None) -> list[tuple[str, str]]:
        return [(v, label) for v, label in opts if v != excluded_id]

    # Resolve concrete defaults ourselves rather than leaving either field
    # empty for select_field()'s own "default to the first option" fallback
    # to handle - if both From and To fell back independently (e.g. this
    # dialog opened from the page header, with no envelope preselected on
    # either side), they could both land on the same first envelope in the
    # list at the same time. Picking To's default only after From's is
    # locked in guarantees they never start out equal.
    default_from = from_id or (opts[0][0] if opts else None)
    default_to = to_id or next((v for v, _ in opts if v != default_from), None)

    async def handle_confirm(e: ft.ControlEvent) -> None:
        error_text.value = ""

        source_id = controls["From"].value
        target_id = controls["To"].value
        if not source_id or not target_id:
            error_text.value = "Pick both envelopes."
            page.update()
            return
        if source_id == target_id:
            error_text.value = "Pick two different envelopes."
            page.update()
            return

        parsed = parse_amount(controls["Amount"].value)
        if parsed is None or float(parsed) <= 0:
            error_text.value = "Enter a positive amount, e.g. 42,50."
            page.update()
            return

        payload = {
            "from_envelope_id": source_id,
            "to_envelope_id": target_id,
            "month": range_to_dates("this")[0].isoformat(),
            "amount": parsed,
        }
        result = await api_client.transfer_envelope_allocation(payload)
        if result is None:
            error_text.value = "Couldn't move that money — try again."
            page.update()
            return

        page.pop_dialog()
        if on_moved is not None:
            await on_moved()

    dialog, controls = build_modal(
        p,
        title="Move money",
        subtitle="Take from one envelope and give it to another. Nothing leaves your budget.",
        fields=[
            ModalField("From", "select", options=_options_excluding(default_to), value=default_from or ""),
            ModalField("To", "select", options=_options_excluding(default_from), value=default_to or ""),
            ModalField(
                "Amount",
                "input",
                placeholder="0,00",
                value=f"{amount:.2f}".replace(".", ",") if amount else "",
            ),
        ],
        cta_label="Move money",
        extra=error_text,
        page=page,
        on_close=close,
        on_confirm=handle_confirm,
    )

    from_dropdown, to_dropdown = controls["From"], controls["To"]

    def _sync_options(_: ft.ControlEvent | None = None) -> None:
        # Keeps each side's list from ever offering the envelope currently
        # picked on the other side - the same-envelope guard in
        # `handle_confirm` above stays as a backstop, but this makes the
        # mistake impossible to make in the first place.
        from_dropdown.options = [
            ft.dropdown.Option(key=v, text=label) for v, label in _options_excluding(to_dropdown.value)
        ]
        to_dropdown.options = [
            ft.dropdown.Option(key=v, text=label) for v, label in _options_excluding(from_dropdown.value)
        ]
        page.update()

    from_dropdown.on_select = _sync_options
    to_dropdown.on_select = _sync_options

    return dialog


def new_envelope_dialog(
    page: ft.Page,
    *,
    category_groups: list[dict] | None = None,
    envelope: dict | None = None,
    default_category_group_id: str | None = None,
    on_saved: Callable[[], Awaitable[None]] | None = None,
) -> ft.AlertDialog:
    """Add and Edit share this one dialog: `envelope=None` creates, a real
    envelope dict pre-fills the fields and switches the confirm handler to
    an update call."""
    p = palette(page)
    close = _close(page)
    group_options = [(cg["id"], cg["name"]) for cg in (category_groups or [])]
    error_text = ft.Text("", style=text_style(12, 500, p.over_ink))

    target_value = ""
    if envelope and envelope.get("target_amount") is not None:
        target_value = str(envelope["target_amount"]).replace(".", ",")

    async def handle_confirm(e: ft.ControlEvent) -> None:
        error_text.value = ""

        name = controls["Name"].value.strip()
        if not name:
            error_text.value = "Enter a name."
            page.update()
            return

        category_group_id = controls["Category group"].value
        if not category_group_id:
            error_text.value = "Pick a category group."
            page.update()
            return

        target_raw = controls["Monthly target (optional)"].value
        target_amount = parse_amount(target_raw) if target_raw else None

        payload = {"category_group_id": category_group_id, "name": name, "target_amount": target_amount}
        if envelope is not None:
            result = await api_client.update_envelope(envelope["id"], payload)
        else:
            result = await api_client.create_envelope(payload)

        if result is None:
            error_text.value = "Couldn't save — try again."
            page.update()
            return

        page.pop_dialog()
        if on_saved is not None:
            await on_saved()

    dialog, controls = build_modal(
        p,
        title="Edit envelope" if envelope is not None else "Add envelope",
        subtitle="Envelopes hold the money you plan to spend on one thing.",
        fields=[
            ModalField("Name", "input", placeholder="e.g. Pharmacy", value=envelope["name"] if envelope else ""),
            ModalField(
                "Category group",
                "select",
                options=group_options,
                value=envelope["category_group_id"] if envelope else (default_category_group_id or ""),
            ),
            ModalField(
                "Monthly target (optional)",
                "input",
                placeholder="0,00",
                hint="Envelo will suggest filling to this amount each month.",
                value=target_value,
            ),
        ],
        cta_label="Save changes" if envelope is not None else "Add envelope",
        extra=error_text,
        page=page,
        on_close=close,
        on_confirm=handle_confirm,
    )
    return dialog


def new_group_dialog(
    page: ft.Page,
    *,
    category_groups: list[dict] | None = None,
    category_group: dict | None = None,
    on_saved: Callable[[], Awaitable[None]] | None = None,
) -> ft.AlertDialog:
    """Add and Edit share this one dialog: `category_group=None` creates, a
    real category group dict pre-fills the field and switches the confirm
    handler to an update call - same pattern as `new_envelope_dialog`."""
    p = palette(page)
    close = _close(page)
    error_text = ft.Text("", style=text_style(12, 500, p.over_ink))

    async def handle_confirm(e: ft.ControlEvent) -> None:
        error_text.value = ""

        name = controls["Group name"].value.strip()
        if not name:
            error_text.value = "Enter a name."
            page.update()
            return

        if category_group is not None:
            result = await api_client.update_category_group(category_group["id"], {"name": name})
        else:
            payload = {"name": name, "sort_order": len(category_groups or [])}
            result = await api_client.create_category_group(payload)
        if result is None:
            error_text.value = "Couldn't save — try again."
            page.update()
            return

        page.pop_dialog()
        if on_saved is not None:
            await on_saved()

    dialog, controls = build_modal(
        p,
        title="Rename category group" if category_group is not None else "Add category group",
        subtitle="Groups organise envelopes on the budget screen.",
        fields=[
            ModalField(
                "Group name",
                "input",
                placeholder="e.g. Household",
                hint="Groups keep the envelope list scannable.",
                value=category_group["name"] if category_group else "",
            )
        ],
        cta_label="Save changes" if category_group is not None else "Add group",
        extra=error_text,
        page=page,
        on_close=close,
        on_confirm=handle_confirm,
    )
    return dialog


def confirm_delete_dialog(
    page: ft.Page,
    *,
    title: str,
    message: str,
    on_confirm: Callable[[], Awaitable[str | None]],
) -> ft.AlertDialog:
    """A small Cancel/Delete confirmation, reused for deleting a category
    group or an envelope. `on_confirm` does the actual API call and returns
    an error message to show inline (e.g. the 409 "still has ..." messages
    `api_client.delete_envelope`/`delete_category_group` return) or `None`
    on success, in which case the dialog closes."""
    p = palette(page)
    close = _close(page)
    error_text = ft.Text("", style=text_style(12, 500, p.over_ink))

    async def handle_confirm(e: ft.ControlEvent) -> None:
        error_text.value = ""
        error = await on_confirm()
        if error:
            error_text.value = error
            page.update()
            return
        page.pop_dialog()

    dialog, _ = build_modal(
        p,
        title=title,
        subtitle=message,
        fields=[],
        cta_label="Delete",
        extra=error_text,
        page=page,
        on_close=close,
        on_confirm=handle_confirm,
    )
    dialog.actions[1] = danger_button(p, "Delete", handle_confirm)
    return dialog


def new_rule_dialog(
    page: ft.Page,
    *,
    envelopes: list[dict] | None = None,
    rule: dict | None = None,
    on_saved: Callable[[], Awaitable[None]] | None = None,
) -> ft.AlertDialog:
    """Add and Edit share this one dialog, like `new_envelope_dialog` above.

    One condition, not three. The dialog used to offer "Payee contains" /
    "Description contains" / "Amount equals" against a model that has a single
    `phrase` column - two of the three could not be saved, and the one that could
    was matched against the description while the label said payee.
    """
    p = palette(page)
    close = _close(page)
    envelope_options = [(e["id"], e["name"]) for e in (envelopes or [])]
    error_text = ft.Text("", style=text_style(12, 500, p.over_ink))

    async def handle_confirm(e: ft.ControlEvent) -> None:
        error_text.value = ""

        phrase = controls["Payee contains"].value.strip()
        if not phrase:
            error_text.value = "Enter something to match on."
            page.update()
            return

        envelope_id = controls["Put it in"].value
        if not envelope_id:
            error_text.value = "Pick an envelope."
            page.update()
            return

        payload = {"envelope_id": envelope_id, "phrase": phrase}
        if rule is not None:
            result = await api_client.update_categorization_rule(rule["id"], payload)
        else:
            result = await api_client.create_categorization_rule(payload)

        if result is None:
            error_text.value = "Couldn't save — try again."
            page.update()
            return

        page.pop_dialog()
        if on_saved is not None:
            await on_saved()

    dialog, controls = build_modal(
        p,
        title="Edit rule" if rule is not None else "Add rule",
        subtitle="Rules file a transaction the moment you import it, based on who was paid.",
        fields=[
            ModalField(
                "Payee contains",
                "input",
                placeholder="e.g. Biedronka",
                hint="Not case-sensitive. When several rules match, the longest phrase wins.",
                value=rule["phrase"] if rule else "",
            ),
            ModalField(
                "Put it in",
                "select",
                options=envelope_options,
                value=rule["envelope_id"] if rule else "",
            ),
        ],
        cta_label="Save changes" if rule is not None else "Add rule",
        extra=error_text,
        page=page,
        on_close=close,
        on_confirm=handle_confirm,
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
            ModalField(
                "Type",
                "select",
                options=[("checking", "Checking"), ("savings", "Savings"), ("credit", "Credit card"), ("cash", "Cash")],
            ),
            ModalField(
                "Currency",
                "select",
                options=[
                    ("PLN", "Złoty (PLN)"),
                    ("EUR", "Euro (EUR)"),
                    ("USD", "US dollar (USD)"),
                    ("GBP", "Pound (GBP)"),
                ],
            ),
        ],
        cta_label="Add account",
        on_close=close,
        on_confirm=close,
    )
    return dialog


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

        # `parse_amount` accepts zero (un-assigning an envelope is a real
        # action), so a transaction of 0,00 has to be rejected here.
        amount = parse_amount(controls["Amount"].value)
        if amount is None or float(amount) == 0:
            error_text.value = "Enter a valid, non-zero amount, e.g. 42,50."
            page.update()
            return

        transaction_date = parse_date(controls["Date"].value)
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
                "Payee",
                "input",
                placeholder="Start typing — Albert Heijn, Jumbo…",
                hint="Matches an existing payee, or adds a new one.",
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
