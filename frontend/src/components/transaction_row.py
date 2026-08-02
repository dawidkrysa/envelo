"""Transaction rows - the table row (desktop/tablet) and stacked card
(mobile) used on Transactions, Envelope detail and the Import preview."""

from collections.abc import Callable

import flet as ft

from components.badge import source_badge
from currency import format_money
from mock_data import Transaction, date_short
from theme import Palette, text_style


def transaction_table_row(
    p: Palette,
    tx: Transaction,
    *,
    show_account: bool = True,
    show_envelope: bool = True,
    on_envelope: Callable[[ft.ControlEvent], None] | None = None,
) -> ft.Container:
    amt_ink = p.ok_ink if tx.amount > 0 else p.ink
    cells: list[ft.Control] = [
        ft.Text(date_short(tx.date), style=text_style(12.5, 400, p.ink2), expand=1),
        ft.Text(
            tx.payee, style=text_style(13.5, 500, p.ink), expand=2, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS
        ),
    ]
    if show_envelope:
        cells.append(
            ft.Container(
                content=ft.Text(
                    tx.env_id, style=text_style(13, 400, p.link), no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS
                ),
                ink=True,
                on_click=on_envelope,
                expand=2,
            )
        )
    if show_account:
        cells.append(
            ft.Text(
                tx.account,
                style=text_style(12.5, 400, p.ink2),
                expand=1,
                no_wrap=True,
                overflow=ft.TextOverflow.ELLIPSIS,
            )
        )
    cells.append(ft.Container(content=source_badge(p, tx.source), expand=1))
    cells.append(
        ft.Text(format_money(tx.amount), style=text_style(14, 500, amt_ink), text_align=ft.TextAlign.RIGHT, expand=1)
    )

    return ft.Container(
        content=ft.Row(cells, spacing=14, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=18, vertical=14),
        border=ft.Border(bottom=ft.BorderSide(1, p.sf3)),
    )


def transaction_card(p: Palette, tx: Transaction) -> ft.Container:
    """Mobile stacked card - payee/meta on the left, amount/source on the right."""
    amt_ink = p.ok_ink if tx.amount > 0 else p.ink
    return ft.Container(
        content=ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(
                            tx.payee, style=text_style(14, 500, p.ink), no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS
                        ),
                        ft.Text(f"{date_short(tx.date)} · {tx.env_id}", style=text_style(11.5, 400, p.ink2)),
                    ],
                    spacing=4,
                    tight=True,
                    expand=True,
                ),
                ft.Column(
                    [
                        ft.Text(format_money(tx.amount), style=text_style(14.5, 500, amt_ink)),
                        source_badge(p, tx.source),
                    ],
                    spacing=5,
                    horizontal_alignment=ft.CrossAxisAlignment.END,
                ),
            ],
            spacing=13,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=p.sf,
        border=ft.Border.all(1, p.line),
        border_radius=12,
        padding=ft.Padding.symmetric(horizontal=15, vertical=14),
    )
