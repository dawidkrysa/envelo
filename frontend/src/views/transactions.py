"""Transactions - `isTransactions` in the design: search/filter row and the
transaction table (desktop) / stacked cards (mobile), backed by the real API.

Account/envelope/range filters re-fetch from the API Gateway on change; the
free-text search box has no backend equivalent to filter by, so it filters
client-side over whatever the current server-side filters already fetched.
"""

import calendar
from datetime import date

import flet as ft

from api_client import get_accounts, get_envelopes, get_payees, get_transactions
from components.button import primary_button
from components.card import bordered_panel
from components.input_field import text_input
from components.page_header import page_header
from components.select_field import select_field
from components.table_header import table_header
from components.transaction_row import transaction_card, transaction_table_row
from mock_data import Transaction, format_money
from theme import palette, text_style
from views.common import app_shell, page_band
from views.dialogs import new_transaction_dialog


def _shift_months(d: date, months: int) -> date:
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def _range_to_dates(s: str) -> tuple[date, date]:
    current = date.today()
    year = current.year
    month = current.month
    last_day = calendar.monthrange(year, month)[1]
    match s:
        case "this":
            return (date(year, month, 1), date(year, month, last_day))
        case "last3":
            return (_shift_months(current, -3), current)
        case "year":
            return (_shift_months(current, -12), current)
    return (date(year, month, 1), date(year, month, last_day))


def _to_transaction(t: dict, payees_by_id: dict, envelopes_by_id: dict, accounts_by_id: dict) -> Transaction:
    return Transaction(
        id=t["id"],
        date=t["transaction_date"],
        payee=payees_by_id.get(t["payee_id"], "Unknown"),
        env_id=envelopes_by_id.get(t["envelope_id"], "Uncategorized"),
        account=accounts_by_id.get(t["account_id"], "Unknown"),
        amount=float(t["amount"]),
        source=t["categorization_source"] or "manual",
    )


def _empty_state(p) -> ft.Container:
    return ft.Container(
        content=ft.Column(
            [
                ft.Text("No transactions match these filters", style=text_style(14, 600, p.ink)),
                ft.Text("Try widening the date range or clearing a filter.", style=text_style(13, 400, p.ink3)),
            ],
            spacing=6,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        alignment=ft.Alignment.CENTER,
        padding=48,
        bgcolor=None,
        border=ft.Border.all(1, p.line),
        border_radius=14,
    )


def _loading_rows(p, count: int = 6) -> ft.Container:
    rows = []
    for _ in range(count):
        rows.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Container(height=12, bgcolor=p.sf3, border_radius=4, expand=1),
                        ft.Container(height=12, bgcolor=p.sf3, border_radius=4, expand=2),
                        ft.Container(height=12, bgcolor=p.sf3, border_radius=4, expand=1),
                    ],
                    spacing=14,
                ),
                padding=ft.Padding.symmetric(horizontal=18, vertical=16),
                border=ft.Border(bottom=ft.BorderSide(1, p.sf3)),
            )
        )
    return bordered_panel(p, rows)


