"""Envelope detail - `isDetail` in the design: hero stat + assigned-per-month
history chart, and every transaction in the envelope.

Which envelope to show is read from `page.session.store` (set by the
Envelopes list's row/card click, `views/envelopes.py::_open_detail`, and by
the Dashboard) - routing.py has no dynamic-segment mechanism, so session
storage is the simplest way to carry "which envelope was clicked" across a
`page.navigate()` call. Falls back to the first envelope if nothing was ever
selected this session (e.g. this route was reached some other way, or on a
fresh page load).
"""

import asyncio
from datetime import date

import flet as ft

from api_client import (
    delete_envelope,
    get_accounts,
    get_category_groups,
    get_envelope_allocations,
    get_envelopes,
    get_payees,
    get_spent_by_envelope,
    get_transactions,
    get_transactions_page,
)
from components.bar_chart import HistoryBar, history_bar_chart
from components.button import danger_button, secondary_button
from components.card import bordered_panel, flat_card
from components.page_header import page_header
from components.progress_bar import progress_bar
from components.stat_display import mini_stat, stat_block
from components.table_header import table_header
from components.transaction_row import transaction_table_row
from currency import format_money, format_short
from mock_data import envelope_view
from theme import palette, text_style
from utils import range_to_dates, resolve_target, to_envelope, to_transaction
from views.common import app_shell, page_band
from views.dialogs import confirm_delete_dialog, move_dialog, new_envelope_dialog


