"""Payees - `isPayees` in the design: everyone money has gone to, with
History/Rename/Merge actions.

Every figure on the row - how many transactions, their total, the last one, the
envelope this payee usually lands in - comes from `GET /budget/payees/stats`.
None of it is on `PayeeRead`, and none of it could be worked out here: a payee
with more history than one page of `GET /budget/transactions` would have been
counted and summed short, silently, and worse the longer the budget ran.

Merge exists because imports create a payee per spelling, so one shop arrives as
"BIEDRONKA 1234" and "Biedronka" and the history that decides categorization is
split between them. It was an inert link in the mock; the endpoint behind it is
new.
"""

import asyncio
from datetime import date

import flet as ft

from api_client import collect_failures, get_envelopes, get_payee_stats, get_payees
from components.button import link_button
from components.card import bordered_panel
from components.notice import notice_banner
from components.page_header import page_header
from currency import format_money
from theme import palette, text_style
from views.common import PREFILL_SEARCH_KEY, app_shell
from views.dialogs import merge_payee_dialog, rename_payee_dialog


def _meta(stats: dict) -> str:
    count = stats.get("transaction_count", 0)
    if not count:
        return "no transactions yet"
    rows = "1 transaction" if count == 1 else f"{count} transactions"
    last = stats.get("last_transaction_date")
    if not last:
        return rows
    try:
        when = date.fromisoformat(last)
    except ValueError:
        return rows
    return f"{rows} · last on {when.day} {when.strftime('%B %Y')}"


async def build_payees_view(page: ft.Page) -> ft.View:
    p = palette(page)

    payees: list[dict] = []
    stats: dict[str, dict] = {}
    envelopes: list[dict] = []
    failures: list[str] = []

    async def load() -> None:
        nonlocal payees, stats, envelopes, failures
        with collect_failures() as reported:
            payees, stats, envelopes = await asyncio.gather(get_payees(), get_payee_stats(), get_envelopes())
        failures = list(reported)

    rows_holder = ft.Column(spacing=0)

    async def refresh() -> None:
        await load()
        rows_holder.controls = [bordered_panel(p, _rows())]
        page.update()

    def _history(payee: dict):
        def handler(e: ft.ControlEvent) -> None:
            page.session.store.set(PREFILL_SEARCH_KEY, payee["name"])
            page.navigate("/transactions")

        return handler

    def _rename(payee: dict):
        def handler(e: ft.ControlEvent) -> None:
            page.show_dialog(rename_payee_dialog(page, payee=payee, on_saved=refresh))

        return handler

    def _merge(payee: dict):
        def handler(e: ft.ControlEvent) -> None:
            page.show_dialog(merge_payee_dialog(page, payee=payee, payees=payees, on_saved=refresh))

        return handler

    def _rows() -> list[ft.Control]:
        if not payees:
            return [
                ft.Container(
                    content=ft.Text(
                        "No payees yet. They appear as you import statements or add transactions by hand.",
                        style=text_style(13, 400, p.ink3),
                    ),
                    padding=ft.Padding.symmetric(horizontal=18, vertical=18),
                )
            ]

        envelope_names = {e["id"]: e["name"] for e in envelopes}
        # Busiest first: the payees worth renaming or merging are the ones that
        # keep arriving. The mock's order was whatever the literal list happened
        # to be in.
        ordered = sorted(
            payees,
            key=lambda pe: (-stats.get(pe["id"], {}).get("transaction_count", 0), pe["name"].lower()),
        )

        rows: list[ft.Control] = []
        for payee in ordered:
            payee_stats = stats.get(payee["id"], {})
            envelope_id = payee_stats.get("top_envelope_id")
            # "Uncategorized" is a real state, not a missing value: it means every
            # transaction from this payee is still waiting to be filed.
            envelope_label = envelope_names.get(envelope_id, "Uncategorized") if envelope_id else "Uncategorized"
            total = float(payee_stats.get("total", 0) or 0)
            rows.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(payee["name"], style=text_style(13.5, 500, p.ink)),
                                    ft.Text(_meta(payee_stats), style=text_style(11.5, 400, p.ink3)),
                                ],
                                spacing=3,
                                tight=True,
                                expand=True,
                            ),
                            ft.Container(
                                content=ft.Text(envelope_label, style=text_style(12, 400, p.ink2)),
                                bgcolor=p.sf3,
                                border_radius=6,
                                padding=ft.Padding.symmetric(horizontal=9, vertical=3),
                            ),
                            # Shown with its own sign rather than negated into
                            # looking like spending: an employer or a refund is
                            # money in, and the mock's `-total` turned every one
                            # of those into an expense.
                            ft.Text(
                                format_money(total),
                                style=text_style(13.5, 500, p.ok_ink if total > 0 else p.ink),
                                width=98,
                                text_align=ft.TextAlign.RIGHT,
                            ),
                            ft.Row(
                                [
                                    link_button(p, "History", _history(payee)),
                                    link_button(p, "Rename", _rename(payee), color=p.ink3),
                                    link_button(p, "Merge", _merge(payee), color=p.ink3),
                                ],
                                spacing=14,
                            ),
                        ],
                        # No wrap=True here: the name/meta Column is a flex
                        # (expand) child, and a Wrap cannot contain a flex child.
                        spacing=14,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding.symmetric(horizontal=18, vertical=14),
                    border=ft.Border(bottom=ft.BorderSide(1, p.sf3)),
                )
            )
        return rows

    await load()
    rows_holder.controls = [bordered_panel(p, _rows())]

    count = f"{len(payees)} payee" if len(payees) == 1 else f"{len(payees)} payees"
    body: list[ft.Control] = [page_header(p, "Payees", eyebrow_segments=[count])]

    if failures:
        body.append(
            notice_banner(
                p,
                "Couldn't reach the server, so these totals may be wrong or missing "
                f"({', '.join(sorted(set(failures)))}).",
            )
        )

    body.append(rows_holder)

    return await app_shell(page, "/payees", "payees", body)
