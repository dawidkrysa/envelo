"""Accounts - `isAccounts` in the design: every account and its balance,
as cards."""

import flet as ft

from components.button import link_button, primary_button
from components.card import flat_card
from components.page_header import page_header
from currency import format_money
from mock_data import ACCOUNTS_LIST
from theme import palette, text_style
from views.common import app_shell
from views.dialogs import new_account_dialog


async def build_accounts_view(page: ft.Page) -> ft.View:
    p = palette(page)

    total = sum(a["balance"] for a in ACCOUNTS_LIST)

    cards = []
    for a in ACCOUNTS_LIST:
        ink = p.over_ink if a["balance"] < 0 else p.ink
        cards.append(
            ft.Container(
                content=flat_card(
                    p,
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(a["name"], style=text_style(14.5, 600, p.ink)),
                                    ft.Container(
                                        content=ft.Text(a["type"].upper(), style=text_style(10.5, 500, p.ink2, letter_spacing=0.4)),
                                        bgcolor=p.sf3,
                                        border_radius=6,
                                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Text(format_money(a["balance"]), style=text_style(26, 600, ink, letter_spacing=-0.6)),
                            ft.Container(
                                content=ft.Row(
                                    [
                                        ft.Text(a["meta"], style=text_style(11.5, 400, p.ink3), expand=True),
                                        link_button(p, "Edit"),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                padding=ft.Padding.only(top=11),
                                border=ft.Border(top=ft.BorderSide(1, p.sf3)),
                            ),
                        ],
                        spacing=14,
                    ),
                    radius=14,
                    padding=18,
                ),
                col={"xs": 12, "sm": 6, "lg": 4},
            )
        )

    body: list[ft.Control] = [
        page_header(
            p,
            "Accounts",
            eyebrow_segments=[f"{format_money(total)} across {len(ACCOUNTS_LIST)} accounts"],
            actions=[primary_button(p, "Add account", lambda e: page.show_dialog(new_account_dialog(page)))],
        ),
        ft.ResponsiveRow(cards, spacing=14, run_spacing=14),
    ]

    return await app_shell(page, "/accounts", "accounts", body)
