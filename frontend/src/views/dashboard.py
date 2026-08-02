"""Dashboard - `isDashboard` in the design: "Safe to spend" hero stat, the
top alerts, busiest envelopes and latest transactions. Backed by the real API.

Read-only: every action here navigates somewhere that can actually change
something (an envelope's detail page, the Envelopes screen, Alerts) rather than
editing in place, so this screen has no refresh path of its own.

Spending figures come from the server's `spent-by-envelope` aggregate, not from
summing a fetched list: `GET /budget/transactions` is paged, so any client-side
sum silently understated every amount here once a month held more rows than one
page. The transactions list is still fetched, but only to show the latest few.
"""

import asyncio

import flet as ft

from api_client import (
    get_envelope_allocations,
    get_envelopes,
    get_payees,
    get_spent_by_envelope,
    get_to_assign,
    get_transactions,
)
from components.alert_row import AlertItem, alert_banner
from components.card import flat_card
from components.page_header import page_header
from components.progress_bar import progress_bar
from components.stat_display import stat_block
from currency import format_money
from dates import days_left_label, month_label
from mock_data import Envelope, date_short, envelope_state, envelope_view
from theme import palette, text_style
from utils import range_to_dates, to_envelope, to_transaction
from views.common import app_shell, page_band

_MAX_ROWS = 4


def _open_envelope(page: ft.Page, envelope_id: str):
    """Same hand-off as the Envelopes screen: `routing.py` has no dynamic route
    segments, so the envelope's id travels in `page.session`. The old mock
    version navigated to the detail page without setting it, which meant every
    row on this screen opened whichever envelope happened to be selected last."""

    def handler(e: ft.ControlEvent) -> None:
        page.session.set("selected_envelope_id", envelope_id)
        page.navigate("/envelopes/detail")

    return handler


def _alerts(page: ft.Page, envelopes: list[Envelope]) -> list[AlertItem]:
    p = palette(page)
    ranked = sorted(
        [e for e in envelopes if envelope_state(e) != "ok"],
        key=lambda e: 1 if envelope_state(e) == "over" else 0,
        reverse=True,
    )
    items: list[AlertItem] = []
    for e in ranked[:2]:
        ev = envelope_view(p, e)
        over = ev.state == "over"
        message = (
            f"{e.name} is {format_money(e.spent - e.assigned)} over its plan"
            if over
            else f"{e.name} is at {ev.pct}% — {days_left_label()}, {ev.left_str} to go"
        )
        items.append(
            AlertItem(
                message=message,
                cta="Cover it" if over else "Move money",
                dot_color=p.over if over else p.warn,
                on_fix=_open_envelope(page, e.id),
            )
        )
    if len(ranked) > 2:
        names = ", ".join(e.name for e in ranked[2:])
        items.append(
            AlertItem(
                message=f"{len(ranked) - 2} more envelopes are getting close — {names}",
                cta="See alerts",
                dot_color=p.line2,
                on_fix=lambda e_: page.navigate("/alerts"),
            )
        )
    return items


def _busiest_envelope_row(page: ft.Page, ev) -> ft.Control:
    p = palette(page)
    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(ev.name, style=text_style(14, 500, p.ink)),
                        ft.Text(ev.left_str, style=text_style(14.5, 500, ev.left_ink)),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                progress_bar(p, ev.fill_fraction, color=ev.bar_color, height=7),
                ft.Text(ev.state_label, style=text_style(11.5, 400, ev.state_ink)),
            ],
            spacing=8,
        ),
        padding=ft.Padding.only(top=11),
        border=ft.Border(top=ft.BorderSide(1, p.sf3)),
        ink=True,
        on_click=_open_envelope(page, ev.id),
    )


def _transaction_row(page: ft.Page, tx) -> ft.Control:
    p = palette(page)
    amt_ink = p.ok_ink if tx.amount > 0 else p.ink
    return ft.Container(
        content=ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(
                            tx.payee, style=text_style(13.5, 500, p.ink), no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS
                        ),
                        ft.Text(f"{date_short(tx.date)} · {tx.env_id}", style=text_style(11.5, 400, p.ink3)),
                    ],
                    spacing=3,
                    tight=True,
                    expand=True,
                ),
                ft.Text(format_money(tx.amount), style=text_style(13.5, 500, amt_ink)),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.only(top=10),
        border=ft.Border(top=ft.BorderSide(1, p.sf3)),
    )


def _empty_note(p, message: str) -> ft.Control:
    return ft.Container(
        content=ft.Text(message, style=text_style(12.5, 400, p.ink3)),
        padding=ft.Padding.only(top=11),
        border=ft.Border(top=ft.BorderSide(1, p.sf3)),
    )


