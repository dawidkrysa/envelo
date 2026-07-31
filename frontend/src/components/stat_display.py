"""Big-number stat block - "Safe to spend" (dashboard), "Left to assign"
(envelopes) and the import screen's three summary stat tiles."""

import flet as ft

from theme import Palette, text_style


def stat_block(
    p: Palette,
    label: str,
    value: str,
    *,
    value_size: float = 46,
    value_color: str | None = None,
    note: str | None = None,
) -> ft.Column:
    controls: list[ft.Control] = [
        ft.Text(label.upper(), style=text_style(11.5, 500, p.ink3, letter_spacing=0.7)),
        ft.Text(value, style=text_style(value_size, 600, value_color or p.ink, letter_spacing=-1)),
    ]
    if note:
        controls.append(ft.Text(note, style=text_style(13, 400, p.ink2)))
    return ft.Column(controls, spacing=6, tight=True)


def stat_tile(p: Palette, value: str, label: str, *, fill: str, border: str, ink: str) -> ft.Container:
    """Import screen's "14 matched a rule / 3 guessed by ML / 1 uncategorized"."""
    return ft.Container(
        content=ft.Column(
            [
                ft.Text(value, style=text_style(24, 600, ink)),
                ft.Text(label, style=text_style(12.5, 400, p.ink2)),
            ],
            spacing=5,
            tight=True,
        ),
        bgcolor=fill,
        border=ft.Border.all(1, border),
        border_radius=12,
        padding=ft.Padding.symmetric(horizontal=17, vertical=15),
        expand=True,
    )


def mini_stat(p: Palette, label: str, value: str, *, color: str | None = None) -> ft.Column:
    """Small label/value pair used in the envelope-detail header row and the
    import screen's account/target metadata."""
    return ft.Column(
        [
            ft.Text(label.upper(), style=text_style(11, 500, p.ink3, letter_spacing=0.7)),
            ft.Text(value, style=text_style(20, 500, color or p.ink)),
        ],
        spacing=6,
        tight=True,
    )
