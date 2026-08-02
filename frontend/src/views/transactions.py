"""Transactions - `isTransactions` in the design: search/filter row and the
transaction table (desktop) / stacked cards (mobile), backed by the real API.

Every filter - including the free-text search - is applied by the API Gateway,
and the table shows one page of the result at a time. Nothing is filtered
client-side: the screen only ever holds 50 of what may be thousands of rows, so
filtering here would answer "which of these 50 match" rather than "which of my
transactions match".
"""

import asyncio
from collections.abc import Callable

import flet as ft

from api_client import get_accounts, get_envelopes, get_payees, get_transactions_page
from components.button import primary_button, secondary_button
from components.card import bordered_panel
from components.input_field import text_input
from components.page_header import page_header
from components.select_field import select_field
from components.table_header import table_header
from components.transaction_row import transaction_card, transaction_table_row
from currency import format_money
from mock_data import Transaction
from theme import palette, text_style
from utils import range_to_dates, to_transaction
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


# How long a refresh may run before the dimmed table is replaced by a skeleton.
# Long enough that a local API never reaches it, short enough that a slow one
# does not leave the screen looking stuck.
_SKELETON_AFTER_S = 0.25

# Rows per page. Flet has no list virtualisation - every row is a control sent to
# the client - so this is what actually bounds the screen's cost, no matter how
# much history the database holds.
_PAGE_SIZE = 50

# How long to wait after the last keystroke before searching. `on_change` fires
# per character and search is a server round trip, so without this a six-letter
# payee name is six queries, five of them already obsolete.
_SEARCH_DEBOUNCE_S = 0.3


def _table_columns(band: str) -> list[tuple[str, int, ft.TextAlign]]:
    columns = [
        ("DATE", 1, ft.TextAlign.LEFT),
        ("PAYEE", 2, ft.TextAlign.LEFT),
        ("ENVELOPE", 2, ft.TextAlign.LEFT),
    ]
    if band == "desktop":
        columns.append(("ACCOUNT", 1, ft.TextAlign.LEFT))
    columns += [("SOURCE", 1, ft.TextAlign.LEFT), ("AMOUNT", 1, ft.TextAlign.RIGHT)]
    return columns


