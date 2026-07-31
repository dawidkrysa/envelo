"""Envelopes - `isEnvelopes` in the design: the assign bar, alerts, and the
Ledger/Cards/Flow variant tabs over every category group.

Tab selection, sort, the "needs attention only" filter and group
collapse/expand are local visual state (no persistence, no real assignment
logic) - each interaction just re-renders this screen's content container.
"""

import flet as ft

from components.alert_row import AlertItem, alert_banner
from components.button import primary_button, secondary_button
from components.card import bordered_panel, flat_card
from components.envelope_card import envelope_card
from components.envelope_flow_row import envelope_flow_row
from components.envelope_row import envelope_ledger_row
from components.page_header import page_header
from components.select_field import select_field
from components.stat_display import stat_block
from components.table_header import table_header
from components.tabs import segmented_tabs
from mock_data import (
    DAYS_LEFT,
    GROUPS,
    MONTH,
    POOL,
    attention_envelopes,
    envelope_state,
    envelope_view,
    format_money,
)
from theme import palette, text_style
from views.common import app_shell, page_band
from views.dialogs import move_dialog, new_envelope_dialog

_SORTERS = {
    "left": lambda e: (e.assigned - e.spent),
    "used": lambda e: -(e.spent / max(e.assigned, 1)),
    "name": lambda e: e.name,
}


def _alerts(p) -> list[AlertItem]:
    ranked = sorted(attention_envelopes(), key=lambda e: 1 if envelope_state(e) == "over" else 0, reverse=True)
    items = []
    for e in ranked[:2]:
        ev = envelope_view(p, e)
        over = ev.state == "over"
        message = (
            f"{e.name} is {format_money(e.spent - e.assigned)} over its plan"
            if over
            else f"{e.name} is at {ev.pct}% — {ev.state_label}"
        )
        items.append(AlertItem(message=message, cta="Cover it" if over else "Move money", dot_color=p.over if over else p.warn))
    return items


