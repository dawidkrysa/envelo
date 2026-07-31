"""Envelope card - the "Cards" tab variant on Envelopes and the busiest-
envelopes list on Dashboard."""

from collections.abc import Callable

import flet as ft

from components.badge import state_pill
from components.button import link_button
from components.progress_bar import progress_bar
from mock_data import EnvelopeView
from theme import RADIUS_CARD, Palette, text_style


def envelope_card(
    p: Palette,
    ev: EnvelopeView,
    *,
    on_open: Callable[[ft.ControlEvent], None] | None = None,
    on_assign: Callable[[ft.ControlEvent], None] | None = None,
    on_move: Callable[[ft.ControlEvent], None] | None = None,
) -> ft.Container:
    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(content=ft.Text(ev.name, style=text_style(14.5, 600, p.ink)), ink=True, on_click=on_open, expand=True),
                        state_pill(p, ev.state, ev.pill_label),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Column(
                    [
                        ft.Text(ev.left_str, style=text_style(31, 600, ev.left_ink, letter_spacing=-0.7)),
                        ft.Text(ev.left_of_label, style=text_style(11.5, 400, p.ink3)),
                    ],
                    spacing=6,
                    tight=True,
                ),
                ft.Column(
                    [
                        progress_bar(p, ev.fill_fraction, color=ev.bar_color, height=8),
                        ft.Row(
                            [
                                ft.Text(ev.spent_label, style=text_style(11.5, 400, p.ink2), no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                                ft.Text(ev.target_note, style=text_style(11.5, 400, p.ink3), no_wrap=True),
                            ],
                            spacing=10,
                        ),
                    ],
                    spacing=7,
                ),
                ft.Container(
                    content=ft.Row(
                        [link_button(p, "Assign", on_assign), link_button(p, "Move", on_move, color=p.ink3)],
                        spacing=16,
                    ),
                    padding=ft.Padding.only(top=11),
                    border=ft.Border(top=ft.BorderSide(1, p.sf3)),
                ),
            ],
            spacing=14,
        ),
        bgcolor=p.sf,
        border=ft.Border.all(1, ev.card_border),
        border_radius=RADIUS_CARD,
        padding=ft.Padding.only(left=17, right=17, top=17, bottom=15),
    )
