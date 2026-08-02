"""Left nav sidebar (desktop/tablet) and bottom nav bar (mobile) - the `<nav>`
shell shared by every screen, plus its "category groups" quick-jump list and
user footer.

Icons are approximated with the closest Material glyph in `ft.Icons`; the
design draws its own single-stroke SVG paths, which Flet controls cannot
render directly without embedding raster/SVG assets.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

import flet as ft

from theme import RADIUS_BUTTON, RADIUS_PILL, RADIUS_TILE, Palette, text_style

# Dark warm-brown ink for the amber count badge - fixed in the design
# regardless of light/dark mode.
_COUNT_INK = "#331F05"

ICONS: dict[str, str] = {
    "dashboard": ft.Icons.GRID_VIEW_ROUNDED,
    "envelopes": ft.Icons.MAIL_OUTLINE_ROUNDED,
    "transactions": ft.Icons.REORDER_ROUNDED,
    "forecast": ft.Icons.SHOW_CHART_ROUNDED,
    "alerts": ft.Icons.ERROR_OUTLINE_ROUNDED,
    "import": ft.Icons.UPLOAD_FILE_OUTLINED,
    "statements": ft.Icons.DESCRIPTION_OUTLINED,
    "rules": ft.Icons.OUTLINED_FLAG_ROUNDED,
    "accounts": ft.Icons.ACCOUNT_BALANCE_OUTLINED,
    "settings": ft.Icons.SETTINGS_OUTLINED,
    "payees": ft.Icons.PEOPLE_OUTLINE_ROUNDED,
}


@dataclass(frozen=True)
class NavItem:
    id: str
    label: str
    route: str
    count: int = 0


@dataclass(frozen=True)
class NavGroup:
    title: str
    items: list[NavItem] = field(default_factory=list)


NAV_GROUPS: list[NavGroup] = [
    NavGroup("Budget", [
        NavItem("dashboard", "Dashboard", "/dashboard"),
        NavItem("envelopes", "Envelopes", "/envelopes"),
        NavItem("transactions", "Transactions", "/transactions"),
    ]),
    NavGroup("Insights", [
        NavItem("forecast", "Forecast", "/forecast"),
        NavItem("alerts", "Alerts", "/alerts"),
    ]),
    NavGroup("Import", [
        NavItem("import", "Import statement", "/import"),
        NavItem("statements", "Statements", "/statements"),
        NavItem("rules", "Rules", "/rules"),
    ]),
    NavGroup("Setup", [
        NavItem("accounts", "Accounts", "/accounts"),
        NavItem("payees", "Payees", "/payees"),
        NavItem("settings", "Settings", "/settings"),
    ]),
]

# The mobile bottom bar only has room for the five most-used destinations.
MOBILE_NAV_IDS = {"dashboard", "envelopes", "transactions", "alerts", "settings"}


def _count_badge(count: int) -> ft.Container:
    return ft.Container(
        content=ft.Text(str(count), style=text_style(10, 600, _COUNT_INK)),
        bgcolor="#CD9219",
        border_radius=RADIUS_PILL,
        width=17,
        height=17,
        alignment=ft.Alignment.CENTER,
    )


def _sidebar_item(p: Palette, item: NavItem, active: bool, compact: bool, on_click: Callable) -> ft.Container:
    row: list[ft.Control] = [
        ft.Icon(ICONS.get(item.id, ft.Icons.CIRCLE_OUTLINED), size=17, color=p.ok if active else p.ink3),
    ]
    if not compact:
        row.append(
            ft.Text(
                item.label,
                style=text_style(13.5, 600 if active else 400, p.ink if active else p.ink2),
                expand=True,
            )
        )
        if item.count:
            row.append(_count_badge(item.count))
    return ft.Container(
        content=ft.Row(row, spacing=0 if compact else 10, alignment=ft.MainAxisAlignment.CENTER if compact else ft.MainAxisAlignment.START),
        bgcolor=p.ok_fill if active else "transparent",
        border_radius=RADIUS_BUTTON,
        height=42 if compact else 36,
        padding=0 if compact else ft.Padding.symmetric(horizontal=11),
        ink=True,
        on_click=on_click,
        tooltip=item.label if compact else None,
    )


def _bottom_item(p: Palette, item: NavItem, active: bool, on_click: Callable) -> ft.Container:
    return ft.Container(
        content=ft.Column(
            [
                ft.Icon(ICONS.get(item.id, ft.Icons.CIRCLE_OUTLINED), size=21, color=p.ok if active else p.ink3),
                ft.Text(item.label, style=text_style(10.5, 500, p.ink if active else p.ink3)),
            ],
            spacing=5,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        alignment=ft.Alignment.CENTER,
        expand=True,
        ink=True,
        on_click=on_click,
    )


def brand_mark(p: Palette, *, show_wordmark: bool = True, scale: float = 1.0) -> ft.Row:
    """The "E" tile + "Envelo" wordmark, reused in the nav (compact, default
    scale) and as the larger hero lockup above the login/first-run card
    (`scale` > 1) - sized as a group so the tile, glyph, wordmark and gap
    stay in proportion instead of just the text growing on its own."""
    tile = 28 * scale
    parts: list[ft.Control] = [
        ft.Container(
            content=ft.Text("E", style=text_style(13 * scale, 500, p.on_brand)),
            width=tile,
            height=tile,
            bgcolor=p.brand,
            border_radius=RADIUS_TILE * scale,
            alignment=ft.Alignment.CENTER,
        )
    ]
    if show_wordmark:
        parts.append(ft.Text("Envelo", style=text_style(15 * scale, 600, p.ink, letter_spacing=-0.15)))
    return ft.Row(parts, spacing=10 * scale)


@dataclass(frozen=True)
class CategoryGroupNav:
    """A row in the sidebar's "Category groups" quick-jump list."""

    name: str
    left_str: str
    bar_color: str
    on_click: Callable[[ft.ControlEvent], None] | None = None


