"""Select - design system "Inputs" swatch `<select>` and every filter/sort/
currency/account dropdown across the screens."""

import flet as ft

from theme import CONTROL_HEIGHT, RADIUS_BUTTON, Palette, text_style


def select_field(
    p: Palette,
    options: list[tuple[str, str]],
    *,
    value: str | None = None,
    height: float = CONTROL_HEIGHT,
    width: float | None = None,
    expand: bool | int = False,
    on_select=None,
    disabled: bool = False,
) -> ft.Dropdown:
    """`options` is a list of (value, label) pairs, matching the design's
    `<option value="...">label</option>` rows.

    `disabled` greys the picker out and drops its handler - for a setting the app
    can display but cannot yet act on, where leaving it operable would let
    someone choose an option that does nothing.
    """
    return ft.Dropdown(
        disabled=disabled,
        # Falls back to the first option for both an explicit `None` and an
        # empty string - a caller that has "no id yet" (e.g. a dialog opened
        # without a preselected envelope) passes "" here, and that must not
        # be handed to Flutter as a real value: it won't match any option,
        # leaving the field in a value-set-but-nothing-selected state that
        # `move_dialog`'s same-envelope guard depends on not happening.
        value=value if value else (options[0][0] if options else None),
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
        # reflows - this is the intermittent glitch on refresh. The explicit
        # vertical padding below plus the taller default give enough headroom
        # that the fallback render doesn't overflow either.
        #
        # That default is `theme.CONTROL_HEIGHT` (48), not a smaller number,
        # because Material refuses to draw this control below its 48px minimum
        # interactive size regardless: asking for 40 produced ~48, so the nominal
        # height was a fiction and anything sitting beside it lined up wrong.
        # Passing a larger height works; passing a smaller one does nothing.
        # `vertical_alignment=CENTER` on the row a select sits in (see
        # envelopes.py/transactions.py) still guards against any residual
        # difference being top-heavy.
        content_padding=ft.Padding.symmetric(horizontal=11, vertical=8),
        bgcolor=p.sf,
        border_color=p.line,
        focused_border_color=p.ok,
        border_radius=RADIUS_BUTTON,
        border_width=1,
        on_select=on_select,
    )
