"""Accounts - `isAccounts` in the design: every account and its balance, as
cards.

Balances come from `GET /budget/accounts/balances`, summed by the database.
Summing a fetched transaction list instead would be wrong past 100 rows, which
every real account passes in a few months - the same trap `spent-by-envelope`
exists to avoid on the envelope side.

**Amounts here carry the account's own currency code**, not the app-wide display
format. `currency.py` is a presentation preference for one person's whole
budget; `accounts.currency` is what a particular account is actually denominated
in. Rendering a EUR account as "1 234,56 zł" because that is how you like to read
money would be a different number, not a different formatting.
"""

import asyncio
from datetime import datetime

import flet as ft

from api_client import collect_failures, get_account_balances, get_accounts
from components.button import link_button, primary_button
from components.card import flat_card
from components.notice import notice_banner
from components.page_header import page_header
from currency import format_amount_bare
from theme import palette, text_style
from views.common import app_shell
from views.dialogs import ACCOUNT_TYPES, new_account_dialog

_TYPE_LABELS = dict(ACCOUNT_TYPES)


def _amount(value: float, currency: str) -> str:
    """`2 418,62 PLN` - the reader's separators, the account's currency."""
    return f"{format_amount_bare(value)} {currency}"


def _last_import_label(raw: str | None) -> str:
    if not raw:
        return "no imports yet"
    try:
        imported = datetime.fromisoformat(raw)
    except ValueError:
        return "no imports yet"
    return f"last import {imported.day} {imported.strftime('%B')}"


def _meta(currency: str, stats: dict) -> str:
    """`PLN · 142 transactions · last import 24 July`.

    The mock's version of this line was a fixed string per account. Every part of
    it is now something the server counted, including "no imports yet", which is
    the honest state of an account whose rows were all entered by hand.
    """
    count = stats.get("transaction_count", 0)
    rows = "1 transaction" if count == 1 else f"{count} transactions"
    return f"{currency} · {rows} · {_last_import_label(stats.get('last_imported_at'))}"


async def build_accounts_view(page: ft.Page) -> ft.View:
    p = palette(page)

    accounts: list[dict] = []
    balances: dict[str, dict] = {}
    failures: list[str] = []

    async def load() -> None:
        nonlocal accounts, balances, failures
        with collect_failures() as reported:
            accounts, balances = await asyncio.gather(get_accounts(), get_account_balances())
        failures = list(reported)

    cards_holder = ft.ResponsiveRow(spacing=14, run_spacing=14)

    async def refresh() -> None:
        await load()
        cards_holder.controls = _cards()
        page.update()

    def _edit(account: dict):
        def handler(e: ft.ControlEvent) -> None:
            page.show_dialog(new_account_dialog(page, account=account, on_saved=refresh))

        return handler

    def _balance_of(account: dict) -> float:
        return float(balances.get(account["id"], {}).get("balance", 0) or 0)

    def _cards() -> list[ft.Control]:
        if not accounts:
            return [
                ft.Container(
                    content=flat_card(
                        p,
                        ft.Text(
                            "No accounts yet. Add the one your statements come from and the rest follows.",
                            style=text_style(13, 400, p.ink3),
                        ),
                        radius=14,
                        padding=18,
                    ),
                    col={"xs": 12},
                )
            ]

        cards: list[ft.Control] = []
        for account in accounts:
            balance = _balance_of(account)
            stats = balances.get(account["id"], {})
            cards.append(
                ft.Container(
                    content=flat_card(
                        p,
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text(account["name"], style=text_style(14.5, 600, p.ink)),
                                        ft.Container(
                                            content=ft.Text(
                                                _TYPE_LABELS.get(account["type"], account["type"]).upper(),
                                                style=text_style(10.5, 500, p.ink2, letter_spacing=0.4),
                                            ),
                                            bgcolor=p.sf3,
                                            border_radius=6,
                                            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                ft.Text(
                                    _amount(balance, account["currency"]),
                                    style=text_style(
                                        26, 600, p.over_ink if balance < 0 else p.ink, letter_spacing=-0.6
                                    ),
                                ),
                                ft.Container(
                                    content=ft.Row(
                                        [
                                            ft.Text(
                                                _meta(account["currency"], stats),
                                                style=text_style(11.5, 400, p.ink3),
                                                expand=True,
                                            ),
                                            link_button(p, "Edit", _edit(account)),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    padding=ft.Padding.only(top=11),
                                    border=ft.Border(top=ft.BorderSide(1, p.sf3)),
                                ),
                            ],
                            spacing=14,
                        ),
                        radius=14,
                        padding=18,
                    ),
                    col={"xs": 12, "sm": 6, "lg": 4},
                )
            )
        return cards

    def _eyebrow() -> str:
        """Totals across accounts only mean something in one currency.

        The mock added four PLN balances and called it a total. With real
        accounts the currency is per account, so adding a EUR balance to a PLN
        one would produce a number that is not money in anything - better to say
        how many currencies are in play and let the cards speak.
        """
        count = f"{len(accounts)} account" if len(accounts) == 1 else f"{len(accounts)} accounts"
        currencies = {a["currency"] for a in accounts}
        if len(currencies) == 1:
            total = sum(_balance_of(a) for a in accounts)
            return f"{_amount(total, currencies.pop())} across {count}"
        return f"{count} in {len(currencies)} currencies"

    await load()
    cards_holder.controls = _cards()

    body: list[ft.Control] = [
        page_header(
            p,
            "Accounts",
            eyebrow_segments=[_eyebrow()] if accounts else None,
            actions=[
                primary_button(p, "Add account", lambda e: page.show_dialog(new_account_dialog(page, on_saved=refresh)))
            ],
        ),
    ]

    if failures:
        body.append(
            notice_banner(
                p,
                "Couldn't reach the server, so these balances may be wrong or missing "
                f"({', '.join(sorted(set(failures)))}).",
            )
        )

    body.append(cards_holder)

    return await app_shell(page, "/accounts", "accounts", body)