async def build_envelope_detail_view(page: ft.Page) -> ft.View:
    p = palette(page)
    band = page_band(page)

    date_from, date_to = range_to_dates("this")
    current_month = date_from.isoformat()

    envelopes, category_groups, payees, accounts = await asyncio.gather(
        get_envelopes(), get_category_groups(), get_payees(), get_accounts()
    )
    payees_by_id = {pe["id"]: pe["name"] for pe in payees}
    accounts_by_id = {a["id"]: a["name"] for a in accounts}
    envelopes_by_id = {e["id"]: e["name"] for e in envelopes}

    selected_id = page.session.store.get("selected_envelope_id")
    envelope_raw = next((e for e in envelopes if e["id"] == selected_id), None) or (
        envelopes[0] if envelopes else None
    )

    if envelope_raw is None:
        return await app_shell(
            page,
            "/envelopes/detail",
            "envelopes",
            [ft.Text("No envelopes yet — add one first.", style=text_style(14, 500, p.ink))],
        )

    envelope_id = envelope_raw["id"]
    allocations: list[dict] = []
    transactions_raw: list[dict] = []
    spent_by_envelope: dict[str, float] = {}
    spent_to_date: dict[str, float] = {}
    total_transactions = 0

    async def load() -> None:
        nonlocal allocations, transactions_raw, spent_by_envelope, spent_to_date, total_transactions
        allocations, transactions_raw, spent_by_envelope, spent_to_date, all_time = await asyncio.gather(
            get_envelope_allocations(envelope_id=envelope_id),
            get_transactions(envelope_id=envelope_id, date_from=date_from, date_to=date_to),
            get_spent_by_envelope(date_from=date_from, date_to=date_to),
            # Same aggregate without a start date: everything spent up to the end
            # of this month, which is what the carry-over below is derived from.
            get_spent_by_envelope(date_to=date_to),
            # One row, for the count in its header - the delete confirmation
            # needs to say how many transactions are about to lose their
            # envelope, and that is every one of them, not just this month's.
            get_transactions_page(envelope_id=envelope_id, limit=1),
        )
        total_transactions = all_time[1]

    def compute_envelope():
        # From the server's aggregate, not from summing `transactions_raw`: that
        # list is paged, so a busy envelope's "Spent" was understated by whatever
        # did not fit on the first page while the rows below looked complete.
        spent = spent_by_envelope.get(envelope_id, 0.0)
        current_alloc = next((a for a in allocations if a["month"] == current_month), None)
        assigned = float(current_alloc["assigned_amount"]) if current_alloc else 0.0
        fallback_target = float(envelope_raw["target_amount"]) if envelope_raw["target_amount"] is not None else 0.0
        target = resolve_target(allocations, envelope_id, current_month, fallback_target)

        # What was still in the envelope when the month began: assigned in
        # earlier months, less spent in earlier months. Matches
        # `views/common.BudgetSnapshot` - money is not reset at the 1st.
        assigned_before = sum(float(a["assigned_amount"]) for a in allocations if a["month"] < current_month)
        spent_before = spent_to_date.get(envelope_id, 0.0) - spent
        carried_over = assigned_before - spent_before

        return to_envelope(envelope_raw, assigned, spent, target, carried_over)

    def build_body() -> list[ft.Control]:
        envelope = compute_envelope()
        ev = envelope_view(p, envelope)

        # Always show the current month as the chart's last (highlighted)
        # bar, even with no allocation yet this month - matching the design's
        # original "always show this month" behaviour rather than letting
        # the chart silently end at whatever month was last assigned.
        other_months = sorted((a for a in allocations if a["month"] != current_month), key=lambda a: a["month"])[-5:]
        history_values = [
            (date.fromisoformat(a["month"]).strftime("%b"), float(a["assigned_amount"])) for a in other_months
        ]
        history_values.append((date_from.strftime("%b"), envelope.assigned))
        max_value = max(v for _, v in history_values) or 1
        bars = [
            HistoryBar(
                label=label,
                amount_label=format_short(value),
                height_px=max((value / max_value) * 72, 4),
                color=p.ok if i == len(history_values) - 1 else p.ok_fill,
            )
            for i, (label, value) in enumerate(history_values)
        ]

        hero_card = flat_card(
            p,
            ft.Column(
                [
                    ft.Row(
                        [
                            stat_block(p, "Left this month", ev.left_str, value_size=46, value_color=ev.left_ink),
                            mini_stat(p, "Assigned", ev.assigned_str),
                            mini_stat(p, "Spent", ev.spent_str),
                            mini_stat(p, "Target", format_money(envelope.target), color=p.ink2),
                        ],
                        spacing=26,
                        wrap=True,
                    ),
                    ft.Column(
                        [
                            progress_bar(p, ev.fill_fraction, color=ev.bar_color, height=10),
                            ft.Text(ev.state_label, style=text_style(12.5, 400, ev.state_ink)),
                        ],
                        spacing=8,
                    ),
                ],
                spacing=18,
            ),
            radius=14,
            padding=20,
        )

        history_card = flat_card(
            p,
            ft.Column(
                [
                    ft.Text("ASSIGNED PER MONTH", style=text_style(11, 500, p.ink3, letter_spacing=0.7)),
                    history_bar_chart(p, bars),
                ],
                spacing=14,
            ),
            radius=14,
            padding=20,
        )

        charts_row = (
            ft.Column([hero_card, history_card], spacing=18)
            if band != "desktop"
            else ft.Row(
                [ft.Container(content=hero_card, expand=135), ft.Container(content=history_card, expand=100)],
                spacing=18,
                vertical_alignment=ft.CrossAxisAlignment.START,
            )
        )

        detail_transactions = [
            to_transaction(t, payees_by_id, envelopes_by_id, accounts_by_id) for t in transactions_raw
        ]
        columns = [
            ("DATE", 1, ft.TextAlign.LEFT),
            ("PAYEE", 2, ft.TextAlign.LEFT),
            ("SOURCE", 1, ft.TextAlign.LEFT),
            ("AMOUNT", 1, ft.TextAlign.RIGHT),
        ]
        rows: list[ft.Control] = [table_header(p, columns)]
        for t in detail_transactions:
            rows.append(transaction_table_row(p, t, show_account=False, show_envelope=False))

        return [
            ft.Column(
                [
                    ft.Container(
                        content=ft.Text("← All envelopes", style=text_style(12, 500, p.ink3)),
                        ink=True,
                        on_click=lambda e: page.navigate("/envelopes"),
                    ),
                    page_header(
                        p,
                        envelope_raw["name"],
                        actions=[
                            secondary_button(
                                p,
                                "Move money",
                                lambda e: page.show_dialog(
                                    move_dialog(
                                        page, envelopes=envelopes, on_moved=refresh_detail, from_id=envelope_id
                                    )
                                ),
                            ),
                            secondary_button(
                                p,
                                "Edit envelope",
                                lambda e: page.show_dialog(
                                    new_envelope_dialog(
                                        page,
                                        category_groups=category_groups,
                                        envelope=envelope_raw,
                                        on_saved=refresh_detail,
                                    )
                                ),
                            ),
                            danger_button(
                                p,
                                "Delete envelope",
                                lambda e: page.show_dialog(
                                    confirm_delete_dialog(
                                        page,
                                        title="Delete envelope?",
                                        message=_delete_message(),
                                        on_confirm=_delete_envelope,
                                    )
                                ),
                            ),
                        ],
                    ),
                ],
                spacing=7,
            ),
            charts_row,
            ft.Row(
                [
                    ft.Text("Transactions in this envelope", style=text_style(15, 600, p.ink)),
                    ft.Text(f"{len(detail_transactions)} this month", style=text_style(12.5, 400, p.ink3)),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            bordered_panel(p, rows),
        ]

    content_holder = ft.Column(spacing=18)

    async def refresh_detail() -> None:
        nonlocal envelopes, category_groups, envelope_raw
        envelopes = await get_envelopes()
        category_groups = await get_category_groups()
        envelope_raw = next((e for e in envelopes if e["id"] == envelope_id), envelope_raw)
        await load()
        content_holder.controls = build_body()
        page.update()
        refresh_nav = getattr(page, "refresh_nav", None)
        if refresh_nav is not None:
            await refresh_nav()

    def _delete_message() -> str:
        """Says what deleting actually does rather than only that it is
        permanent. The transactions survive - they just stop belonging to an
        envelope - and whatever was assigned goes back into the pool; both are
        worth knowing *before* confirming, not discovering afterwards."""
        name = envelope_raw["name"]
        if not total_transactions:
            return f'Delete "{name}"? This can\'t be undone.'
        rows = "1 transaction" if total_transactions == 1 else f"{total_transactions} transactions"
        return (
            f'Delete "{name}"? Its {rows} will be kept but left uncategorised, '
            'and any money assigned to it goes back to "to assign". This can\'t be undone.'
        )

    async def _delete_envelope() -> str | None:
        result = await delete_envelope(envelope_id)
        if result is None:
            return "Couldn't delete — try again."
        if isinstance(result, dict) and result.get("error"):
            return result["error"]
        page.navigate("/envelopes")
        return None

    await load()
    content_holder.controls = build_body()

    return await app_shell(page, "/envelopes/detail", "envelopes", [content_holder])
