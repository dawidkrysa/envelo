"""Envelope detail - `isDetail` in the design: hero stat + assigned-per-month
history chart, and every transaction in the envelope.

No cross-screen selection state exists in this static prototype, so the
detail screen always shows "Groceries" - the same envelope the design itself
defaults `state.selected` to.
"""

import flet as ft

from components.bar_chart import HistoryBar, history_bar_chart
from components.button import secondary_button
from components.card import bordered_panel, flat_card
from components.page_header import page_header
from components.progress_bar import progress_bar
from components.stat_display import mini_stat, stat_block
from components.table_header import table_header
from components.transaction_row import transaction_table_row
from mock_data import (
    HISTORY,
    TRANSACTIONS,
    envelope_by_id,
    envelope_view,
    format_money,
    format_short,
)
from theme import palette, text_style
from views.common import app_shell, page_band
from views.dialogs import move_dialog, new_envelope_dialog

SELECTED_ENVELOPE_ID = "groceries"


async def build_envelope_detail_view(page: ft.Page) -> ft.View:
    p = palette(page)
    band = page_band(page)

    envelope = envelope_by_id(SELECTED_ENVELOPE_ID)
    ev = envelope_view(p, envelope)

    history_values = [*HISTORY.items(), ("Jul", envelope.assigned)]
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

    detail_transactions = [t for t in TRANSACTIONS if t.env_id == envelope.id]

    body: list[ft.Control] = [
        ft.Column(
            [
                ft.Container(
                    content=ft.Text("← All envelopes", style=text_style(12, 500, p.ink3)),
                    ink=True,
                    on_click=lambda e: page.navigate("/envelopes"),
                ),
                page_header(
                    p,
                    envelope.name,
                    actions=[
                        secondary_button(p, "Move money", lambda e: page.show_dialog(move_dialog(page))),
                        secondary_button(p, "Edit envelope", lambda e: page.show_dialog(new_envelope_dialog(page))),
                    ],
                ),
            ],
            spacing=7,
        ),
    ]

    charts_row = (
        ft.Column([hero_card, history_card], spacing=18)
        if band != "desktop"
        else ft.Row(
            [ft.Container(content=hero_card, expand=135), ft.Container(content=history_card, expand=100)],
            spacing=18,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
    )
    body.append(charts_row)

    body.append(
        ft.Row(
            [
                ft.Text("Transactions in this envelope", style=text_style(15, 600, p.ink)),
                ft.Text(f"{len(detail_transactions)} this month", style=text_style(12.5, 400, p.ink3)),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
    )

    columns = [("DATE", 1, ft.TextAlign.LEFT), ("PAYEE", 2, ft.TextAlign.LEFT), ("SOURCE", 1, ft.TextAlign.LEFT), ("AMOUNT", 1, ft.TextAlign.RIGHT)]
    rows: list[ft.Control] = [table_header(p, columns)]
    for t in detail_transactions:
        rows.append(transaction_table_row(p, t, show_account=False, show_envelope=False))
    body.append(bordered_panel(p, rows))

    return app_shell(page, "/envelopes/detail", "envelopes", body)