async def build_transactions_view(page: ft.Page) -> ft.View:
    p = palette(page)
    band = page_band(page)
    state = {"account_id": "all", "envelope_id": "all", "range": "this", "search": ""}

    payees = await get_payees()
    accounts = await get_accounts()
    transactions = await get_transactions()
    envelopes = await get_envelopes()

    account_options = [("all", "All accounts")] + [(a["id"], a["name"]) for a in accounts]
    envelope_options = [("all", "All envelopes")] + [(e["id"], e["name"]) for e in envelopes]
    range_options = [("this", "This month"), ("last3", "Last 3 months"), ("year", "This year")]

    payees_by_id = {p["id"]: p["name"] for p in payees}
    accounts_by_id = {a["id"]: a["name"] for a in accounts}
    envelopes_by_id = {e["id"]: e["name"] for e in envelopes}

    rows_data = [_to_transaction(t, payees_by_id, envelopes_by_id, accounts_by_id) for t in transactions]

    def on_account_select(e: ft.ControlEvent) -> None:
        state["account_id"] = e.control.value
        page.run_task(refresh_transactions)

    def on_envelope_select(e: ft.ControlEvent) -> None:
        state["envelope_id"] = e.control.value
        page.run_task(refresh_transactions)

    def on_range_select(e: ft.ControlEvent) -> None:
        state["range"] = e.control.value
        page.run_task(refresh_transactions)

    def on_search_change(e: ft.ControlEvent) -> None:
        state["search"] = e.control.value
        render_summary()
        render_list()
        page.update()

    def visible_rows() -> list[Transaction]:
        query = state["search"].strip().lower()
        if not query:
            return rows_data
        return [t for t in rows_data if query in t.payee.lower() or query in format_money(t.amount).lower()]

    # Search absorbs whatever width the three (natural-sized, un-expanded)
    # dropdowns don't need - expand=True on the search field only, not on
    # the dropdowns, so it's the search box that shrinks/grows with the
    # window instead of dropdown text ever getting squeezed below its
    # natural width (Flet's Dropdown has no ellipsis/overflow fallback, so
    # that squeeze used to render as broken, mid-word-truncated text - a
    # narrow search box just looks like a narrow search box). Because
    # nothing follows the dropdown group and the search field claims all
    # left-over space, the dropdowns end up flush against the right edge
    # without needing MainAxisAlignment.SPACE_BETWEEN (which, combined with
    # wrap=True, was wrapping this row a run early even when both groups
    # comfortably fit side by side - Wrap's own layout pass, not a real
    # width shortage).
    filters_row = ft.Row(
        [
            text_input(p, placeholder="Search payee or amount", expand=True, on_change=on_search_change),
            select_field(p, account_options, value="all", on_select=on_account_select),
            select_field(p, envelope_options, value="all", on_select=on_envelope_select),
            select_field(p, range_options, value="this", on_select=on_range_select),
        ],
        spacing=9,
    )

    summary_holder = ft.Container()

    def render_summary() -> None:
        visible = visible_rows()
        net = sum(t.amount for t in visible)
        summary_holder.content = ft.Row(
            [
                ft.Text(f"{len(visible)} of {len(rows_data)} transactions", style=text_style(12.5, 400, p.ink3)),
                ft.Text(f"Net {format_money(net)}", style=text_style(12.5, 500, p.ink2)),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

    list_holder = ft.Container()

    def render_list() -> None:
        visible = visible_rows()
        if len(visible) == 0:
            list_holder.content = _empty_state(p)
        elif band == "mobile":
            list_holder.content = ft.Column([transaction_card(p, t) for t in visible], spacing=9)
        else:
            columns = [
                ("DATE", 1, ft.TextAlign.LEFT),
                ("PAYEE", 2, ft.TextAlign.LEFT),
                ("ENVELOPE", 2, ft.TextAlign.LEFT),
            ]
            if band == "desktop":
                columns.append(("ACCOUNT", 1, ft.TextAlign.LEFT))
            columns += [("SOURCE", 1, ft.TextAlign.LEFT), ("AMOUNT", 1, ft.TextAlign.RIGHT)]
            rows: list[ft.Control] = [table_header(p, columns)]
            for t in visible:
                rows.append(
                    transaction_table_row(
                        p, t, show_account=band == "desktop", on_envelope=lambda e: page.navigate("/envelopes/detail")
                    )
                )
            list_holder.content = bordered_panel(p, rows)

    async def refresh_transactions() -> None:
        list_holder.content = _loading_rows(p)
        page.update()

        # Also used as `new_transaction_dialog`'s on_created callback, which can
        # have just created a brand-new payee - re-fetch so its name resolves
        # instead of falling back to "Unknown", and so a second "Add
        # transaction" in the same session sees it too (avoiding a duplicate
        # payee, which is the exact thing the match-before-create logic in
        # dialogs.py exists to prevent).
        nonlocal payees, payees_by_id
        payees = await get_payees()
        payees_by_id = {pe["id"]: pe["name"] for pe in payees}

        date_from, date_to = _range_to_dates(state["range"])
        raw = await get_transactions(
            account_id=None if state["account_id"] == "all" else state["account_id"],
            envelope_id=None if state["envelope_id"] == "all" else state["envelope_id"],
            date_from=date_from,
            date_to=date_to,
        )
        nonlocal rows_data
        rows_data = [_to_transaction(t, payees_by_id, envelopes_by_id, accounts_by_id) for t in raw]
        render_summary()
        render_list()
        page.update()

    render_summary()
    render_list()

    body: list[ft.Control] = [
        page_header(
            p,
            "Transactions",
            eyebrow_segments=["All accounts"],
            actions=[
                primary_button(
                    p,
                    "Add transaction",
                    lambda e: page.show_dialog(
                        new_transaction_dialog(
                            page,
                            accounts=accounts,
                            envelopes=envelopes,
                            payees=payees,
                            on_created=refresh_transactions,
                        )
                    ),
                ),
            ],
        ),
        filters_row,
        summary_holder,
        list_holder,
    ]

    return app_shell(page, "/transactions", "transactions", body)