def build_nav(
    p: Palette,
    band: str,
    active_id: str,
    navigate: Callable[[str], None],
    attention_count: int = 0,
    category_groups: list[CategoryGroupNav] | None = None,
) -> ft.Control:
    """`band` is "mobile" | "tablet" | "desktop" from `theme.layout_band`."""
    is_mobile = band == "mobile"
    is_tablet = band == "tablet"
    is_desktop = band == "desktop"

    def with_count(item: NavItem) -> NavItem:
        return item if item.id != "alerts" else NavItem(item.id, item.label, item.route, attention_count)

    if is_mobile:
        items = [
            with_count(i)
            for g in NAV_GROUPS
            for i in g.items
            if i.id in MOBILE_NAV_IDS
        ]
        return ft.Container(
            content=ft.Row(
                [_bottom_item(p, i, i.id == active_id, lambda e, r=i.route: navigate(r)) for i in items],
                spacing=0,
            ),
            height=66,
            padding=ft.Padding.symmetric(horizontal=6),
            bgcolor=p.sf,
            border=ft.Border(top=ft.BorderSide(1, p.line)),
        )

    sections: list[ft.Control] = []
    if not is_tablet:
        sections.append(ft.Container(content=brand_mark(p), padding=ft.Padding.symmetric(vertical=4, horizontal=6)))
        sections.append(ft.Container(height=6))

    for gi, group in enumerate(NAV_GROUPS):
        group_children: list[ft.Control] = []
        if not is_tablet:
            group_children.append(ft.Text(group.title.upper(), style=text_style(10.5, 600, p.ink3, letter_spacing=1.3)))
        elif gi > 0:
            group_children.append(ft.Container(width=22, height=1, bgcolor=p.line, margin=ft.Margin.symmetric(vertical=5)))
        for item in group.items:
            group_children.append(
                _sidebar_item(
                    p,
                    with_count(item),
                    item.id == active_id or (item.id == "envelopes" and active_id == "detail"),
                    is_tablet,
                    lambda e, r=item.route: navigate(r),
                )
            )
        sections.append(ft.Column(group_children, spacing=2))

    # The design pins "Category groups" and the user footer to the bottom of
    # the sidebar (`margin-top:auto`); putting the scrolling nav list in an
    # `expand=True` sibling above them reproduces that without a fixed offset.
    footer_sections: list[ft.Control] = []
    if is_desktop and category_groups:
        footer_sections.append(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [ft.Text("CATEGORY GROUPS", style=text_style(10, 500, p.ink3, letter_spacing=1))],
                        ),
                        *(
                            ft.Container(
                                content=ft.Row(
                                    [
                                        ft.Container(width=3, height=15, bgcolor=g.bar_color, border_radius=2),
                                        ft.Text(g.name, style=text_style(12.5, 400, p.ink2), expand=True, no_wrap=True),
                                        ft.Text(g.left_str, style=text_style(11, 400, p.ink3)),
                                    ],
                                    spacing=9,
                                ),
                                height=32,
                                padding=ft.Padding.symmetric(horizontal=12),
                                border_radius=RADIUS_TILE,
                                ink=True,
                                on_click=g.on_click,
                            )
                            for g in category_groups
                        ),
                    ],
                    spacing=2,
                ),
                padding=ft.Padding.only(top=12),
                border=ft.Border(top=ft.BorderSide(1, p.sf3)),
            )
        )
    if is_desktop:
        footer_sections.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Container(
                            content=ft.Text("DK", style=text_style(11.5, 500, p.link)),
                            width=28,
                            height=28,
                            bgcolor=p.ok_fill,
                            border_radius=RADIUS_PILL,
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Column(
                            [
                                ft.Text("Dawid Krysa", style=text_style(12.5, 500, p.ink)),
                                ft.Text("Settings", style=text_style(11, 400, p.ink3)),
                            ],
                            spacing=1,
                            tight=True,
                        ),
                    ],
                    spacing=10,
                ),
                padding=ft.Padding.symmetric(horizontal=12, vertical=11),
                border=ft.Border(top=ft.BorderSide(1, p.line)),
            )
        )

    return ft.Container(
        content=ft.Column(
            [
                ft.Column(sections, spacing=14, expand=True, scroll=ft.ScrollMode.HIDDEN),
                *footer_sections,
            ],
            spacing=14,
            expand=True,
        ),
        width=74 if is_tablet else 244,
        padding=ft.Padding.symmetric(horizontal=10, vertical=16),
        bgcolor=p.sf,
        border=ft.Border(right=ft.BorderSide(1, p.line)),
    )
