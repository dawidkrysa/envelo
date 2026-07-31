"""Page header - the eyebrow label + H1 title + trailing actions row repeated
at the top of every screen (`pageHeadStyle` in the design)."""

import flet as ft

from theme import Palette, text_style


def eyebrow(p: Palette, *segments: str) -> ft.Control:
    """Uppercase 11px meta line above the title, e.g. "July 2026 · 9 days left".
    Multiple segments render with a 1px vertical divider between them."""
    parts: list[ft.Control] = []
    for i, seg in enumerate(segments):
        if i > 0:
            parts.append(ft.Container(width=1, height=11, bgcolor=p.line2))
        parts.append(ft.Text(seg.upper(), style=text_style(11, 500, p.ink3, letter_spacing=1.1)))
    return ft.Row(parts, spacing=10)


def page_header(
    p: Palette,
    title: str,
    *,
    eyebrow_segments: list[str] | None = None,
    subtitle: str | None = None,
    actions: list[ft.Control] | None = None,
) -> ft.Control:
    heading: list[ft.Control] = []
    if eyebrow_segments:
        heading.append(eyebrow(p, *eyebrow_segments))
    heading.append(ft.Text(title, style=text_style(26, 600, p.ink, letter_spacing=-0.4)))
    left = ft.Column(heading, spacing=6, tight=True)

    if subtitle and not actions:
        return ft.Row(
            [left, ft.Text(subtitle, style=text_style(12.5, 400, p.ink3))],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.END,
            wrap=True,
            spacing=20,
        )
    if not actions:
        return left
    # No wrap=True on this inner Row: a Wrap whose direct children are the
    # button components (ink= + animate= Containers) renders as a solid
    # placeholder box in Flet 0.86 instead of the buttons - only the outer
    # Row (whose children are Columns/Rows, not bare button Containers) is
    # safe to wrap.
    return ft.Row(
        [left, ft.Row(actions, spacing=8)],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.END,
        wrap=True,
        spacing=20,
    )
