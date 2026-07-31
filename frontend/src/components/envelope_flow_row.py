"""Envelope flow row - the "Flow" tab variant on Envelopes: a thicker bar with
a target tick and three quick-action pills (Fill to target / Cover spending /
Move money)."""

from collections.abc import Callable

import flet as ft

from components.progress_bar import progress_bar
from mock_data import EnvelopeView
from theme import RADIUS_PILL, Palette, text_style


def _flow_pill_button(p: Palette, label: str, on_click) -> ft.Container:
    return ft.Container(
        content=ft.Text(label, style=text_style(12, 500, p.ink)),
        bgcolor=p.sf,
        border=ft.Border.all(1, p.line),
        border_radius=RADIUS_PILL,
        height=29,
        padding=ft.Padding.symmetric(horizontal=11),
        alignment=ft.Alignment.CENTER,
        ink=True,
        on_click=on_click,
    )


def envelope_flow_row(
    p: Palette,
    ev: EnvelopeView,
    *,
    on_open: Callable[[ft.ControlEvent], None] | None = None,
    on_fill_target: Callable[[ft.ControlEvent], None] | None = None,
    on_cover: Callable[[ft.ControlEvent], None] | None = None,
    on_move: Callable[[ft.ControlEvent], None] | None = None,
) -> ft.Container:
    target_fraction = min(ev.target / max(ev.assigned, ev.target), 1.0) if ev.target else 1.0
    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Row(
                            [
                                ft.Container(content=ft.Text(ev.name, style=text_style(14, 500, p.ink)), ink=True, on_click=on_open),
                                ft.Text(ev.group_name.upper(), style=text_style(11, 400, p.ink3, letter_spacing=0.5)),
                            ],
                            spacing=9,
                        ),
                        ft.Text(ev.left_str, style=text_style(15, 500, ev.left_ink)),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                progress_bar(p, ev.fill_fraction, color=ev.bar_color, height=16, target_fraction=target_fraction),
                ft.Row(
                    [
                        ft.Text(ev.bar_label, style=text_style(12, 400, p.ink2)),
                        ft.Text(f"{ev.pct_str} used", style=text_style(12, 400, p.ink3)),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Row(
                    [
                        _flow_pill_button(p, "Fill to target", on_fill_target),
                        _flow_pill_button(p, "Cover spending", on_cover),
                        _flow_pill_button(p, "Move money", on_move),
                    ],
                    spacing=7,
                ),
            ],
            spacing=9,
        ),
        bgcolor=ev.flow_fill,
        border_radius=11,
        padding=ft.Padding.symmetric(horizontal=15, vertical=14),
    )
