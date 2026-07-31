"""Text inputs - design system "Inputs" swatch, login form fields, modal
fields and the ledger's inline assign-amount field with a currency suffix."""

import flet as ft

from theme import RADIUS_BUTTON, Palette, text_style


def text_input(
    p: Palette,
    *,
    value: str = "",
    placeholder: str | None = None,
    height: float = 38,
    size: float = 13.5,
    weight: int = 400,
    text_align: ft.TextAlign = ft.TextAlign.LEFT,
    password: bool = False,
    read_only: bool = False,
    on_change: object = None,
    expand: bool | int = False,
    width: float | None = None,
) -> ft.TextField:
    return ft.TextField(
        value=value,
        hint_text=placeholder,
        password=password,
        can_reveal_password=password,
        read_only=read_only,
        text_align=text_align,
        text_style=text_style(size, weight, p.ink),
        hint_style=text_style(size, 400, p.ink3),
        height=height,
        width=width,
        content_padding=ft.Padding.symmetric(horizontal=13),
        bgcolor=p.sf,
        border_color=p.line,
        focused_border_color=p.ok,
        border_radius=RADIUS_BUTTON,
        border_width=1,
        on_change=on_change,
        expand=expand,
    )


def amount_input(p: Palette, *, value: str = "", currency_symbol: str = "€", height: float = 34) -> ft.Stack:
    """Ledger row's right-aligned assign field with a pinned currency glyph,
    e.g. `118,00` with a trailing " €" that never moves as you type."""
    field = ft.TextField(
        value=value,
        text_align=ft.TextAlign.RIGHT,
        text_style=text_style(13.5, 500, p.ink),
        height=height,
        content_padding=ft.Padding.only(left=10, right=24),
        bgcolor=p.sf,
        border_color=p.sf3,
        focused_border_color=p.ok,
        border_radius=RADIUS_BUTTON,
        border_width=1,
        width=118,
    )
    suffix = ft.Container(
        content=ft.Text(currency_symbol, style=text_style(13, 400, p.ink2)),
        alignment=ft.Alignment.CENTER_RIGHT,
        padding=ft.Padding.only(right=10),
        height=height,
        width=118,
    )
    return ft.Stack([field, suffix])


def label_field(p: Palette, label: str) -> ft.Text:
    """`<label>` above a modal/settings field: uppercase, 11.5px, ink2."""
    return ft.Text(label.upper(), style=text_style(11.5, 500, p.ink2, letter_spacing=0.6))