async def build_dashboard_view(page: ft.Page) -> ft.View:
    p = palette(page)
    band = page_band(page)

    date_from, date_to = range_to_dates("this")

    # Concurrently - none of these depend on each other, and in series they were
    # most of this screen's build time. `spent` comes from the server's own
    # aggregate rather than from summing `transactions`: that list is paged, so
    # summing it understated every figure on this screen once a month held more
    # rows than one page.
    raw_envelopes, allocations, transactions, payees, spent, to_assign = await asyncio.gather(
        get_envelopes(),
        get_envelope_allocations(),
        get_transactions(),
        get_payees(),
        get_spent_by_envelope(date_from=date_from, date_to=date_to),
        get_to_assign(),
    )

    allocation_by_envelope = {a["envelope_id"]: a for a in allocations if a["month"] == date_from.isoformat()}

    def _assigned(envelope_id: str) -> float:
        alloc = allocation_by_envelope.get(envelope_id)
        return float(alloc["assigned_amount"]) if alloc else 0.0

    envelopes = [to_envelope(e, _assigned(e["id"]), spent.get(e["id"], 0)) for e in raw_envelopes]

    # What is genuinely still spendable: money sitting in envelopes that has not
    # been spent, plus anything not yet given a job. An envelope that is already
    # overspent contributes nothing rather than a negative - the overspend is
    # what the alerts below are for, and netting it off here would quietly hide
    # it inside a single number. The mock used to subtract a hardcoded 750 to
    # approximate "rent and savings are already set aside"; nothing in the data
    # model marks an envelope that way, so that distinction is not made.
    safe_to_spend = sum(max(e.assigned - e.spent, 0) for e in envelopes) + to_assign

    top_envelopes = sorted([e for e in envelopes if e.spent > 0], key=lambda e: e.spent, reverse=True)[:_MAX_ROWS]

    payees_by_id = {pe["id"]: pe["name"] for pe in payees}
    envelope_names = {e["id"]: e["name"] for e in raw_envelopes}
    latest = sorted(transactions, key=lambda t: t["transaction_date"], reverse=True)[:_MAX_ROWS]
    top_transactions = [to_transaction(t, payees_by_id, envelope_names) for t in latest]

    body: list[ft.Control] = [
        page_header(p, "Hello", eyebrow_segments=[month_label(), days_left_label()]),
        flat_card(
            p,
            ft.Column(
                [
                    stat_block(
                        p,
                        "Safe to spend",
                        format_money(safe_to_spend),
                        value_size=52,
                        value_color=p.ok_ink if safe_to_spend >= 0 else p.over_ink,
                        note="What is left in your envelopes this month, plus anything still to assign.",
                    ),
                ],
                spacing=9,
            ),
            radius=16,
            padding=22,
        ),
    ]

    alerts = _alerts(page, envelopes)
    if alerts:
        body.append(alert_banner(p, alerts))

    envelopes_card = flat_card(
        p,
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("BUSIEST ENVELOPES", style=text_style(12, 600, p.ink2, letter_spacing=0.8)),
                        ft.Container(
                            content=ft.Text("All envelopes", style=text_style(12.5, 500, p.link)),
                            ink=True,
                            on_click=lambda e: page.navigate("/envelopes"),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                *(
                    [_busiest_envelope_row(page, envelope_view(p, e)) for e in top_envelopes]
                    or [_empty_note(p, "Nothing spent this month yet.")]
                ),
            ],
            spacing=11,
        ),
        radius=14,
        padding=18,
    )

    columns: list[ft.Control] = [envelopes_card]
    if band != "mobile":
        columns.append(
            flat_card(
                p,
                ft.Column(
                    [
                        ft.Text("LATEST TRANSACTIONS", style=text_style(12, 600, p.ink2, letter_spacing=0.8)),
                        *(
                            [_transaction_row(page, t) for t in top_transactions]
                            or [_empty_note(p, "No transactions imported yet.")]
                        ),
                    ],
                    spacing=11,
                ),
                radius=14,
                padding=18,
            )
        )

    if band == "mobile":
        body.append(ft.Column(columns, spacing=16))
    else:
        # No expand=True on the Row itself: it sits directly in the
        # scrollable body Column, which gives it unbounded height - a flex
        # child needs a bounded main axis. A bare Row already fills the
        # Column's width by default; only the two cards need expand (relative
        # to the Row's own horizontal axis) to share that width.
        body.append(ft.Row(columns, spacing=16, vertical_alignment=ft.CrossAxisAlignment.START))
        for col in columns:
            col.expand = True

    return await app_shell(page, "/dashboard", "dashboard", body)
