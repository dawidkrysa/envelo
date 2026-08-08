"""Forecast - `isForecast` in the design: projected month-end spending against
what the envelopes hold, a per-group comparison chart and the envelopes trending
over their plan.

**This screen computes no projection of its own.** Every figure comes from
`GET /budget/forecast`, which names the estimator behind it in `method`. That
split is the whole point of the endpoint existing: the straight-line pacing
behind today's numbers is a placeholder for a real predictive model, and when it
is replaced this file does not change. It used to do the arithmetic here - over
the static mock, with a hardcoded 31-day month and an invented `assigned * 0.15`
for envelopes nothing had been spent from - which meant the model would have had
to be built twice to agree with itself.

The envelope and group *names* still come from `fetch_budget_snapshot()`: the
forecast speaks in ids, like every other aggregate, and the snapshot is fetched
anyway for the nav rail.
"""

import asyncio

import flet as ft

from api_client import collect_failures, get_forecast
from components.bar_chart import ForecastGroupBar, forecast_bar_chart
from components.card import flat_card
from components.notice import notice_banner
from components.page_header import page_header
from components.stat_display import mini_stat, stat_block
from currency import format_money, format_short
from dates import days_left_label, month_end_label, month_label
from mock_data import date_short
from theme import palette, text_style
from views.common import app_shell, fetch_budget_snapshot, page_band

_MAX_TRENDING = 6

_BAR_MAX_PX = 88

_METHOD_NOTES = {
    "linear-pace": (
        "Straight-line pace: what you have spent so far this month, scaled to the whole month. "
        "It knows nothing about your habits yet — a rent payment already made counts the same as everyday spending."
    ),
}


def _open_envelope(page: ft.Page, envelope_id: str):
    """Same hand-off as the Dashboard and the Envelopes list: `routing.py` has no
    dynamic route segments, so the id travels in the session store. Every
    "trending over" row used to navigate to `/envelopes/detail` without setting
    it, so all of them opened whichever envelope had been looked at last."""

    def handler(e: ft.ControlEvent) -> None:
        page.session.store.set("selected_envelope_id", envelope_id)
        page.navigate("/envelopes/detail")

    return handler


def _bar_height(value: float, scale: float) -> float:
    """A negative `funded` (an envelope carrying an overspend into the month) has
    no bar to draw, and would otherwise be handed to Flet as a negative height."""
    return max((max(value, 0.0) / scale) * _BAR_MAX_PX, 4)


def _method_note(forecast: dict) -> str:
    """How the numbers were arrived at, in the reader's words.

    An unknown `method` is described rather than hidden: new estimators will
    appear here, and a projection presented with no indication of where it came
    from invites more confidence than a straight line deserves.
    """
    method = forecast.get("method")
    if not method:
        return ""
    explained = _METHOD_NOTES.get(method, f'Estimated by "{method}".')
    as_of = forecast.get("as_of")
    return f"{explained} Based on spending up to {date_short(as_of)}." if as_of else explained


def _empty_note(p, message: str) -> ft.Control:
    return ft.Container(
        content=ft.Text(message, style=text_style(12.5, 400, p.ink3)),
        padding=ft.Padding.only(top=11),
        border=ft.Border(top=ft.BorderSide(1, p.sf3)),
    )


def _trending_row(page: ft.Page, name: str, row: dict) -> ft.Control:
    p = palette(page)
    spent = float(row["spent"])
    projected = float(row["projected"])
    over = projected - float(row["funded"])
    return ft.Container(
        content=ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(name, style=text_style(13.5, 500, p.ink)),
                        ft.Text(
                            f"{format_money(spent)} spent, {format_money(projected)} projected",
                            style=text_style(11.5, 400, p.ink3),
                        ),
                    ],
                    spacing=3,
                    tight=True,
                    expand=True,
                ),
                ft.Text(f"+{format_money(over)}", style=text_style(13.5, 500, p.warn_ink)),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.only(top=11),
        border=ft.Border(top=ft.BorderSide(1, p.sf3)),
        ink=True,
        on_click=_open_envelope(page, row["envelope_id"]),
    )