def _loading_rows(p, band: str, count: int) -> ft.Container:
    """Placeholder rows for a fetch slow enough to be worth acknowledging.

    Carries the real `table_header` and takes its row count from what is already
    on screen, so swapping it in does not resize the panel. A skeleton with a
    fixed height is worse than no skeleton: it collapses a long table to a stub
    and grows it back, which reads as the page jumping rather than loading.
    """
    rows: list[ft.Control] = [] if band == "mobile" else [table_header(p, _table_columns(band))]
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
    state = {"account_id": "all", "envelope_id": "all", "range": "this", "search": "", "page": 0}

    # Concurrently: two independent lookups the filter dropdowns need before
    # anything can render.
    accounts, envelopes = await asyncio.gather(get_accounts(), get_envelopes())

    account_options = [("all", "All accounts")] + [(a["id"], a["name"]) for a in accounts]
    envelope_options = [("all", "All envelopes")] + [(e["id"], e["name"]) for e in envelopes]
    range_options = [("this", "This month"), ("last3", "Last 3 months"), ("year", "This year")]

    accounts_by_id = {a["id"]: a["name"] for a in accounts}
    envelopes_by_id = {e["id"]: e["name"] for e in envelopes}

    # Filled by `_fetch_rows()` below, which is also what every filter change
    # calls - the screen has exactly one way of deciding which transactions it is
    # showing. It used to load with a bare `get_transactions()` while the range
    # dropdown already read "This month", so the table opened showing every
    # transaction ever and the first touch of *any* filter silently applied the
    # date range too. Picking an account looked like it also changed the period.
    payees: list[dict] = []
    payees_by_id: dict[str, str] = {}
    rows_data: list[Transaction] = []
    # How many match the current filters, from the server. `rows_data` only ever
    # holds one page of them.
    total = 0

    def _refilter(key: str) -> Callable[[ft.ControlEvent], None]:
        """Apply a filter and go back to page 1.

        Staying on page 4 while narrowing the results lands the user past the end
        of the new result set, which looks like the filter returned nothing."""

        def handler(e: ft.ControlEvent) -> None:
            state[key] = e.control.value
            state["page"] = 0
            page.run_task(refresh_transactions)

        return handler

    on_account_select = _refilter("account_id")
    on_envelope_select = _refilter("envelope_id")
    on_range_select = _refilter("range")

    def _go_to_page(delta: int) -> Callable[[ft.ControlEvent], None]:
        def handler(e: ft.ControlEvent) -> None:
            state["page"] = max(0, min(state["page"] + delta, _last_page()))
            page.run_task(refresh_transactions)

        return handler

    def _last_page() -> int:
        return max(0, (total - 1) // _PAGE_SIZE)

    def on_search_change(e: ft.ControlEvent) -> None:
        state["search"] = e.control.value
        state["page"] = 0
        page.run_task(_search_after_typing_stops, e.control.value)

    async def _search_after_typing_stops(typed: str) -> None:
        """Search is a server round trip now, and `on_change` fires per keystroke -
        so wait out the typing instead of querying per character.

        `typed` is passed in rather than read from `state` here: by the time these
        tasks actually run, `state["search"]` already holds the *last* keystroke,
        so every one of them would see itself as current and fire. Comparing the
        value captured when the task was scheduled is what makes the superseded
        ones return quietly - they are not cancelled, just made harmless."""
        await asyncio.sleep(_SEARCH_DEBOUNCE_S)
        if state["search"] != typed:
            return
        await refresh_transactions()

    def visible_rows() -> list[Transaction]:
        # Whatever the server sent back: the search is part of the query now, so
        # there is nothing left to filter out here.
        return rows_data

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
            text_input(p, placeholder="Search payee, description or amount", expand=True, on_change=on_search_change),
            select_field(p, account_options, value="all", on_select=on_account_select),
            select_field(p, envelope_options, value="all", on_select=on_envelope_select),
            select_field(p, range_options, value="this", on_select=on_range_select),
        ],
        spacing=9,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    summary_holder = ft.Container()

    def render_summary() -> None:
        visible = visible_rows()
        net = sum(t.amount for t in visible)
        if total == 0:
            label = "No transactions match" if state["search"].strip() else "No transactions"
        else:
            first = state["page"] * _PAGE_SIZE + 1
            label = f"{first}–{first + len(rows_data) - 1} of {total} transactions"
        summary_holder.content = ft.Row(
            [
                ft.Text(label, style=text_style(12.5, 400, p.ink3)),
                ft.Text(f"Net {format_money(net)}", style=text_style(12.5, 500, p.ink2)),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

    pager_holder = ft.Container()

    def render_pager() -> None:
        """Prev/next plus which page of how many.

        Hidden entirely when everything fits on one page - a pager that can never
        do anything is just noise above the table."""
        if total <= _PAGE_SIZE:
            pager_holder.content = None
            return
        current, last = state["page"], _last_page()
        pager_holder.content = ft.Row(
            [
                ft.Text(f"Page {current + 1} of {last + 1}", style=text_style(12.5, 400, p.ink3)),
                ft.Row(
                    [
                        secondary_button(p, "← Previous", _go_to_page(-1), disabled=current == 0),
                        secondary_button(p, "Next →", _go_to_page(1), disabled=current >= last),
                    ],
                    spacing=8,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    list_holder = ft.Container(animate_opacity=ft.Animation(140, ft.AnimationCurve.EASE_OUT))

    def render_list() -> None:
        visible = visible_rows()
        if len(visible) == 0:
            list_holder.content = _empty_state(p)
        elif band == "mobile":
            list_holder.content = ft.Column([transaction_card(p, t) for t in visible], spacing=9)
        else:
            rows: list[ft.Control] = [table_header(p, _table_columns(band))]
            for t in visible:
                rows.append(
                    transaction_table_row(
                        p, t, show_account=band == "desktop", on_envelope=lambda e: page.navigate("/envelopes/detail")
                    )
                )
            list_holder.content = bordered_panel(p, rows)

    async def _fetch_rows() -> None:
        # Also used as `new_transaction_dialog`'s on_created callback, which can
        # have just created a brand-new payee - re-fetch so its name resolves
        # instead of falling back to "Unknown", and so a second "Add
        # transaction" in the same session sees it too (avoiding a duplicate
        # payee, which is the exact thing the match-before-create logic in
        # dialogs.py exists to prevent).
        nonlocal payees, payees_by_id, rows_data, total
        date_from, date_to = range_to_dates(state["range"])
        payees, (raw, total) = await asyncio.gather(
            get_payees(),
            get_transactions_page(
                account_id=None if state["account_id"] == "all" else state["account_id"],
                envelope_id=None if state["envelope_id"] == "all" else state["envelope_id"],
                date_from=date_from,
                date_to=date_to,
                search=state["search"],
                skip=state["page"] * _PAGE_SIZE,
                limit=_PAGE_SIZE,
            ),
        )
        payees_by_id = {pe["id"]: pe["name"] for pe in payees}
        rows_data = [to_transaction(t, payees_by_id, envelopes_by_id, accounts_by_id) for t in raw]

    async def refresh_transactions() -> None:
        """Re-fetch for the current filters without the table jumping.

        The list is dimmed in place first, not replaced. Swapping straight to a
        skeleton meant a 20-row table collapsed to a fixed 6-row stub and grew
        back again - and against a local API that whole cycle happens inside one
        or two frames, so it reads as a flicker, not as loading. Dimming changes
        no layout at all, so nothing on the page moves.

        The skeleton still exists for the case it was meant for: a fetch slow
        enough that a dimmed table looks frozen. It is only swapped in once the
        request has been running past `_SKELETON_AFTER_S`, and it is sized to the
        rows currently on screen so even that swap keeps the panel's height.
        """
        list_holder.opacity = 0.4
        page.update()

        fetch = asyncio.ensure_future(_fetch_rows())
        done, _ = await asyncio.wait({fetch}, timeout=_SKELETON_AFTER_S)
        if not done:
            list_holder.content = _loading_rows(p, band, count=max(len(visible_rows()), 3))
            list_holder.opacity = 1
            page.update()
        await fetch

        render_summary()
        render_list()
        render_pager()
        list_holder.opacity = 1
        page.update()

    await _fetch_rows()
    render_summary()
    render_list()
    render_pager()

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
        pager_holder,
    ]

    return await app_shell(page, "/transactions", "transactions", body)
