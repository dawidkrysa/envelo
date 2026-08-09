"""Rules - `isRules` in the design: the payee-matching rules applied on import.

The mock version described a feature the backend did not have. Every row said
"Payee contains" while `match_envelope_for_transaction` compared the phrase to
the transaction *description*; the header promised rules "applied on import, top
to bottom" when there is no ordering at all - the longest matching phrase wins;
and the dialog offered payee/description/amount conditions against a model with a
single `phrase` column, so two of the three could never be saved.

The matcher now does what the screen always claimed (match on the payee), so the
copy here is finally true - including the part that is not obvious: a rule you
wrote beats where that payee's transactions have gone before. See
`app/db/repositories/categorization_rule.py`.

The "46 matches" column is gone. Nothing records which rule filed which
transaction, so any number here would have been either invented or a different
question wearing the same label.
"""

import asyncio

import flet as ft

from api_client import collect_failures, delete_categorization_rule, get_categorization_rules, get_envelopes
from components.button import link_button, primary_button
from components.card import flat_card
from components.notice import notice_banner
from components.page_header import page_header
from theme import palette, text_style
from views.common import app_shell
from views.dialogs import confirm_delete_dialog, new_rule_dialog


def _chip(p, text: str, *, fill: str, ink: str) -> ft.Control:
    return ft.Container(
        content=ft.Text(text, style=text_style(13, 500, ink)),
        bgcolor=fill,
        border_radius=7,
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
    )


async def build_rules_view(page: ft.Page) -> ft.View:
    p = palette(page)

    rules: list[dict] = []
    envelopes: list[dict] = []
    failures: list[str] = []

    async def load() -> None:
        nonlocal rules, envelopes, failures
        with collect_failures() as reported:
            rules, envelopes = await asyncio.gather(get_categorization_rules(), get_envelopes())
        failures = list(reported)

    rows_holder = ft.Column(spacing=9)

    async def refresh() -> None:
        await load()
        rows_holder.controls = _rows()
        page.update()

    def _delete(rule: dict):
        async def confirm() -> str | None:
            if await delete_categorization_rule(rule["id"]) is None:
                return "Couldn't delete — try again."
            await refresh()
            return None

        def handler(e: ft.ControlEvent) -> None:
            page.show_dialog(
                confirm_delete_dialog(
                    page,
                    title="Delete rule?",
                    message=(
                        f'Delete the rule for "{rule["phrase"]}"? Transactions it already filed keep their '
                        "envelope; only future imports change. This can't be undone."
                    ),
                    on_confirm=confirm,
                )
            )

        return handler

    def _edit(rule: dict):
        def handler(e: ft.ControlEvent) -> None:
            page.show_dialog(new_rule_dialog(page, envelopes=envelopes, rule=rule, on_saved=refresh))

        return handler

    def _rows() -> list[ft.Control]:
        envelope_names = {e["id"]: e["name"] for e in envelopes}
        if not rules:
            return [
                flat_card(
                    p,
                    ft.Text(
                        "No rules yet. Add one and Envelo will file that payee for you on the next import.",
                        style=text_style(13, 400, p.ink3),
                    ),
                    radius=12,
                    padding=ft.Padding.symmetric(horizontal=17, vertical=18),
                )
            ]

        # Sorted by phrase length, longest first - the order the matcher resolves
        # ties in. The mock numbered the rows 1..n beside "applied top to bottom",
        # which implied a precedence the server does not have; showing them in the
        # order that actually decides ties is the honest version of that idea.
        ordered = sorted(rules, key=lambda r: (-len(r["phrase"]), r["phrase"].lower()))

        rows: list[ft.Control] = []
        for rule in ordered:
            rows.append(
                flat_card(
                    p,
                    ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Text("Payee contains", style=text_style(13, 400, p.ink3)),
                                    _chip(p, rule["phrase"], fill=p.sf3, ink=p.ink),
                                    ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=15, color=p.ink3),
                                    _chip(
                                        p,
                                        envelope_names.get(rule["envelope_id"], "Deleted envelope"),
                                        fill=p.ok_fill,
                                        ink=p.ok_ink,
                                    ),
                                ],
                                spacing=9,
                                wrap=True,
                                expand=True,
                            ),
                            ft.Row(
                                [
                                    link_button(p, "Edit", _edit(rule)),
                                    link_button(p, "Delete", _delete(rule), color=p.over_ink),
                                ],
                                spacing=14,
                            ),
                        ],
                        # No wrap=True here: the "chips" Row is a flex (expand)
                        # child, and a Wrap cannot contain a flex child.
                        spacing=14,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    radius=12,
                    padding=ft.Padding.symmetric(horizontal=17, vertical=15),
                )
            )
        return rows

    await load()
    rows_holder.controls = _rows()

    body: list[ft.Control] = [
        page_header(
            p,
            "Rules",
            # Was "Applied on import, top to bottom". There is no top and no
            # bottom: when several rules match the same payee, the longest phrase
            # wins, and a rule beats what that payee did before.
            eyebrow_segments=["Applied on import", "Longest match wins"],
            actions=[
                primary_button(
                    p,
                    "Add rule",
                    lambda e: page.show_dialog(new_rule_dialog(page, envelopes=envelopes, on_saved=refresh)),
                )
            ],
        ),
    ]

    if failures:
        body.append(
            notice_banner(
                p,
                "Couldn't reach the server, so this list may be incomplete "
                f"({', '.join(sorted(set(failures)))}).",
            )
        )

    body.append(rows_holder)

    return await app_shell(page, "/rules", "rules", body)
