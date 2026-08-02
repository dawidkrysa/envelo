"""Modal dialog - the bottom-sheet-on-mobile / centered-card-on-desktop used
for Assign money, Move money, Add envelope/group/rule/account/transaction.

For most of these, Confirm just closes the dialog (a stub, per the brief - no
data is actually assigned/moved/created); Cancel and the × both do the same.
"Add transaction" is the exception - it reads real values back out and calls
the API - which is why `build_modal()` returns the built field controls
(keyed by `ModalField.label`) alongside the dialog, and takes an optional
`extra` control appended after the fields (used there for an inline error).
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date as date_

import flet as ft

from components.button import primary_button, secondary_button
from components.input_field import label_field, text_input
from components.select_field import select_field
from theme import CONTROL_HEIGHT, RADIUS_BUTTON, RADIUS_CARD_LG, RADIUS_TILE, Palette, text_style


@dataclass(frozen=True)
class ModalField:
    label: str
    kind: str  # "select" | "input" | "date"
    value: str = ""
    options: list[tuple[str, str]] = field(default_factory=list)
    placeholder: str = ""
    hint: str = ""


def _date_field(p: Palette, f: ModalField, page: ft.Page) -> tuple[ft.Control, ft.Control]:
    """A read-only field that opens a calendar `ft.DatePicker` on click,
    rather than free-typed text - `page` is needed to show the picker dialog."""
    text_field = text_input(p, value=f.value, placeholder=f.placeholder, expand=True, read_only=True)

    picker = ft.DatePicker(value=date_.fromisoformat(f.value) if f.value else None)

    def _on_change(e: ft.ControlEvent) -> None:
        if picker.value is not None:
            text_field.value = picker.value.isoformat()[:10]
            page.update()

    picker.on_change = _on_change

    icon = ft.Container(
        content=ft.Icon(ft.Icons.CALENDAR_MONTH_OUTLINED, size=18, color=p.ink2),
        width=CONTROL_HEIGHT,
        height=CONTROL_HEIGHT,
        border=ft.Border.all(1, p.line),
        border_radius=RADIUS_BUTTON,
        alignment=ft.Alignment.CENTER,
        ink=True,
        on_click=lambda e: page.show_dialog(picker),
    )
    return ft.Row([text_field, icon], spacing=8), text_field


def _field_control(p: Palette, f: ModalField, page: ft.Page | None = None) -> tuple[ft.Control, ft.Control]:
    # No explicit heights here: every field kind inherits `theme.CONTROL_HEIGHT`,
    # so a dialog mixing selects and inputs (Add envelope, Add transaction) keeps
    # one field size. Pinning them to 40 used to leave the selects visibly taller,
    # since Material will not draw a dropdown below 48 whatever it is told.
    if f.kind == "select":
        control: ft.Control = select_field(p, f.options, value=f.value, expand=True)
        value_control = control
    elif f.kind == "date":
        control, value_control = _date_field(p, f, page)
    else:
        control = text_input(
            p,
            value=f.value,
            placeholder=f.placeholder,
            size=13.5,
            weight=400,
            expand=True,
        )
        value_control = control
    children: list[ft.Control] = [label_field(p, f.label), control]
    if f.hint:
        children.append(ft.Text(f.hint, style=text_style(11.5, 400, p.ink3)))
    return ft.Column(children, spacing=6), value_control


def build_modal(
    p: Palette,
    *,
    title: str,
    subtitle: str,
    fields: list[ModalField],
    cta_label: str,
    preview: tuple[str, str] | None = None,
    extra: ft.Control | None = None,
    page: ft.Page | None = None,  # required if any field has kind="date"
    on_close: Callable[[ft.ControlEvent], None] | None = None,
    on_confirm: Callable[[ft.ControlEvent], None | Awaitable[None]] | None = None,
) -> tuple[ft.AlertDialog, dict[str, ft.Control]]:
    field_controls = [_field_control(p, f, page) for f in fields]
    body: list[ft.Control] = [wrapper for wrapper, _ in field_controls]
    controls = {f.label: ctrl for f, (_, ctrl) in zip(fields, field_controls)}
    if extra:
        body.append(extra)
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

    dialog = ft.AlertDialog(
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
    return dialog, controls
