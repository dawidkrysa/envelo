"""Alert rows - the compact banner list on Dashboard/Envelopes and the fuller
two-line history rows on the Alerts screen."""

from collections.abc import Callable
from dataclasses import dataclass

import flet as ft

from components.button import link_button
from theme import Palette, text_style


@dataclass(frozen=True)
class AlertItem:
    message: str
    cta: str
    dot_color: str
    on_fix: Callable[[ft.ControlEvent], None] | None = None
    title: str = ""
    meta: str = ""


def alert_banner(p: Palette, items: list[AlertItem]) -> ft.Container:
    """Compact one-line alert list used on Dashboard and Envelopes."""
    rows = []
    for i, a in enumerate(items):
        rows.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.CIRCLE, size=8, color=a.dot_color),
                        ft.Text(a.message, style=text_style(13, 400, p.ink2), expand=True, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                        link_button(p, a.cta, a.on_fix),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                border=ft.Border(bottom=ft.BorderSide(1, p.sf3)) if i < len(items) - 1 else None,
            )
        )
    return ft.Container(content=ft.Column(rows, spacing=0), bgcolor=p.sf, border=ft.Border.all(1, p.line), border_radius=12)


def alert_history_row(p: Palette, item: AlertItem) -> ft.Container:
    """Two-line row with icon, title, meta and a CTA link - Alerts screen."""
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=16, color=item.dot_color),
                ft.Column(
                    [
                        ft.Text(item.title, style=text_style(13.5, 500, p.ink)),
                        ft.Text(item.meta, style=text_style(12.5, 400, p.ink3)),
                    ],
                    spacing=3,
                    expand=True,
                    tight=True,
                ),
                link_button(p, item.cta, item.on_fix),
            ],
            spacing=13,
            vertical_alignment=ft.CrossAxisAlignment.START,
        ),
        padding=ft.Padding.symmetric(horizontal=17, vertical=15),
        border=ft.Border(bottom=ft.BorderSide(1, p.sf3)),
    )
