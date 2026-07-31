"""Select - design system "Inputs" swatch `<select>` and every filter/sort/
currency/account dropdown across the screens."""

import flet as ft

from theme import RADIUS_BUTTON, Palette, text_style


def select_field(
    p: Palette,
    options: list[tuple[str, str]],
    *,
    value: str | None = None,
    height: float = 40,
    width: float | None = None,
    expand: bool | int = False,
    on_select=None,
) -> ft.Dropdown:
    """`options` is a list of (value, label) pairs, matching the design's
    `<option value="...">label</option>` rows."""
    return ft.Dropdown(
        value=value if value is not None else (options[0][0] if options else None),
        options=[ft.dropdown.Option(key=v, text=label) for v, label in options],
        # A plain closed picker like the design's <select> - not the
        # searchable/editable combo-box this control defaults to.
        editable=False,
        enable_search=False,
        enable_filter=False,
        text_style=text_style(13, 500, p.ink),
        height=height,
        width=width,
        expand=expand,
        # No dense=True: it shrinks Material's intrinsic decoration box on
        # top of content_padding, leaving no slack for the brief window
        # (each page load, before the IBM Plex Sans .ttf files finish
        # downloading) where Flutter Web paints this fixed-height control
        # with a fallback system font. Fallback line-height can exceed the
        # branded font's, and a dense box clips/overlaps it until the swap
        # reflows - this is the "co jakiś czas" glitch on refresh. The
        # explicit vertical padding below plus the taller 40px default give
        # enough headroom that the fallback render doesn't overflow either.
        content_padding=ft.Padding.symmetric(horizontal=11, vertical=8),
        bgcolor=p.sf,
        border_color=p.line,
        focused_border_color=p.ok,
        border_radius=RADIUS_BUTTON,
        border_width=1,
        on_select=on_select,
    )