async def build_forecast_view(page: ft.Page) -> ft.View:
    p = palette(page)
    band = page_band(page)

    # `collect_failures` has to enclose the gather, not follow it: each task
    # copies the context as it is created, so the recorder must already be in
    # place. Without it an unreachable server drew a confident 0,00 zł forecast.
    with collect_failures() as failures:
        snapshot, forecast = await asyncio.gather(fetch_budget_snapshot(), get_forecast())

    group_names = {cg["id"]: cg["name"] for cg in snapshot.category_groups}
    envelope_names = {e["id"]: e["name"] for e in snapshot.envelopes}

    # The baseline is what the envelopes hold - carried over included - not what
    # was assigned this month. Against a monthly top-up alone, an envelope
    # sitting on last month's leftover reads as trending over while it is fine.
    funded_total = float(forecast.get("funded_total") or 0)
    projected_total = float(forecast.get("projected_total") or 0)
    diff = projected_total - funded_total
    over_plan = diff > 0

    bars = []
    for group in forecast.get("category_groups", []):
        funded = float(group["funded"])
        projected = float(group["projected"])
        scale = max(funded, projected, 0.0) or 1.0
        bars.append(
            ForecastGroupBar(
                label=group_names.get(group["category_group_id"], "Unnamed group"),
                amount_label=format_short(projected),
                assigned_height_px=_bar_height(funded, scale),
                projected_height_px=_bar_height(projected, scale),
                color=p.warn if projected > funded else p.ok,
            )
        )

    # Already ranked by the server, most at risk first - re-sorting here would
    # overrule whatever produced the projection.
    trending = [e for e in forecast.get("envelopes", []) if float(e["projected"]) > float(e["funded"])]

    summary = (
        f"At this pace you will spend about {format_money(diff)} more than your envelopes hold. "
        "Move money now and the month still balances."
        if over_plan
        else "You are on pace to stay inside what your envelopes hold."
    )

    stats: list[ft.Control] = [
        ft.Row(
            [
                stat_block(
                    p,
                    "Projected spending",
                    format_money(projected_total),
                    value_size=38,
                    value_color=p.warn_ink if over_plan else p.ok_ink,
                ),
                mini_stat(p, "Available", format_money(funded_total)),
                mini_stat(
                    p,
                    "Difference",
                    format_money(diff),
                    color=p.warn_ink if over_plan else p.ok_ink,
                ),
            ],
            spacing=26,
            wrap=True,
        ),
        ft.Text(summary, style=text_style(13.5, 400, p.ink2)),
    ]

    note = _method_note(forecast)
    if note:
        stats.append(ft.Text(note, style=text_style(11.5, 400, p.ink3)))

    stats.append(
        ft.Container(
            content=(
                forecast_bar_chart(p, bars, projected_label=f"Projected by {month_end_label()}")
                if bars
                else _empty_note(p, "No category groups yet — there is nothing to project.")
            ),
            padding=ft.Padding.only(top=6),
            border=ft.Border(top=ft.BorderSide(1, p.sf3)),
        )
    )

    main_card = flat_card(p, ft.Column(stats, spacing=18), radius=14, padding=20)

    trending_rows: list[ft.Control] = [
        _trending_row(page, envelope_names.get(e["envelope_id"], "Unnamed envelope"), e)
        for e in trending[:_MAX_TRENDING]
    ]
    if len(trending) > _MAX_TRENDING:
        trending_rows.append(
            _empty_note(p, f"and {len(trending) - _MAX_TRENDING} more — see the Envelopes screen.")
        )
    if not trending_rows:
        # Never seen before: the mock always had rows to show here.
        trending_rows.append(_empty_note(p, "Nothing is trending over its plan."))

    trending_card = flat_card(
        p,
        ft.Column(
            [ft.Text("TRENDING OVER", style=text_style(12, 600, p.ink3, letter_spacing=0.8)), *trending_rows],
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
        page_header(p, "Forecast", eyebrow_segments=[month_label(), days_left_label()]),
    ]

    # Before the numbers, not after: a projection built from part of the data is
    # not a projection, and the reader has to know that before reading it.
    if failures:
        body.append(
            notice_banner(
                p,
                "Couldn't reach the server, so this forecast is incomplete "
                f"({', '.join(sorted(set(failures)))}). Treat the figures below as partial.",
            )
        )

    body.append(charts_row)

    return await app_shell(page, "/forecast", "forecast", body, snapshot=snapshot)
