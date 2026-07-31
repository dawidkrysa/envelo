"""Forecast - `isForecast` in the design: projected month-end spending vs
what was assigned, a per-group comparison chart and the envelopes trending
over their plan."""

import flet as ft

from components.bar_chart import ForecastGroupBar, forecast_bar_chart
from components.card import flat_card
from components.page_header import page_header
from components.stat_display import mini_stat, stat_block
from mock_data import DAYS_LEFT, GROUPS, MONTH, all_envelopes, format_money, format_short
from theme import palette, text_style
from views.common import app_shell, page_band


async def build_forecast_view(page: ft.Page) -> ft.View:
    p = palette(page)
    band = page_band(page)

    rate = (31 - DAYS_LEFT) / 31
    envelopes = all_envelopes()

    def projected(e) -> float:
        return max(e.spent / rate, e.spent) if e.spent > 0 else e.assigned * 0.15

    assigned_total = sum(e.assigned for e in envelopes)
    projected_total = sum(projected(e) for e in envelopes)
    diff = projected_total - assigned_total

    bars = []
    for g in GROUPS:
        ga = sum(e.assigned for e in g.envelopes)
        gp = sum(projected(e) for e in g.envelopes)
        m = max(ga, gp) or 1
        bars.append(
            ForecastGroupBar(
                label=g.name,
                amount_label=format_short(gp),
                assigned_height_px=max((ga / m) * 88, 4),
                projected_height_px=max((gp / m) * 88, 4),
                color=p.warn if gp > ga else p.ok,
            )
        )

    trending = [
        e
        for e in envelopes
        if e.spent > 0 and e.spent / rate > e.assigned
    ]

    summary = (
        f"At your current pace you will spend about {format_money(diff)} more than you assigned. "
        "Move money now and the month still balances."
        if projected_total > assigned_total
        else "You are on pace to stay inside what you assigned this month."
    )

    main_card = flat_card(
        p,
        ft.Column(
            [
                ft.Row(
                    [
                        stat_block(p, "Projected spending", format_money(projected_total), value_size=38, value_color=p.warn_ink),
                        mini_stat(p, "Assigned", format_money(assigned_total)),
                        mini_stat(p, "Difference", format_money(diff), color=p.warn_ink),
                    ],
                    spacing=26,
                    wrap=True,
                ),
                ft.Text(summary, style=text_style(13.5, 400, p.ink2)),
                ft.Container(
                    content=forecast_bar_chart(p, bars),
                    padding=ft.Padding.only(top=6),
                    border=ft.Border(top=ft.BorderSide(1, p.sf3)),
                ),
            ],
            spacing=18,
        ),
        radius=14,
        padding=20,
    )

    trending_card = flat_card(
        p,
        ft.Column(
            [
                ft.Text("TRENDING OVER", style=text_style(12, 600, p.ink3, letter_spacing=0.8)),
                *[
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Text(e.name, style=text_style(13.5, 500, p.ink)),
                                        ft.Text(
                                            f"spending {format_money(e.spent)} so far this month",
                                            style=text_style(11.5, 400, p.ink3),
                                        ),
                                    ],
                                    spacing=3,
                                    tight=True,
                                ),
                                ft.Text(f"+{format_money(e.spent / rate - e.assigned)}", style=text_style(13.5, 500, p.warn_ink)),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        padding=ft.Padding.only(top=11),
                        border=ft.Border(top=ft.BorderSide(1, p.sf3)),
                        ink=True,
                        on_click=lambda e_: page.navigate("/envelopes/detail"),
                    )
                    for e in trending
                ],
            ],
            spacing=11,
        ),
        radius=14,
        padding=20,
    )

    charts_row = (
        ft.Column([main_card, trending_card], spacing=18)
        if band != "desktop"
        else ft.Row(
            [ft.Container(content=main_card, expand=135), ft.Container(content=trending_card, expand=100)],
            spacing=18,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
    )

    body: list[ft.Control] = [
        page_header(p, "Forecast", eyebrow_segments=[MONTH, f"{DAYS_LEFT} days left"]),
        charts_row,
    ]

    return app_shell(page, "/forecast", "forecast", body)
