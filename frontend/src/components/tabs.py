"""Segmented tab control - Envelopes' Ledger/Cards/Flow switch and
Transactions' Populated/Loading/Empty state switch."""

from collections.abc import Callable

import flet as ft

from theme import RADIUS_TILE, Palette, text_style


def segmented_tabs(
    p: Palette,
    labels: list[str],
    active_index: int,
    on_select: Callable[[int], None] | None = None,
) -> ft.Container:
    buttons = []
    for i, label in enumerate(labels):
        active = i == active_index
        buttons.append(
            ft.Container(
                content=ft.Text(label, style=text_style(12.5, 600 if active else 500, p.ink if active else p.ink2)),
                bgcolor=p.sf if active else "transparent",
                border_radius=RADIUS_TILE,
                height=30,
                padding=ft.Padding.symmetric(horizontal=13),
                alignment=ft.Alignment.CENTER,
                ink=True,
                shadow=(
                    ft.BoxShadow(blur_radius=2, offset=ft.Offset(0, 1), color="#14000000")
                    if active
                    else None
                ),
                on_click=(lambda e, idx=i: on_select(idx)) if on_select else None,
            )
        )
    return ft.Container(
        content=ft.Row(buttons, spacing=2),
        bgcolor=p.sf3,
        border_radius=10,
        padding=3,
    )
