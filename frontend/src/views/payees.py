"""Payees - `isPayees` in the design: everyone money has gone to, with
History/Rename/Merge actions."""

import flet as ft

from components.button import link_button
from components.card import bordered_panel
from components.page_header import page_header
from currency import format_money
from mock_data import PAYEES
from theme import palette, text_style
from views.common import app_shell


async def build_payees_view(page: ft.Page) -> ft.View:
    p = palette(page)

    rows = []
    for pe in PAYEES:
        rows.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text(pe["name"], style=text_style(13.5, 500, p.ink)),
                                ft.Text(f"{pe['count']} transactions · last on {pe['last']}", style=text_style(11.5, 400, p.ink3)),
                            ],
                            spacing=3,
                            tight=True,
                            expand=True,
                        ),
                        ft.Container(
                            content=ft.Text(pe["envelope"], style=text_style(12, 400, p.ink2)),
                            bgcolor=p.sf3,
                            border_radius=6,
                            padding=ft.Padding.symmetric(horizontal=9, vertical=3),
                        ),
                        ft.Text(format_money(-pe["total"]), style=text_style(13.5, 500, p.ink), width=88, text_align=ft.TextAlign.RIGHT),
                        ft.Row(
                            [
                                link_button(p, "History", lambda e: page.navigate("/transactions")),
                                link_button(p, "Rename", color=p.ink3),
                                link_button(p, "Merge", color=p.ink3),
                            ],
                            spacing=14,
                        ),
                    ],
                    # No wrap=True here: the name/meta Column is a flex
                    # (expand) child, and a Wrap cannot contain a flex child.
                    spacing=14,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.symmetric(horizontal=18, vertical=14),
                border=ft.Border(bottom=ft.BorderSide(1, p.sf3)),
            )
        )

    body: list[ft.Control] = [
        page_header(p, "Payees", eyebrow_segments=[f"{len(PAYEES)} payees"]),
        bordered_panel(p, rows),
    ]

    return await app_shell(page, "/payees", "payees", body)
