"""Component gallery - every piece of the Envelo component library on one
screen, for visual review outside the app's routing.

Run with:  flet run src/gallery.py   (from the frontend/ directory)
        or: cd src && flet run gallery.py
"""

import dataclasses

import flet as ft

from components.alert_row import AlertItem, alert_banner, alert_history_row
from components.badge import badge, source_badge, state_pill
from components.bar_chart import ForecastGroupBar, HistoryBar, forecast_bar_chart, history_bar_chart
from components.button import danger_button, ghost_button, link_button, primary_button, secondary_button
from components.card import bordered_panel, flat_card
from components.envelope_card import envelope_card
from components.envelope_flow_row import envelope_flow_row
from components.envelope_row import envelope_ledger_row
from components.input_field import amount_input, text_input
from components.modal_dialog import ModalField, build_modal
from components.nav_rail import build_nav
from components.page_header import page_header
from components.progress_bar import progress_bar
from components.select_field import select_field
from components.stat_display import mini_stat, stat_block, stat_tile
from components.table_header import table_header
from components.tabs import segmented_tabs
from components.toast import toast
from components.toggle_switch import toggle_switch
from components.transaction_row import transaction_card, transaction_table_row
from currency import format_money
from dates import days_left_label
from mock_data import GROUPS, TRANSACTIONS, all_envelopes, envelope_name, envelope_view
from theme import apply_theme, palette, text_style


def _section(title: str, content: ft.Control) -> ft.Column:
    return ft.Column([ft.Text(title.upper(), style=text_style(13, 600, letter_spacing=1)), content], spacing=12)


