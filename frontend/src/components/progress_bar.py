"""Progress bar - design system "Progress states" swatch and the envelope
fill bars reused on the dashboard, envelope ledger/card/flow rows and detail.
"""

import flet as ft

from theme import RADIUS_PILL, Palette


def progress_bar(
    p: Palette,
    fraction: float,
    *,
    color: str,
    height: float = 8,
    target_fraction: float | None = None,
) -> ft.Control:
    """`fraction` and `target_fraction` are 0..1 (already clamped by caller).

    `target_fraction` draws the thin vertical tick used by the Flow variant
    to mark an envelope's monthly target against its current fill.
    """
    # ft.ProgressBar has no intrinsic width - a bare Column child (the
    # envelope card/flow-row/dashboard layouts all place it that way) gives it
    # no width constraint at all and it collapses to nothing. Wrapping in a
    # Row is a self-contained fix: a Row defaults to its parent's full main
    # axis width regardless of context, and `expand=True` on the bar then
    # claims that width along the Row's horizontal main axis.
    fraction = max(0.0, min(1.0, fraction))
    bar = ft.ProgressBar(
        value=fraction,
        bar_height=height,
        color=color,
        bgcolor=p.sf3,
        border_radius=RADIUS_PILL,
        expand=True,
    )
    if target_fraction is None:
        return ft.Row([bar], spacing=0)

    tf = max(0.0, min(1.0, target_fraction))
    tick_row = ft.Row(
        [
            ft.Container(expand=max(round(tf * 1000), 1)),
            ft.Container(width=2, height=height, bgcolor=p.ink2, opacity=0.4),
            ft.Container(expand=max(round((1 - tf) * 1000), 1)),
        ],
        spacing=0,
    )
    return ft.Row([ft.Stack([bar, tick_row], height=height, expand=True)], spacing=0)
