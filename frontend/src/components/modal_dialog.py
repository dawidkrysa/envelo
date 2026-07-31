"""Modal dialog - the bottom-sheet-on-mobile / centered-card-on-desktop used
for Assign money, Move money, Add envelope/group/rule/account/transaction.

Confirm just closes the dialog (a stub, per the brief - no data is actually
assigned/moved/created); Cancel and the × both do the same.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

import flet as ft

from components.button import primary_button, secondary_button
from components.input_field import label_field, text_input
from components.select_field import select_field
from theme import RADIUS_CARD_LG, RADIUS_TILE, Palette, text_style


@dataclass(frozen=True)
class ModalField:
    label: str
    kind: str  # "select" | "input"
    value: str = ""
    options: list[tuple[str, str]] = field(default_factory=list)
    placeholder: str = ""
    hint: str = ""
    amount_style: bool = False


def _field_control(p: Palette, f: ModalField) -> ft.Control:
    children: list[ft.Control] = [label_field(p, f.label)]
    if f.kind == "select":
        children.append(select_field(p, f.options, value=f.value, height=40))
    else:
        children.append(
            text_input(
                p,
                value=f.value,
                placeholder=f.placeholder,
                height=44 if f.amount_style else 40,
                size=19 if f.amount_style else 13.5,
                weight=600 if f.amount_style else 400,
                text_align=ft.TextAlign.RIGHT if f.amount_style else ft.TextAlign.LEFT,
            )
        )
    if f.hint:
        children.append(ft.Text(f.hint, style=text_style(11.5, 400, p.ink3)))
    return ft.Column(children, spacing=6)


def build_modal(
    p: Palette,
    *,
    title: str,
    subtitle: str,
    fields: list[ModalField],
    cta_label: str,
    preview: tuple[str, str] | None = None,
    on_close: Callable[[ft.ControlEvent], None] | None = None,
    on_confirm: Callable[[ft.ControlEvent], None] | None = None,
) -> ft.AlertDialog:
    body: list[ft.Control] = [_field_control(p, f) for f in fields]
    if preview:
        preview_label, preview_value = preview
        body.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Text(preview_label, style=text_style(12.5, 400, p.ink2), expand=True),
                        ft.Text(preview_value, style=text_style(15, 500, p.ok_ink)),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                bgcolor=p.ok_fill,
                border_radius=11,
                padding=ft.Padding.symmetric(horizontal=15, vertical=13),
            )
        )

    content = ft.Column(
        [
            ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text(title, style=text_style(18, 600, p.ink)),
                            ft.Text(subtitle, style=text_style(12.5, 400, p.ink3)),
                        ],
                        spacing=4,
                        tight=True,
                        expand=True,
                    ),
                    ft.Container(
                        content=ft.Text("×", style=text_style(15, 400, p.ink2)),
                        width=30,
                        height=30,
                        bgcolor=p.sf3,
                        border_radius=RADIUS_TILE,
                        alignment=ft.Alignment.CENTER,
                        ink=True,
                        on_click=on_close,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            ft.Column(body, spacing=15),
        ],
        spacing=20,
        tight=True,
        width=420,
    )

    return ft.AlertDialog(
        content=content,
        content_padding=ft.Padding.only(left=22, right=22, top=20, bottom=20),
        bgcolor=p.sf,
        shape=ft.RoundedRectangleBorder(radius=RADIUS_CARD_LG),
        actions=[
            secondary_button(p, "Cancel", on_close),
            primary_button(p, cta_label, on_confirm or on_close),
        ],
        actions_padding=ft.Padding.only(left=22, right=22, top=15, bottom=15),
        actions_alignment=ft.MainAxisAlignment.END,
        # On narrow widths the actions bar overflows into a stacked column
        # (Flutter's OverflowBar) - it defaults to zero gap between the
        # stacked buttons, which reads as one fused control.
        actions_overflow_button_spacing=10,
    )
