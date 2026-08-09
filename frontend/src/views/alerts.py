"""Alerts - `isAlerts` in the design: every envelope that needs attention right
now, worst first.

**Computed live, not read from a log.** There is no alerts table and no
notification history in the schema, so the mock's "Yesterday, 17:42 · sent by
email" was inventing three things at once: a timestamp, a delivery channel, and
the fact that anything had been sent at all. What the data really supports is the
present tense - which envelopes are over, and which are close - and that is what
this screen now says.

Storing these would mean caching a pure function of the envelopes, which buys
nothing until something actually delivers a notification and needs to know
whether it already has. When a notifier exists, an `alerts` table earns its
migration; until then this screen is the honest version.

Forecast-based alerts ("you are on pace to overspend") are deliberately absent:
`GET /budget/forecast` returns a straight-line placeholder today, and a warning
is a poor use of a guess. The Forecast screen shows the same figures with the
estimator named beside them, which a heads-up cannot do.
"""

import flet as ft

from api_client import collect_failures
from components.alert_row import AlertItem, alert_history_row
from components.card import bordered_panel
from components.notice import notice_banner
from components.page_header import page_header
from currency import format_money
from dates import days_left_label, month_label
from mock_data import Envelope, envelope_state, envelope_view
from preferences import alert_threshold
from theme import palette, text_style
from views.common import app_shell, fetch_budget_snapshot


def _open_envelope(page: ft.Page, envelope_id: str):
    """Same hand-off as every other screen that opens an envelope: the id travels
    in `page.session.store` because `routing.py` has no dynamic route segments."""

    def handler(e: ft.ControlEvent) -> None:
        page.session.store.set("selected_envelope_id", envelope_id)
        page.navigate("/envelopes/detail")

    return handler


def _severity(e: Envelope) -> tuple[int, float]:
    """Over-plan envelopes first, ranked by how far over; then the ones getting
    close, ranked by how much of them is gone. Sorted descending."""
    funded = e.funded
    if envelope_state(e) == "over":
        return (1, e.spent - funded)
    return (0, e.spent / funded if funded > 0 else 0.0)


def _alert_item(page: ft.Page, e: Envelope) -> AlertItem:
    p = palette(page)
    ev = envelope_view(p, e)
    over = ev.state == "over"

    if over:
        title = f"{e.name} is {format_money(e.spent - e.funded)} over its plan"
        detail = f"{format_money(e.spent)} spent of {format_money(e.funded)}"
    else:
        title = f"{e.name} is at {ev.pct}% with {days_left_label()}"
        detail = f"{ev.left_str} left of {format_money(e.funded)}"

    # Only facts the data actually holds. The group name is filled in by
    # `BudgetSnapshot.envelope_models()`; when there is none, the separator goes
    # too rather than leaving a stray middle dot.
    meta = " · ".join(part for part in (e.group_name, detail) if part)

    return AlertItem(
        message="",
        title=title,
        meta=meta,
        cta="Open",
        dot_color=p.over if over else p.warn,
        on_fix=_open_envelope(page, e.id),
    )


async def build_alerts_view(page: ft.Page) -> ft.View:
    p = palette(page)

    with collect_failures() as failures:
        snapshot = await fetch_budget_snapshot()

    off_track = sorted(
        (e for e in snapshot.envelope_models() if envelope_state(e) != "ok"),
        key=_severity,
        reverse=True,
    )

    heading = ft.Column(
        [
            page_header(p, "Alerts", eyebrow_segments=[month_label(), days_left_label()]),
            ft.Text(
                f"Heads-up at {alert_threshold()}% of an envelope — your Settings threshold, "
                "worked out from your envelopes as they stand right now.",
                style=text_style(12.5, 400, p.ink3),
            ),
        ],
        spacing=6,
    )

    body: list[ft.Control] = [heading]

    if failures:
        body.append(
            notice_banner(
                p,
                "Couldn't reach the server, so some envelopes may be missing from this list "
                f"({', '.join(sorted(set(failures)))}).",
            )
        )

    if off_track:
        rows: list[ft.Control] = [alert_history_row(p, _alert_item(page, e)) for e in off_track]
    else:
        # A real possibility now that the list is computed rather than fixed:
        # the mock could never be empty, so this state had no copy at all.
        rows = [
            ft.Container(
                content=ft.Text(
                    "Nothing needs attention — every envelope is inside what it holds.",
                    style=text_style(13, 400, p.ink3),
                ),
                padding=ft.Padding.symmetric(horizontal=17, vertical=18),
            )
        ]

    body.append(bordered_panel(p, rows))

    return await app_shell(page, "/alerts", "alerts", body, snapshot=snapshot)
