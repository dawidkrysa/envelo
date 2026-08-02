"""Statements - `isStatements` in the design: every imported file, with a
link back into its transactions."""

import flet as ft

from components.badge import badge
from components.button import primary_button
from components.card import bordered_panel
from components.page_header import page_header
from components.table_header import table_header
from mock_data import STATEMENTS
from theme import palette, text_style
from views.common import app_shell


async def build_statements_view(page: ft.Page) -> ft.View:
    p = palette(page)

    columns = [("FILE", 2, ft.TextAlign.LEFT), ("ACCOUNT", 1, ft.TextAlign.LEFT), ("IMPORTED", 1, ft.TextAlign.LEFT), ("ROWS", 1, ft.TextAlign.RIGHT)]
    rows: list[ft.Control] = [table_header(p, columns)]
    for st in STATEMENTS:
        rows.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Row(
                            [
                                badge(st["format"], fill=p.sf3, ink=p.ink2, size=10, weight=600, radius=5, padding_x=7, padding_y=2),
                                ft.Container(
                                    content=ft.Text(st["filename"], style=text_style(13.5, 500, p.ink), no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                                    ink=True,
                                    on_click=lambda e: page.navigate("/transactions"),
                                ),
                            ],
                            spacing=10,
                            expand=2,
                        ),
                        ft.Text(st["account"], style=text_style(13, 400, p.ink2), expand=1, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(st["date"], style=text_style(12.5, 400, p.ink3), expand=1),
                        ft.Container(
                            content=ft.Text(str(st["count"]), style=text_style(13.5, 500, p.link), text_align=ft.TextAlign.RIGHT),
                            ink=True,
                            on_click=lambda e: page.navigate("/transactions"),
                            expand=1,
                        ),
                    ],
                    spacing=14,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.symmetric(horizontal=18, vertical=14),
                border=ft.Border(bottom=ft.BorderSide(1, p.sf3)),
            )
        )

    body: list[ft.Control] = [
        page_header(
            p,
            "Statements",
            eyebrow_segments=[f"{len(STATEMENTS)} files"],
            actions=[primary_button(p, "Import statement", lambda e: page.navigate("/import"))],
        ),
        bordered_panel(p, rows),
    ]

    return await app_shell(page, "/statements", "statements", body)