async def build_envelopes_view(page: ft.Page) -> ft.View:
    p = palette(page)
    band = page_band(page)
    state = {"variant": "ledger", "attention_only": False, "sort": "default", "collapsed": {}}

    def open_detail(e: ft.ControlEvent) -> None:
        page.navigate("/envelopes/detail")

    def ledger_content() -> ft.Control:
        columns = [("ENVELOPE", 2, ft.TextAlign.LEFT)]
        if band != "mobile":
            columns += [("ASSIGNED", 1, ft.TextAlign.RIGHT), ("SPENT", 1, ft.TextAlign.RIGHT)]
        columns.append(("LEFT", 1, ft.TextAlign.RIGHT))
        if band == "desktop":
            columns.append(("PROGRESS", 2, ft.TextAlign.LEFT))

        rows: list[ft.Control] = [table_header(p, columns)]
        for g in GROUPS:
            envs = list(g.envelopes)
            if state["attention_only"]:
                envs = [e for e in envs if envelope_state(e) != "ok"]
            if state["sort"] in _SORTERS:
                envs = sorted(envs, key=_SORTERS[state["sort"]])
            if not envs:
                continue
            left = sum(e.assigned - e.spent for e in envs)
            collapsed = state["collapsed"].get(g.id, False)

            def toggle(e: ft.ControlEvent, gid: str = g.id) -> None:
                state["collapsed"][gid] = not state["collapsed"].get(gid, False)
                rerender()

            rows.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Text("▸" if collapsed else "▾", style=text_style(11, 500, p.ink3)),
                                    ft.Text(g.name, style=text_style(13.5, 600, p.ink)),
                                ],
                                spacing=9,
                            ),
                            ft.Text(f"{format_money(left)} left", style=text_style(13, 500, p.ink2)),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    padding=ft.Padding.symmetric(horizontal=18, vertical=12),
                    bgcolor=p.sf2,
                    border=ft.Border(bottom=ft.BorderSide(1, p.sf3)),
                    ink=True,
                    on_click=toggle,
                )
            )
            if not collapsed:
                for e in envs:
                    rows.append(envelope_ledger_row(p, envelope_view(p, e), band, on_open=open_detail))

        rows.append(
            ft.Container(
                content=ft.Text("+ Add category group", style=text_style(13, 500, p.ink3)),
                padding=ft.Padding.symmetric(horizontal=18, vertical=14),
                bgcolor=p.sf,
                ink=True,
            )
        )
        return bordered_panel(p, rows)

    def cards_content() -> ft.Control:
        sections = []
        for g in GROUPS:
            left = sum(e.assigned - e.spent for e in g.envelopes)
            cards = [
                ft.Container(
                    content=envelope_card(p, envelope_view(p, e), on_open=open_detail),
                    col={"xs": 12, "sm": 6, "lg": 4},
                )
                for e in g.envelopes
            ]
            sections.append(
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(g.name.upper(), style=text_style(13, 600, p.ink3, letter_spacing=0.6)),
                                ft.Text(f"{format_money(left)} left", style=text_style(12.5, 500, p.ink2)),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.ResponsiveRow(cards, spacing=14, run_spacing=14),
                    ],
                    spacing=12,
                )
            )
        return ft.Column(sections, spacing=26)

    def flow_content() -> ft.Control:
        rows = [envelope_flow_row(p, envelope_view(p, e), on_open=open_detail) for g in GROUPS for e in g.envelopes]
        return ft.Container(
            content=ft.Column(rows, spacing=8),
            bgcolor=p.sf,
            border=ft.Border.all(1, p.line),
            border_radius=16,
            padding=8,
        )

    def variant_body() -> ft.Control:
        if state["variant"] == "cards":
            return cards_content()
        if state["variant"] == "flow":
            return flow_content()
        return ledger_content()

    variant_holder = ft.Container(content=None)
    tabs_holder = ft.Container(content=None)

    def rerender() -> None:
        variant_holder.content = variant_body()
        tabs_holder.content = segmented_tabs(
            p, ["Ledger", "Cards", "Flow"], ["ledger", "cards", "flow"].index(state["variant"]), select_variant
        )
        page.update()

    def select_variant(index: int) -> None:
        state["variant"] = ["ledger", "cards", "flow"][index]
        rerender()

    def toggle_attention(e: ft.ControlEvent) -> None:
        state["attention_only"] = not state["attention_only"]
        rerender()

    def on_sort(e: ft.ControlEvent) -> None:
        state["sort"] = e.control.value
        rerender()

    variant_holder.content = variant_body()
    tabs_holder.content = segmented_tabs(p, ["Ledger", "Cards", "Flow"], 0, select_variant)

    to_assign = POOL
    to_assign_color = p.over_ink if to_assign < 0 else (p.ink2 if to_assign == 0 else p.ok_ink)
    to_assign_hint = (
        "You have assigned more than you have — take some back."
        if to_assign < 0
        else ("Every euro has a job. Nice." if to_assign == 0 else "Give this a job before the month starts.")
    )

    assign_bar = flat_card(
        p,
        ft.Row(
            [
                stat_block(p, "Left to assign", format_money(to_assign), value_size=42, value_color=to_assign_color, note=to_assign_hint),
                ft.Row(
                    [
                        secondary_button(p, "Fill all to target"),
                        ft.Container(
                            content=ft.Text("Reset", style=text_style(12.5, 500, p.ink3)),
                            height=34,
                            padding=ft.Padding.symmetric(horizontal=13),
                            alignment=ft.Alignment.CENTER,
                            ink=True,
                        ),
                    ],
                    spacing=8,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.END,
            wrap=True,
            spacing=20,
        ),
        radius=14,
        padding=ft.Padding.symmetric(horizontal=22, vertical=20),
    )

    toolbar_right: list[ft.Control] = []
    if band != "mobile":
        toolbar_right.append(secondary_button(p, "Needs attention only", toggle_attention))
        toolbar_right.append(
            select_field(
                p,
                [("default", "Sort: group order"), ("left", "Sort: least money left"), ("used", "Sort: most used"), ("name", "Sort: name")],
                value="default",
                height=32,
                on_select=on_sort,
            )
        )

    body: list[ft.Control] = [
        page_header(
            p,
            "Envelopes",
            eyebrow_segments=[MONTH, f"{DAYS_LEFT} days left"],
            actions=[
                secondary_button(p, "Move money", lambda e: page.show_dialog(move_dialog(page))),
                primary_button(p, "Add envelope", lambda e: page.show_dialog(new_envelope_dialog(page))),
            ],
        ),
        assign_bar,
    ]

    alerts = _alerts(p)
    if alerts:
        body.append(alert_banner(p, alerts))

    body.append(
        ft.Row(
            [tabs_holder, ft.Row(toolbar_right, spacing=9)],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            wrap=True,
            spacing=16,
        )
    )
    body.append(variant_holder)

    return app_shell(page, "/envelopes", "envelopes", body)
