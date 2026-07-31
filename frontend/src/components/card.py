"""Flat card - the generic white/bordered panel every stat block, table and
list container in the design sits on (`background:var(--sf);border:1px solid
var(--line);border-radius:...`)."""

import flet as ft

from theme import RADIUS_CARD, Palette


def flat_card(
    p: Palette,
    content: ft.Control,
    *,
    radius: float = RADIUS_CARD,
    padding: ft.Padding | int | None = None,
    border_color: str | None = None,
    bgcolor: str | None = None,
) -> ft.Container:
    return ft.Container(
        content=content,
        bgcolor=bgcolor or p.sf,
        border=ft.Border.all(1, border_color or p.line),
        border_radius=radius,
        padding=20 if padding is None else padding,
    )


def bordered_panel(
    p: Palette,
    children: list[ft.Control],
    *,
    radius: float = RADIUS_CARD,
) -> ft.Container:
    """A card whose content is a list of full-bleed rows (table/list), so the
    card itself carries no padding - each row manages its own."""
    return ft.Container(
        content=ft.Column(children, spacing=0),
        bgcolor=p.sf,
        border=ft.Border.all(1, p.line),
        border_radius=radius,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )
