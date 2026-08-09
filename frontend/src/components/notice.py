"""Notice banner - a full-width strip explaining why a screen is showing less
than it should.

Distinct from `components/alert_row.py`: those alerts are *about the budget*
(an envelope is over its plan) and always offer somewhere to go. This one is
about the app itself - most often "we could not reach the server" - and has no
fix to offer beyond trying again later, so it carries no CTA.
"""

import flet as ft

from theme import Palette, text_style


def notice_banner(p: Palette, message: str, *, icon: str = ft.Icons.CLOUD_OFF_ROUNDED) -> ft.Container:
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(icon, size=17, color=p.warn_ink),
                ft.Text(message, style=text_style(13, 400, p.warn_ink), expand=True),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=p.warn_fill,
        border=ft.Border.all(1, p.warn_border),
        border_radius=12,
        padding=ft.Padding.symmetric(horizontal=14, vertical=12),
    )
