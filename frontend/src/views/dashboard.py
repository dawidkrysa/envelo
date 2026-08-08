"""Dashboard - `isDashboard` in the design: "Safe to spend" hero stat, the
top alerts, busiest envelopes and latest transactions. Backed by the real API.

Read-only: every action here navigates somewhere that can actually change
something (an envelope's detail page, the Envelopes screen, Alerts) rather than
editing in place, so this screen has no refresh path of its own.

Spending figures come from the server's `spent-by-envelope` aggregate, not from
summing a fetched list: `GET /budget/transactions` is paged, so any client-side
sum silently understated every amount here once a month held more rows than one
page. The latest-transactions card asks the server for exactly the handful of
rows it shows, in the order the server already sorts them.
"""

import asyncio

import flet as ft

from api_client import collect_failures, get_payees, get_to_assign, get_transactions_page
from components.alert_row import AlertItem, alert_banner
from components.card import flat_card
from components.notice import notice_banner
from components.page_header import page_header
from components.progress_bar import progress_bar
from components.stat_display import stat_block
from currency import format_money
from dates import days_left_label, month_label
from mock_data import Envelope, date_short, envelope_state, envelope_view
from theme import palette, text_style
from utils import to_transaction
from views.common import app_shell, fetch_budget_snapshot, page_band

_MAX_ROWS = 4


def _open_envelope(page: ft.Page, envelope_id: str):
    """Same hand-off as the Envelopes screen: `routing.py` has no dynamic route
    segments, so the envelope's id travels in the session store. The old mock
    version navigated to the detail page without setting it, which meant every
    row on this screen opened whichever envelope happened to be selected last.

    `page.session` is the `Session` object itself, which has no key-value
    methods - the store hangs off it as `page.session.store`. Calling
    `page.session.set(...)` raised straight into the app's error banner."""

    def handler(e: ft.ControlEvent) -> None:
        page.session.store.set("selected_envelope_id", envelope_id)
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
            f"{e.name} is {format_money(e.spent - e.funded)} over its plan"
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

    # Concurrently - none of these depend on each other, and in series they were
    # most of this screen's build time. The snapshot carries the month's
    # envelopes/assignments/spending and is handed to `app_shell` below so the
    # nav rail doesn't fetch the same three things all over again.
    #
    # `collect_failures` has to wrap the gather rather than follow it: the tasks
    # copy the current context as they are created, so the recorder must already
    # be installed by then.
    with collect_failures() as failures:
        snapshot, latest_page, payees, to_assign = await asyncio.gather(
            fetch_budget_snapshot(),
            # Exactly the rows this screen shows, in the order the server
            # already sorts them (`transaction_date DESC, id DESC`). It used to
            # fetch up to 100 rows to display four, then re-sort them by date
            # alone - which broke ties differently from every other screen, so
            # two transactions on the same day could swap places between here
            # and the Transactions list.
            get_transactions_page(limit=_MAX_ROWS),
            get_payees(),
            get_to_assign(),
        )

    latest_transactions, _ = latest_page
    envelopes = snapshot.envelope_models()

    # What is genuinely still spendable: what is left in the envelopes - carried
    # over included - plus anything not yet given a job. Together with the
    # corrected `to_assign` these add up to the cash actually on hand, rather
    # than to a number that drifts a little further off every month.
    #
    # An envelope that is already overspent contributes nothing rather than a
    # negative - the overspend is what the alerts below are for, and netting it
    # off here would quietly hide it inside a single number. The mock used to
    # subtract a hardcoded 750 to approximate "rent and savings are already set
    # aside"; nothing in the data model marks an envelope that way, so that
    # distinction is not made.
    safe_to_spend = sum(max(e.available, 0) for e in envelopes) + to_assign

    # `e.spent` is this month's activity, so this ranks by what actually moved
    # recently rather than by which envelope has the largest lifetime total.
    top_envelopes = sorted([e for e in envelopes if e.spent > 0], key=lambda e: e.spent, reverse=True)[:_MAX_ROWS]

    payees_by_id = {pe["id"]: pe["name"] for pe in payees}
    envelope_names = {e["id"]: e["name"] for e in snapshot.envelopes}
    top_transactions = [to_transaction(t, payees_by_id, envelope_names) for t in latest_transactions]

    body: list[ft.Control] = [
        # Not "Hello": there is no user entity behind the API yet (the gateway
        # hard-codes a single owner), so the greeting had no name to follow it
        # and read as an unfinished placeholder.
        page_header(p, "Your budget", eyebrow_segments=[month_label(), days_left_label()]),
    ]

    # Before the numbers, not after: every figure below is built from whatever
    # did arrive, so if part of it never did, the reader has to know that before
    # believing a "safe to spend" of 0,00 zł or an empty envelope list.
    if failures:
        body.append(
            notice_banner(
                p,
                "Couldn't reach the server, so this page is incomplete "
                f"({', '.join(sorted(set(failures)))}). The figures below are not the whole picture.",
            )
        )

    body.append(
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
                        note="What is left in your envelopes, plus anything still to assign.",
                    ),
                ],
                spacing=9,
            ),
            radius=16,
            padding=22,
        )
    )

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

    # Shown on every band, phones included: it used to be dropped below tablet
    # width, which took "what just came out of my account" - the one thing worth
    # glancing at on a phone - off the small screen entirely. Stacked under the
    # envelopes card there rather than beside it.
    transactions_card = flat_card(
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

    columns: list[ft.Control] = [envelopes_card, transactions_card]

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

    # The snapshot goes to the shell so the nav rail reuses this screen's
    # envelopes/assignments/spending instead of re-fetching all three.
    return await app_shell(page, "/dashboard", "dashboard", body, snapshot=snapshot)
