"""Alerts - `isAlerts` in the design: the last 30 days of heads-up
notifications, sorted newest first."""

import flet as ft

from components.alert_row import AlertItem, alert_history_row
from components.card import bordered_panel
from components.page_header import page_header
from mock_data import ALERT_HISTORY
from theme import palette, text_style
from views.common import app_shell

THRESHOLD = 80


async def build_alerts_view(page: ft.Page) -> ft.View:
    p = palette(page)

    def on_fix(target: str):
        return lambda e: page.navigate(target)

    body: list[ft.Control] = [
        ft.Column(
            [
                page_header(p, "Alerts", eyebrow_segments=["Last 30 days"]),
                ft.Text(f"Heads-up at {THRESHOLD}% of an envelope", style=text_style(12.5, 400, p.ink3)),
            ],
            spacing=6,
        ),
        bordered_panel(
            p,
            [
                alert_history_row(
                    p,
                    AlertItem(
                        message="",
                        title=a["title"],
                        meta=a["meta"],
                        cta=a["cta"],
                        dot_color=p.over if a["over"] else p.warn,
                        on_fix=on_fix("/forecast" if a["cta"] == "Forecast" else "/envelopes/detail"),
                    ),
                )
                for a in ALERT_HISTORY
            ],
        ),
    ]

    return app_shell(page, "/alerts", "alerts", body)
