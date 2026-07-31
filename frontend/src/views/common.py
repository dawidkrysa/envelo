"""Shared page shell - nav rail/bottom bar + scrollable content column reused
by every screen. The design's own device-frame preview chrome (the bordered,
drop-shadowed rectangle simulating a phone/tablet in the design tool) is not
reproduced here: a real app fills its actual window instead of a mockup frame.
"""

import flet as ft

from components.nav_rail import CategoryGroupNav, build_nav
from mock_data import GROUP_BAR_COLOR, GROUPS, attention_envelopes, format_money
from theme import Palette, content_padding, layout_band, palette


def page_band(page: ft.Page) -> str:
    return layout_band(getattr(page, "width", None))


def category_group_nav(p: Palette, page: ft.Page) -> list[CategoryGroupNav]:
    items = []
    for g in GROUPS:
        left = sum(e.assigned - e.spent for e in g.envelopes)
        color = p.warn if GROUP_BAR_COLOR.get(g.id) == "warn" else p.ok_border
        items.append(
            CategoryGroupNav(
                name=g.name,
                left_str=f"{format_money(left)} left",
                bar_color=color,
                on_click=lambda e, gid=g.id: page.navigate("/envelopes"),
            )
        )
    return items


def _content_column(page: ft.Page, band: str, body: list[ft.Control]) -> ft.Column:
    content = ft.Container(
        content=ft.Column(body, spacing=20),
        padding=content_padding(band),
    )
    return ft.Column([content], scroll=ft.ScrollMode.AUTO, expand=True, spacing=0)


def app_shell(page: ft.Page, route: str, active_nav_id: str, body: list[ft.Control]) -> ft.View:
    """Every main screen: nav + a scrollable content column with the correct
    per-breakpoint padding (`padStyle` in the design)."""
    p = palette(page)
    band = page_band(page)

    def navigate(target: str) -> None:
        page.navigate(target)

    nav = build_nav(
        p,
        band,
        active_nav_id,
        navigate,
        attention_count=len(attention_envelopes()),
        category_groups=category_group_nav(p, page),
    )

    main = _content_column(page, band, body)

    if band == "mobile":
        shell: ft.Control = ft.Column([main, nav], expand=True, spacing=0)
    else:
        shell = ft.Row([nav, main], expand=True, spacing=0, vertical_alignment=ft.CrossAxisAlignment.STRETCH)

    return ft.View(
        route=route,
        controls=[shell],
        padding=0,
        spacing=0,
        bgcolor=p.canvas,
    )


def standalone_shell(page: ft.Page, route: str, body: list[ft.Control]) -> ft.View:
    """A screen with no nav rail - Login and First-run sit outside the app
    proper (pre-auth / pre-setup), so they aren't part of the persistent nav
    and don't show the sidebar."""
    p = palette(page)
    band = page_band(page)
    main = _content_column(page, band, body)

    return ft.View(
        route=route,
        controls=[main],
        padding=0,
        spacing=0,
        bgcolor=p.canvas,
    )
