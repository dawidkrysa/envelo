"""First run - `isFirstRun` in the design: the 3-step setup checklist shown
before a new budget has any accounts or envelopes.

Pre-setup, so this sits outside the app shell: no nav rail, and not listed as
a destination in it.
"""

import flet as ft

from components.button import primary_button, secondary_button
from components.card import flat_card
from components.page_header import page_header
from mock_data import SETUP_STEPS
from theme import palette, text_style
from views.common import standalone_shell

_ROUTES = {"Add account": "/accounts", "Import": "/import", "Envelopes": "/envelopes"}


async def build_first_run_view(page: ft.Page) -> ft.View:
    p = palette(page)

    rows = []
    for step in SETUP_STEPS:
        num_fill, num_ink = (p.ok_fill, p.ok_ink) if step["done"] else (p.sf3, p.ink2)
        border = p.ok_border if step["done"] else p.line
        button = (primary_button if step["done"] else secondary_button)(
            p, step["cta"], lambda e, cta=step["cta"]: page.navigate(_ROUTES.get(cta, "/dashboard"))
        )
        rows.append(
            flat_card(
                p,
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Text(str(step["n"]), style=text_style(12.5, 500, num_ink)),
                            width=27,
                            height=27,
                            bgcolor=num_fill,
                            border_radius=999,
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Column(
                            [
                                ft.Text(step["title"], style=text_style(14.5, 600, p.ink)),
                                ft.Text(step["body"], style=text_style(13, 400, p.ink3)),
                            ],
                            spacing=3,
                            tight=True,
                            expand=True,
                        ),
                        button,
                    ],
                    spacing=15,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                radius=13,
                border_color=border,
                padding=ft.Padding.symmetric(horizontal=20, vertical=19),
            )
        )

    body: list[ft.Control] = [
        page_header(p, "Set up Envelo", eyebrow_segments=["Step 1 of 3"]),
        ft.Column(rows, spacing=11, width=620),
    ]

    return standalone_shell(page, "/first-run", body)
