"""Settings - `isSettings` in the design: alert threshold, notification
channel, currency, appearance and sign-out.

Currency and appearance are real and persist; the threshold slider keeps its own
visual state per the brief, and the notification select is still decorative.
"""

import flet as ft

from components.button import danger_button
from components.card import flat_card
from components.page_header import page_header
from components.select_field import select_field
from components.toggle_switch import toggle_switch
from currency import CURRENCIES, CURRENCY_STORAGE_KEY, current_currency, set_currency
from theme import palette, text_style
from views.common import app_shell


async def build_settings_view(page: ft.Page) -> ft.View:
    p = palette(page)
    state = {"threshold": 80}

    threshold_value = ft.Text(f"{state['threshold']}%", style=text_style(16, 600, p.warn_ink))

    def on_threshold(e: ft.ControlEvent) -> None:
        state["threshold"] = int(e.control.value)
        threshold_value.value = f"{state['threshold']}%"
        page.update()

    threshold_card = flat_card(
        p,
        ft.Column(
            [
                ft.Row(
                    [ft.Text("Warn me at", style=text_style(14, 600, p.ink)), threshold_value],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Slider(min=50, max=100, divisions=10, value=80, active_color=p.ok, on_change=on_threshold),
                ft.Text(
                    "You will get a heads-up once an envelope reaches this share of its money.",
                    style=text_style(12.5, 400, p.ink3),
                ),
            ],
            spacing=9,
        ),
        radius=13,
        padding=ft.Padding.symmetric(horizontal=20, vertical=19),
    )

    async def on_theme_change(e: ft.ControlEvent) -> None:
        # Every screen bakes its palette's colors into each control's
        # bgcolor/text style at build time (theme.palette(page) is only
        # read once, not re-evaluated live) - flipping page.theme_mode
        # alone recolors Flutter's own Material widgets but leaves all of
        # that already-built content in the old palette. Re-running the
        # same full rebuild main.py's on_route_change does for every
        # route/band change is what actually repaints this screen (and
        # the nav rail) in the new palette.
        page.theme_mode = ft.ThemeMode.DARK if e.control.value else ft.ThemeMode.LIGHT
        page.bgcolor = palette(page).canvas
        if page.on_route_change:
            await page.on_route_change(e)
        else:
            page.update()

    async def on_currency_change(e: ft.ControlEvent) -> None:
        # Same full-rebuild trick as the theme toggle above, for the same reason:
        # every screen formats its amounts once at build time, so flipping the
        # currency has no effect on anything already on screen until the route is
        # rebuilt. Persisted so the choice survives a reload - there is no
        # user-settings table on the backend, so this stays client-side.
        set_currency(e.control.value)
        await page.shared_preferences.set(CURRENCY_STORAGE_KEY, current_currency())
        if page.on_route_change:
            await page.on_route_change(e)
        else:
            page.update()

    def settings_row(label: str, hint: str, control: ft.Control) -> ft.Container:
        return flat_card(
            p,
            ft.Row(
                [
                    ft.Column(
                        [ft.Text(label, style=text_style(14, 600, p.ink)), ft.Text(hint, style=text_style(12.5, 400, p.ink3))],
                        spacing=3,
                        tight=True,
                        expand=True,
                    ),
                    control,
                ],
                # No wrap=True here: the label/hint Column is a flex (expand)
                # child, and a Wrap cannot contain a flex child.
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            radius=13,
            padding=ft.Padding.symmetric(horizontal=20, vertical=17),
        )

    rows = [
        settings_row(
            "Notifications",
            "Where your heads-ups go.",
            select_field(p, [("email", "Email"), ("webhook", "Webhook"), ("both", "Email and webhook")], value="email", width=190),
        ),
        settings_row(
            "Currency",
            "Used for every amount in Envelo.",
            select_field(
                p,
                [(code, cf.label) for code, cf in CURRENCIES.items()],
                value=current_currency(),
                width=230,
                on_select=on_currency_change,
            ),
        ),
        settings_row(
            "Appearance",
            "Dark — easier at night." if page.theme_mode == ft.ThemeMode.DARK else "Light — the default.",
            toggle_switch(p, page.theme_mode == ft.ThemeMode.DARK, on_theme_change),
        ),
        flat_card(
            p,
            ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text("Sign out", style=text_style(14, 600, p.ink)),
                            ft.Text("You will need your email and password to get back in.", style=text_style(12.5, 400, p.ink3)),
                        ],
                        spacing=3,
                        tight=True,
                    ),
                    danger_button(p, "Sign out", lambda e: page.navigate("/login")),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            radius=13,
            padding=ft.Padding.symmetric(horizontal=20, vertical=17),
        ),
    ]

    body: list[ft.Control] = [
        page_header(p, "Settings", eyebrow_segments=["Dawid Krysa · dawid@envelo.local"]),
        ft.Column([threshold_card, *rows], spacing=11, width=660),
    ]

    return await app_shell(page, "/settings", "settings", body)
