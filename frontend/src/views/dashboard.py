"""Dashboard - `isDashboard` in the design: "Safe to spend" hero stat, the
top alerts, busiest envelopes and latest transactions."""

import flet as ft

from components.alert_row import AlertItem, alert_banner
from components.card import flat_card
from components.page_header import page_header
from components.progress_bar import progress_bar
from components.stat_display import stat_block
from mock_data import (
    DAYS_LEFT,
    MONTH,
    POOL,
    TRANSACTIONS,
    all_envelopes,
    attention_envelopes,
    date_short,
    envelope_name,
    envelope_state,
    envelope_view,
    format_money,
)
from theme import palette, text_style
from views.common import app_shell, page_band


def _alerts(page: ft.Page) -> list[AlertItem]:
    p = palette(page)
    attention = attention_envelopes()
    ranked = sorted(attention, key=lambda e: 1 if envelope_state(e) == "over" else 0, reverse=True)
    items: list[AlertItem] = []
    for e in ranked[:2]:
        ev = envelope_view(p, e)
        over = ev.state == "over"
        message = (
            f"{e.name} is {format_money(e.spent - e.assigned)} over its plan"
            if over
            else f"{e.name} is at {ev.pct}% — {DAYS_LEFT} days left, {ev.left_str} to go"
        )
        items.append(
            AlertItem(
                message=message,
                cta="Cover it" if over else "Move money",
                dot_color=p.over if over else p.warn,
                on_fix=lambda e_: page.navigate("/envelopes/detail"),
            )
        )
    if len(ranked) > 2:
        names = ", ".join(e.name for e in ranked[2:])
        items.append(
            AlertItem(
                message=(f"{len(ranked) - 2} more envelopes are getting close — {names}"),
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
        on_click=lambda e: page.navigate("/envelopes/detail"),
    )


def _transaction_row(page: ft.Page, tx) -> ft.Control:
    p = palette(page)
    amt_ink = p.ok_ink if tx.amount > 0 else p.ink
    return ft.Container(
        content=ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(tx.payee, style=text_style(13.5, 500, p.ink), no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(f"{date_short(tx.date)} · {envelope_name(tx.env_id)}", style=text_style(11.5, 400, p.ink3)),
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


async def build_dashboard_view(page: ft.Page) -> ft.View:
    p = palette(page)
    band = page_band(page)

    envelopes = all_envelopes()
    safe_to_spend = sum(max(e.assigned - e.spent, 0) for e in envelopes) - 750 + POOL

    top_envelopes = sorted(envelopes, key=lambda e: e.spent, reverse=True)[:4]
    top_transactions = TRANSACTIONS[:4]

    body: list[ft.Control] = [
        page_header(p, "Hello, Maartje", eyebrow_segments=[MONTH, f"{DAYS_LEFT} days left"]),
        flat_card(
            p,
            ft.Column(
                [
                    stat_block(
                        p,
                        "Safe to spend",
                        format_money(safe_to_spend),
                        value_size=52,
                        value_color=p.ok_ink,
                        note="Everyday envelopes only — rent and savings are already set aside.",
                    ),
                ],
                spacing=9,
            ),
            radius=16,
            padding=22,
        ),
    ]

    alerts = _alerts(page)
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
                *[_busiest_envelope_row(page, envelope_view(p, e)) for e in top_envelopes],
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
                        *[_transaction_row(page, t) for t in top_transactions],
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

    return app_shell(page, "/dashboard", "dashboard", body)
