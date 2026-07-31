"""Toast - the bottom-center confirmation pill (e.g. "18 transactions
imported"). Presentational only; shown statically in the gallery."""

import flet as ft

from theme import RADIUS_PILL, Palette, text_style


def toast(p: Palette, message: str) -> ft.Container:
    return ft.Container(
        content=ft.Row(
            [
                ft.Container(width=7, height=7, bgcolor=p.ok, border_radius=RADIUS_PILL),
                ft.Text(message, style=text_style(13, 500, p.sf2)),
            ],
            spacing=11,
            tight=True,
        ),
        bgcolor=p.toast,
        border_radius=11,
        padding=ft.Padding.symmetric(horizontal=17, vertical=12),
    )
