"""Rules - `isRules` in the design: the payee-matching rules applied on
import, top to bottom."""

import flet as ft

from components.button import link_button, primary_button
from components.card import flat_card
from components.page_header import page_header
from mock_data import RULES
from theme import palette, text_style
from views.common import app_shell
from views.dialogs import new_rule_dialog


async def build_rules_view(page: ft.Page) -> ft.View:
    p = palette(page)

    rows = []
    for i, r in enumerate(RULES, start=1):
        rows.append(
            flat_card(
                p,
                ft.Row(
                    [
                        ft.Text(str(i), style=text_style(11.5, 500, p.ink3)),
                        ft.Row(
                            [
                                ft.Text("Payee contains", style=text_style(13, 400, p.ink3)),
                                ft.Container(
                                    content=ft.Text(r["pattern"], style=text_style(13, 500, p.ink)),
                                    bgcolor=p.sf3,
                                    border_radius=7,
                                    padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                                ),
                                ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=15, color=p.ink3),
                                ft.Container(
                                    content=ft.Text(r["envelope"], style=text_style(13, 500, p.ok_ink)),
                                    bgcolor=p.ok_fill,
                                    border_radius=7,
                                    padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                                ),
                            ],
                            spacing=9,
                            wrap=True,
                            expand=True,
                        ),
                        ft.Text(r["hits"], style=text_style(12, 400, p.ink3)),
                        ft.Row([link_button(p, "Edit"), link_button(p, "Delete", color=p.over_ink)], spacing=14),
                    ],
                    # No wrap=True here: the "chips" Row is a flex (expand)
                    # child, and a Wrap cannot contain a flex child.
                    spacing=14,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                radius=12,
                padding=ft.Padding.symmetric(horizontal=17, vertical=15),
            )
        )

    body: list[ft.Control] = [
        page_header(
            p,
            "Rules",
            eyebrow_segments=["Applied on import, top to bottom"],
            actions=[primary_button(p, "Add rule", lambda e: page.show_dialog(new_rule_dialog(page)))],
        ),
        ft.Column(rows, spacing=9),
    ]

    return await app_shell(page, "/rules", "rules", body)