def main(page: ft.Page) -> None:
    page.title = "Envelo - component gallery"
    apply_theme(page)
    p = palette(page)

    envelopes = all_envelopes()
    ev = envelope_view(p, envelopes[1])  # Groceries: a "warn" state example
    ev_over = envelope_view(p, next(e for e in envelopes if e.id == "gifts"))
    tx = dataclasses.replace(TRANSACTIONS[0], env_id=envelope_name(TRANSACTIONS[0].env_id))

    def open_demo_modal(e: ft.ControlEvent) -> None:
        dialog, _ = build_modal(
            p,
            title="Assign money",
            subtitle='Move money out of "left to assign" into an envelope.',
            fields=[
                ModalField("Envelope", "select", options=[(g.envelopes[0].id, g.envelopes[0].name) for g in GROUPS]),
                ModalField(
                    "Amount to assign",
                    "input",
                    placeholder="0,00",
                    hint=f"You have {format_money(137.4)} left to assign.",
                ),
            ],
            cta_label="Assign",
            preview=("Left to assign afterwards", format_money(137.4)),
            on_close=lambda e: page.pop_dialog(),
            on_confirm=lambda e: page.pop_dialog(),
        )
        page.show_dialog(dialog)

    tab_state = {"index": 0}
    tabs_holder = ft.Container()

    def render_tabs() -> None:
        tabs_holder.content = segmented_tabs(p, ["Ledger", "Cards", "Flow"], tab_state["index"], select_tab)

    def select_tab(i: int) -> None:
        tab_state["index"] = i
        render_tabs()
        page.update()

    render_tabs()

    page.add(
        ft.Column(
            [
                page_header(p, "Component gallery", eyebrow_segments=["Envelo", "Flet 0.86.2"]),
                _section(
                    "Buttons",
                    ft.Row(
                        [
                            primary_button(p, "Primary"),
                            secondary_button(p, "Secondary"),
                            ghost_button(p, "Ghost"),
                            danger_button(p, "Danger"),
                            link_button(p, "Link action"),
                        ],
                        spacing=10,
                    ),
                ),
                _section(
                    "Badges",
                    ft.Row(
                        [
                            source_badge(p, "rule"),
                            source_badge(p, "ml"),
                            source_badge(p, "manual"),
                            badge("On track", fill=p.ok_fill, ink=p.ok_ink),
                            badge("85%", fill=p.warn_fill, ink=p.warn_ink),
                            badge("Over", fill=p.over_fill, ink=p.over_ink),
                            state_pill(p, "ok", "On track"),
                            state_pill(p, "warn", "85%"),
                            state_pill(p, "over", "Over"),
                        ],
                        spacing=8,
                        wrap=True,
                    ),
                ),
                _section(
                    "Progress bars",
                    ft.Column(
                        [
                            progress_bar(p, 0.44, color=p.ok),
                            progress_bar(p, 0.85, color=p.warn),
                            progress_bar(p, 1.0, color=p.over),
                            progress_bar(p, 0.6, color=p.ok, height=16, target_fraction=0.8),
                        ],
                        spacing=10,
                    ),
                ),
                _section(
                    "Inputs & selects",
                    ft.Row(
                        [
                            text_input(p, placeholder="Payee"),
                            amount_input(p, value="420,00"),
                            select_field(p, [("groceries", "Groceries"), ("transport", "Transport")]),
                        ],
                        spacing=12,
                    ),
                ),
                _section("Tabs", tabs_holder),
                _section(
                    "Page header, stat blocks",
                    ft.Row(
                        [
                            stat_block(
                                p,
                                "Safe to spend",
                                format_money(1842.10),
                                value_size=40,
                                value_color=p.ok_ink,
                                note="Everyday envelopes only.",
                            ),
                            mini_stat(p, "Assigned", format_money(520)),
                            stat_tile(p, "14", "matched a rule", fill=p.ok_fill, border=p.ok_border, ink=p.ok_ink),
                        ],
                        spacing=24,
                        wrap=True,
                    ),
                ),
                _section(
                    "Alerts",
                    ft.Column(
                        [
                            alert_banner(
                                p,
                                [
                                    AlertItem(
                                        message=f"Gifts is {format_money(22.5)} over its plan", cta="Cover it", dot_color=p.over
                                    ),
                                    AlertItem(
                                        message=f"Groceries is at 85% — {days_left_label()}", cta="Move money", dot_color=p.warn
                                    ),
                                ],
                            ),
                            bordered_panel(
                                p,
                                [
                                    alert_history_row(
                                        p,
                                        AlertItem(
                                            message="",
                                            title=f"Gifts went {format_money(22.5)} over its plan",
                                            meta="Yesterday, 17:42 · Gifts",
                                            cta="Open",
                                            dot_color=p.over,
                                        ),
                                    )
                                ],
                            ),
                        ],
                        spacing=12,
                    ),
                ),
                _section(
                    "Envelope row / card / flow row",
                    ft.Column(
                        [
                            bordered_panel(
                                p,
                                [
                                    table_header(
                                        p, [("ENVELOPE", 2, ft.TextAlign.LEFT), ("LEFT", 1, ft.TextAlign.RIGHT)]
                                    ),
                                    envelope_ledger_row(p, ev, "desktop"),
                                ],
                            ),
                            ft.Row([ft.Container(content=envelope_card(p, ev_over), width=280)], wrap=True),
                            envelope_flow_row(p, ev),
                        ],
                        spacing=14,
                    ),
                ),
                _section(
                    "Transactions",
                    ft.Column(
                        [
                            bordered_panel(
                                p,
                                [
                                    table_header(
                                        p,
                                        [
                                            ("DATE", 1, ft.TextAlign.LEFT),
                                            ("PAYEE", 2, ft.TextAlign.LEFT),
                                            ("ENVELOPE", 2, ft.TextAlign.LEFT),
                                            ("SOURCE", 1, ft.TextAlign.LEFT),
                                            ("AMOUNT", 1, ft.TextAlign.RIGHT),
                                        ],
                                    ),
                                    transaction_table_row(p, tx),
                                ],
                            ),
                            ft.Container(content=transaction_card(p, tx), width=340),
                        ],
                        spacing=14,
                    ),
                ),
                _section(
                    "Bar charts",
                    ft.Row(
                        [
                            flat_card(
                                p,
                                history_bar_chart(
                                    p, [HistoryBar("Feb", "480", 60, p.ok_fill), HistoryBar("Jul", "520", 65, p.ok)]
                                ),
                                padding=16,
                            ),
                            flat_card(
                                p,
                                forecast_bar_chart(p, [ForecastGroupBar("Living", "1.900", 70, 82, p.warn)]),
                                padding=16,
                            ),
                        ],
                        spacing=16,
                        wrap=True,
                    ),
                ),
                _section(
                    "Toggle switch & toast",
                    ft.Row(
                        [toggle_switch(p, True), toast(p, "18 transactions imported")],
                        spacing=20,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ),
                _section("Modal dialog", secondary_button(p, "Open modal preview", open_demo_modal)),
                _section(
                    "Nav rail (desktop / tablet / mobile)",
                    ft.Row(
                        [
                            build_nav(p, "desktop", "dashboard", lambda r: None, attention_count=2),
                            build_nav(p, "tablet", "envelopes", lambda r: None),
                            build_nav(p, "mobile", "transactions", lambda r: None),
                        ],
                        spacing=16,
                    ),
                ),
            ],
            spacing=32,
            scroll=ft.ScrollMode.AUTO,
        )
    )


if __name__ == "__main__":
    ft.run(main)
