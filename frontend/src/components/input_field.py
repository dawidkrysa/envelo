"""Text inputs - design system "Inputs" swatch, login form fields, modal
fields and the ledger's inline assign-amount field with a currency suffix."""

import flet as ft

from currency import symbol
from theme import CONTROL_HEIGHT, RADIUS_BUTTON, Palette, text_style


def text_input(
    p: Palette,
    *,
    value: str = "",
    placeholder: str | None = None,
    height: float = CONTROL_HEIGHT,
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


def amount_input(
    p: Palette,
    *,
    value: str = "",
    currency_symbol: str | None = None,
    height: float = 34,
    on_blur: object = None,
    on_submit: object = None,
) -> ft.Stack:
    """Ledger row's right-aligned assign field with a pinned currency glyph,
    e.g. `118,00` with a trailing ` zł` that never moves as you type.

    `currency_symbol` defaults to the currently selected currency's glyph. It is
    resolved here rather than in the signature because a default argument is
    evaluated once at import, which would freeze the app on whatever currency
    happened to be selected first.
    """
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
        on_blur=on_blur,
        on_submit=on_submit,
    )
    # Wrapped in a TransparentPointer: this container covers the whole field, and
    # the glyph's own text render box hit-tests, so without it a tap landing on
    # the symbol is swallowed here instead of focusing the field underneath.
    suffix = ft.TransparentPointer(
        content=ft.Container(
            content=ft.Text(currency_symbol or symbol(), style=text_style(13, 400, p.ink2)),
            alignment=ft.Alignment.CENTER_RIGHT,
            padding=ft.Padding.only(right=10),
            height=height,
            width=118,
        )
    )
    return ft.Stack([field, suffix])


def label_field(p: Palette, label: str) -> ft.Text:
    """`<label>` above a modal/settings field: uppercase, 11.5px, ink2."""
    return ft.Text(label.upper(), style=text_style(11.5, 500, p.ink2, letter_spacing=0.6))
