"""Buttons - design system page "Buttons" swatch (Primary/Secondary/Ghost/Danger)
and the `<button>` elements reused across every screen's page head.
"""

from collections.abc import Callable

import flet as ft

from theme import RADIUS_BUTTON, Palette, text_style


def _label_control(label: str | ft.Control, style: ft.TextStyle) -> ft.Control:
    """Most callers pass a plain string; a caller that needs to change the
    label later (the login screen's Sign in/Create account toggle) passes an
    already-built `ft.Text` it holds a reference to and mutates in place."""
    return label if isinstance(label, ft.Control) else ft.Text(label, style=style)


def _button(
    label: str | ft.Control,
    *,
    bgcolor: str,
    border_color: str,
    color: str,
    weight: int,
    on_click: Callable[[ft.ControlEvent], None] | None,
    height: float = 38,
    padding_x: float = 15,
    expand: bool = False,
) -> ft.Container:
    return ft.Container(
        content=_label_control(label, text_style(13.5, weight, color)),
        bgcolor=bgcolor,
        border=ft.Border.all(1, border_color) if border_color else None,
        border_radius=RADIUS_BUTTON,
        height=height,
        padding=ft.Padding.symmetric(horizontal=padding_x),
        alignment=ft.Alignment.CENTER,
        ink=True,
        on_click=on_click,
        expand=expand,
        animate=ft.Animation(120, ft.AnimationCurve.EASE_OUT),
    )


def primary_button(
    p: Palette,
    label: str | ft.Control,
    on_click: Callable[[ft.ControlEvent], None] | None = None,
    expand: bool = False,
    height: float = 38,
) -> ft.Container:
    return _button(
        label,
        bgcolor=p.brand,
        border_color=p.brand,
        color=p.on_brand,
        weight=600,
        on_click=on_click,
        padding_x=16,
        expand=expand,
        height=height,
    )


def secondary_button(
    p: Palette,
    label: str | ft.Control,
    on_click: Callable[[ft.ControlEvent], None] | None = None,
    expand: bool = False,
    height: float = 38,
) -> ft.Container:
    return _button(
        label,
        bgcolor=p.sf,
        border_color=p.line2,
        color=p.ink,
        weight=500,
        on_click=on_click,
        padding_x=15,
        expand=expand,
        height=height,
    )


def ghost_button(
    p: Palette,
    label: str | ft.Control,
    on_click: Callable[[ft.ControlEvent], None] | None = None,
) -> ft.Container:
    return _button(
        label,
        bgcolor="transparent",
        border_color=None,
        color=p.ink3,
        weight=500,
        on_click=on_click,
        padding_x=13,
    )


def danger_button(
    p: Palette,
    label: str | ft.Control,
    on_click: Callable[[ft.ControlEvent], None] | None = None,
) -> ft.Container:
    return _button(
        label,
        bgcolor=p.sf,
        border_color=p.over_border,
        color=p.over_ink,
        weight=500,
        on_click=on_click,
        padding_x=15,
    )


def link_button(
    p: Palette,
    label: str | ft.Control,
    on_click: Callable[[ft.ControlEvent], None] | None = None,
    color: str | None = None,
    size: float = 12.5,
) -> ft.Container:
    """The borderless text-only `<button style="color:var(--link)">` links
    used for row-level actions (Assign, Move, Edit, Delete, ...)."""
    return ft.Container(
        content=_label_control(label, text_style(size, 500, color or p.link)),
        ink=False,
        on_click=on_click,
        padding=0,
    )
