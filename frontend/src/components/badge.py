"""Badges/pills - design system "Badges" swatch (Rule/ML/Manual/On track/85%/Over)
and the source, format and state pills reused on transactions, statements and
envelope cards.
"""

import flet as ft

from theme import Palette, text_style


def badge(
    label: str,
    *,
    fill: str,
    ink: str,
    uppercase: bool = True,
    size: float = 10,
    weight: int = 500,
    radius: float = 6,
    padding_x: float = 8,
    padding_y: float = 3,
    letter_spacing: float = 0.6,
) -> ft.Container:
    return ft.Container(
        content=ft.Text(
            label.upper() if uppercase else label,
            style=text_style(size, weight, ink, letter_spacing=letter_spacing),
        ),
        bgcolor=fill,
        border_radius=radius,
        padding=ft.Padding.symmetric(horizontal=padding_x, vertical=padding_y),
    )


def source_badge(p: Palette, source: str) -> ft.Container:
    """Transaction source: rule / ml / manual."""
    if source == "rule":
        return badge(label="Rule", fill=p.rule_fill, ink=p.rule_ink)
    if source == "ml":
        return badge(label="ML", fill=p.ml_fill, ink=p.ml_ink)
    return badge(label="Manual", fill=p.sf3, ink=p.ink2)


def state_pill(p: Palette, state: str, label: str) -> ft.Container:
    """Envelope state pill on card variant: over / warn / ok."""
    fill, ink = {
        "over": (p.over_fill, p.over_ink),
        "warn": (p.warn_fill, p.warn_ink),
    }.get(state, (p.ok_fill, p.ok_ink))
    return badge(label=label, fill=fill, ink=ink, size=10.5, radius=7, letter_spacing=0.4)
