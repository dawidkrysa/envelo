"""Transactions - `isTransactions` in the design: search/filter row, the
Populated/Loading/Empty state tabs, and the transaction table (desktop) /
stacked cards (mobile).

Search and the account/envelope/range filters are visual-only (they render
with their placeholder/default value but do not actually filter the static
row list) - only the state tabs switch what is shown, matching the design's
own dogfooding of the three list states.
"""

import flet as ft

from components.button import primary_button
from components.card import bordered_panel
from components.input_field import text_input
from components.page_header import page_header
from components.select_field import select_field
from components.table_header import table_header
from components.tabs import segmented_tabs
from components.transaction_row import transaction_card, transaction_table_row
from mock_data import ACCOUNTS, TRANSACTIONS, all_envelopes
from theme import palette, text_style
from views.common import app_shell, page_band
from views.dialogs import new_transaction_dialog


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
    state = {"tx_state": "populated"}

    account_options = [("all", "All accounts")] + [(a, a) for a in ACCOUNTS]
    envelope_options = [("all", "All envelopes")] + [(e.id, e.name) for e in all_envelopes()]
    range_options = [("this", "This month"), ("last3", "Last 3 months"), ("year", "This year")]

    # No wrap=True here: a Wrap whose direct children are interactive form
    # controls (TextField/Dropdown) renders as a solid placeholder box in
    # Flet 0.86 instead of the filters - see components/button.py's
    # equivalent note for the button-Container case of the same bug.
    filters_row = ft.Row(
        [
            text_input(p, placeholder="Search payee or amount", width=260),
            select_field(p, account_options, value="all"),
            select_field(p, envelope_options, value="all"),
            select_field(p, range_options, value="this"),
        ],
        spacing=9,
    )

    net = sum(t.amount for t in TRANSACTIONS)
    summary_row = ft.Row(
        [
            ft.Text(f"{len(TRANSACTIONS)} of {len(TRANSACTIONS)} transactions", style=text_style(12.5, 400, p.ink3)),
            ft.Text(f"Net {net:,.2f} €".replace(",", "§").replace(".", ",").replace("§", "."), style=text_style(12.5, 500, p.ink2)),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    list_holder = ft.Container()

    def render_list() -> None:
        if state["tx_state"] == "empty":
            list_holder.content = _empty_state(p)
        elif state["tx_state"] == "loading":
            list_holder.content = _loading_rows(p)
        elif band == "mobile":
            list_holder.content = ft.Column([transaction_card(p, t) for t in TRANSACTIONS], spacing=9)
        else:
            columns = [("DATE", 1, ft.TextAlign.LEFT), ("PAYEE", 2, ft.TextAlign.LEFT), ("ENVELOPE", 2, ft.TextAlign.LEFT)]
            if band == "desktop":
                columns.append(("ACCOUNT", 1, ft.TextAlign.LEFT))
            columns += [("SOURCE", 1, ft.TextAlign.LEFT), ("AMOUNT", 1, ft.TextAlign.RIGHT)]
            rows: list[ft.Control] = [table_header(p, columns)]
            for t in TRANSACTIONS:
                rows.append(
                    transaction_table_row(
                        p, t, show_account=band == "desktop", on_envelope=lambda e: page.navigate("/envelopes/detail")
                    )
                )
            list_holder.content = bordered_panel(p, rows)

    tabs_holder = ft.Container()

    def rerender() -> None:
        tabs_holder.content = segmented_tabs(
            p, ["Populated", "Loading", "Empty"], ["populated", "loading", "empty"].index(state["tx_state"]), select_state
        )
        render_list()
        page.update()

    def select_state(index: int) -> None:
        state["tx_state"] = ["populated", "loading", "empty"][index]
        rerender()

    tabs_holder.content = segmented_tabs(p, ["Populated", "Loading", "Empty"], 0, select_state)
    render_list()

    body: list[ft.Control] = [
        page_header(
            p,
            "Transactions",
            eyebrow_segments=["All accounts"],
            actions=[
                ft.Row(
                    [tabs_holder, primary_button(p, "Add transaction", lambda e: page.show_dialog(new_transaction_dialog(page)))],
                    spacing=8,
                )
            ],
        ),
        filters_row,
        summary_row,
        list_holder,
    ]

    return app_shell(page, "/transactions", "transactions", body)
