"""Envelope ledger row - the table row inside the Envelopes screen's "Ledger"
tab, with per-breakpoint column counts (name/state, assigned, spent, left,
progress+%)."""

from collections.abc import Callable

import flet as ft

from components.input_field import amount_input
from components.progress_bar import progress_bar
from mock_data import EnvelopeView
from theme import Palette, text_style


def envelope_ledger_row(
    p: Palette,
    ev: EnvelopeView,
    band: str,
    *,
    on_open: Callable[[ft.ControlEvent], None] | None = None,
    currency_symbol: str = "€",
) -> ft.Container:
    not_mobile = band != "mobile"
    is_desktop = band == "desktop"

    name_col = ft.Column(
        [
            ft.Container(
                content=ft.Text(ev.name, style=text_style(14, 500, p.ink), no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                ink=True,
                on_click=on_open,
            ),
            ft.Text(ev.state_label, style=text_style(11.5, 400, ev.state_ink), no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
        ],
        spacing=3,
        tight=True,
        expand=2,
    )

    cells: list[ft.Control] = [name_col]
    if not_mobile:
        cells.append(ft.Container(content=amount_input(p, value=ev.assigned_str.replace(" €", ""), currency_symbol=currency_symbol), expand=1))
        cells.append(
            ft.Text(ev.spent_str, style=text_style(13.5, 400, p.ink2), text_align=ft.TextAlign.RIGHT, expand=1)
        )
    cells.append(
        ft.Text(ev.left_str, style=text_style(14.5, 500, ev.left_ink), text_align=ft.TextAlign.RIGHT, expand=1)
    )
    if is_desktop:
        cells.append(
            ft.Row(
                [
                    ft.Container(content=progress_bar(p, ev.fill_fraction, color=ev.bar_color), expand=True),
                    ft.Text(ev.pct_str, style=text_style(11.5, 500, p.ink2), width=38, text_align=ft.TextAlign.RIGHT),
                ],
                spacing=11,
                expand=2,
            )
        )

    return ft.Container(
        content=ft.Row(cells, spacing=16, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=18, vertical=13),
        border=ft.Border(bottom=ft.BorderSide(1, p.sf3)),
    )
