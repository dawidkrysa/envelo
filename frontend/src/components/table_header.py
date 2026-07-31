"""Table header row - the uppercase column-label strip shared by the ledger,
transactions, statements and import-preview tables."""

import flet as ft

from theme import Palette, text_style


def table_header(p: Palette, columns: list[tuple[str, int, ft.TextAlign]]) -> ft.Container:
    """`columns` is a list of (label, expand_flex, alignment)."""
    cells = [
        ft.Text(label.upper(), style=text_style(10.5, 500, p.ink3, letter_spacing=0.9), expand=flex, text_align=align)
        for label, flex, align in columns
    ]
    return ft.Container(
        content=ft.Row(cells, spacing=14),
        bgcolor=p.sf2,
        padding=ft.Padding.symmetric(horizontal=18, vertical=11),
        border=ft.Border(bottom=ft.BorderSide(1, p.line)),
    )
