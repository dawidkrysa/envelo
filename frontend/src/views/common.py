"""Shared page shell - nav rail/bottom bar + scrollable content column reused
by every screen. The design's own device-frame preview chrome (the bordered,
drop-shadowed rectangle simulating a phone/tablet in the design tool) is not
reproduced here: a real app fills its actual window instead of a mockup frame.
"""

import asyncio

import flet as ft

from api_client import (
    get_category_groups,
    get_envelope_allocations,
    get_envelopes,
    get_spent_by_envelope,
)
from components.nav_rail import CategoryGroupNav, build_nav
from currency import format_money
from mock_data import envelope_state
from theme import Palette, content_padding, layout_band, palette
from utils import range_to_dates, to_envelope


def page_band(page: ft.Page) -> str:
    return layout_band(getattr(page, "width", None))


async def category_group_nav(p: Palette, page: ft.Page) -> tuple[list[CategoryGroupNav], int]:
    """Real "left" per category group for the sidebar's quick-jump list, plus how
    many envelopes need attention - mirrors the assigned/spent math
    `views/envelopes.py` does for its own Ledger/Cards/Flow tabs, just re-fetched
    and recomputed here since the nav is shared chrome built independently of
    that screen.

    The attention count comes back from here rather than being computed by the
    caller because this is where the real envelopes already are: it used to be
    `len(attention_envelopes())` over the static mock, so the sidebar badge
    showed the same 3 forever, next to group totals that were real.
    """
    date_from, date_to = range_to_dates("this")
    # Concurrently: the nav is rebuilt on every screen and after every write, so
    # four serial round trips here were a tax on all of them.
    category_groups, envelopes, allocations, spent = await asyncio.gather(
        get_category_groups(),
        get_envelopes(),
        get_envelope_allocations(),
        get_spent_by_envelope(date_from=date_from, date_to=date_to),
    )

    allocation_by_envelope = {a["envelope_id"]: a for a in allocations if a["month"] == date_from.isoformat()}

    items = []
    attention = 0
    for cg in category_groups:
        group_envs = [
            to_envelope(
                e,
                float(allocation_by_envelope[e["id"]]["assigned_amount"]) if e["id"] in allocation_by_envelope else 0.0,
                spent.get(e["id"], 0.0),
            )
            for e in envelopes
            if e["category_group_id"] == cg["id"]
        ]
        left = sum(e.assigned - e.spent for e in group_envs)
        off_track = [e for e in group_envs if envelope_state(e) != "ok"]
        attention += len(off_track)
        items.append(
            CategoryGroupNav(
                name=cg["name"],
                left_str=f"{format_money(left)} left",
                bar_color=p.warn if off_track else p.ok_border,
                on_click=lambda e, gid=cg["id"]: page.navigate("/envelopes"),
            )
        )
    return items, attention


def _content_column(page: ft.Page, band: str, body: list[ft.Control]) -> ft.Column:
    content = ft.Container(
        content=ft.Column(body, spacing=20),
        padding=content_padding(band),
    )
    return ft.Column([content], scroll=ft.ScrollMode.AUTO, expand=True, spacing=0)


async def app_shell(page: ft.Page, route: str, active_nav_id: str, body: list[ft.Control]) -> ft.View:
    """Every main screen: nav + a scrollable content column with the correct
    per-breakpoint padding (`padStyle` in the design)."""
    p = palette(page)
    band = page_band(page)

    def navigate(target: str) -> None:
        page.navigate(target)

    async def build_nav_control() -> ft.Control:
        category_groups, attention_count = await category_group_nav(p, page)
        return build_nav(
            p,
            band,
            active_nav_id,
            navigate,
            attention_count=attention_count,
            category_groups=category_groups,
        )

    nav_holder = ft.Container(content=await build_nav_control())

    async def refresh_nav() -> None:
        """The nav is only rebuilt from scratch on a full route change
        otherwise, so a view that renames/deletes a group or otherwise
        changes an envelope's assigned/spent amount without navigating
        away (e.g. `views/envelopes.py`'s `refresh_envelopes`) calls this
        - via `page.refresh_nav` - to keep the sidebar's names/totals from
        going stale while you stay on the page."""
        nav_holder.content = await build_nav_control()
        page.update()

    page.refresh_nav = refresh_nav

    main = _content_column(page, band, body)

    if band == "mobile":
        shell: ft.Control = ft.Column([main, nav_holder], expand=True, spacing=0)
    else:
        shell = ft.Row([nav_holder, main], expand=True, spacing=0, vertical_alignment=ft.CrossAxisAlignment.STRETCH)

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
