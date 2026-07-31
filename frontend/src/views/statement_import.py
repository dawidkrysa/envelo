"""Import statement - `isImport` in the design: file card, target account,
match-quality stats and a preview table. "Import" only navigates to
Statements - nothing is parsed or saved."""

import flet as ft

from components.badge import badge
from components.button import primary_button, secondary_button
from components.card import bordered_panel, flat_card
from components.page_header import page_header
from components.select_field import select_field
from components.stat_display import stat_tile
from components.table_header import table_header
from mock_data import ACCOUNTS, IMPORT_ROWS, format_money
from theme import palette, text_style
from views.common import app_shell, page_band


async def build_import_view(page: ft.Page) -> ft.View:
    p = palette(page)
    band = page_band(page)

    file_card = flat_card(
        p,
        ft.Row(
            [
                ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=22, color=p.ok),
                ft.Column(
                    [
                        ft.Text("ING_checking_2026-07.csv", style=text_style(14, 500, p.ink)),
                        ft.Text("CSV · 18 rows · 14,2 kB · uploaded just now", style=text_style(12, 400, p.ink3)),
                    ],
                    spacing=3,
                    tight=True,
                    expand=True,
                ),
                secondary_button(p, "Replace"),
            ],
            spacing=14,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        radius=13,
        padding=ft.Padding.symmetric(horizontal=18, vertical=17),
    )

    account_card = flat_card(
        p,
        ft.Column(
            [
                ft.Text("IMPORT INTO", style=text_style(11, 500, p.ink3, letter_spacing=0.6)),
                select_field(p, [(a, a) for a in ACCOUNTS], value=ACCOUNTS[0]),
            ],
            spacing=7,
        ),
        radius=13,
        padding=ft.Padding.symmetric(horizontal=18, vertical=15),
    )

    top_row = (
        ft.Column([file_card, account_card], spacing=14)
        if band != "desktop"
        else ft.Row([ft.Container(content=file_card, expand=True), ft.Container(content=account_card, expand=True)], spacing=14)
    )

    # ResponsiveRow, not a wrapping Row: stat_tile's Container uses
    # expand=True to share width evenly, and a Wrap (what wrap=True on a Row
    # becomes) cannot contain a flex child - ResponsiveRow's column spans give
    # the same even-share-and-wrap result without that conflict.
    stats_row = ft.ResponsiveRow(
        [
            ft.Container(content=stat_tile(p, "14", "matched a rule", fill=p.ok_fill, border=p.ok_border, ink=p.ok_ink), col={"xs": 12, "sm": 4}),
            ft.Container(content=stat_tile(p, "3", "guessed by ML — check these", fill=p.warn_fill, border=p.warn_border, ink=p.warn_ink), col={"xs": 12, "sm": 4}),
            ft.Container(content=stat_tile(p, "1", "left uncategorized", fill=p.sf2, border=p.line, ink=p.ink), col={"xs": 12, "sm": 4}),
        ],
        spacing=12,
        run_spacing=12,
    )

    columns = [("DATE", 1, ft.TextAlign.LEFT), ("PAYEE", 2, ft.TextAlign.LEFT), ("ENVELOPE", 2, ft.TextAlign.LEFT), ("AMOUNT", 1, ft.TextAlign.RIGHT)]
    rows: list[ft.Control] = [table_header(p, columns)]
    for r in IMPORT_ROWS:
        fill, ink = {"ok": (p.ok_fill, p.ok_ink), "warn": (p.warn_fill, p.warn_ink)}.get(r["state"], (p.sf3, p.ink2))
        rows.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Text(r["date"], style=text_style(12.5, 400, p.ink3), expand=1),
                        ft.Text(r["payee"], style=text_style(13.5, 500, p.ink), expand=2, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Container(content=badge(r["envelope"], fill=fill, ink=ink, uppercase=False, size=12, weight=500, radius=6), expand=2),
                        ft.Text(format_money(r["amount"]), style=text_style(13.5, 500, p.ink), text_align=ft.TextAlign.RIGHT, expand=1),
                    ],
                    spacing=14,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.symmetric(horizontal=18, vertical=13),
                border=ft.Border(bottom=ft.BorderSide(1, p.sf3)),
            )
        )

    body: list[ft.Control] = [
        page_header(
            p,
            "Import statement",
            eyebrow_segments=["CSV · MT940 · OFX"],
            actions=[primary_button(p, "Import 18 transactions", lambda e: page.navigate("/statements"))],
        ),
        top_row,
        stats_row,
        ft.Row(
            [
                ft.Text("Preview", style=text_style(15, 600, p.ink)),
                ft.Text("Nothing is saved until you import", style=text_style(12.5, 400, p.ink3)),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        bordered_panel(p, rows),
    ]

    return app_shell(page, "/import", "import", body)
