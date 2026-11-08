"""First run - `isFirstRun` in the design: the setup checklist shown before a
new budget has any accounts, statements or assigned money.

Pre-setup, so this sits outside the app shell: no nav rail, and not listed as
a destination in it.

Each step's `done` is a question the API can already answer, so nothing here is
declared. The mock had them fixed at (done, not done, not done), which meant the
screen told someone with a fully imported budget that they had not started, and
told someone with an empty one that their first step was already behind them -
wrong in both directions, and wrong in the place where being wrong costs most,
since the obvious response is to set everything up a second time.

It deliberately does *not* go through `fetch_budget_snapshot()`, the shared read
for envelope-shaped screens: that fetches five things for the nav rail's benefit,
and this screen has no nav rail and needs one of them.
"""

import asyncio
from dataclasses import dataclass

import flet as ft

from api_client import collect_failures, get_accounts, get_envelope_allocations, get_statements
from components.button import primary_button, secondary_button
from components.card import flat_card
from components.notice import notice_banner
from components.page_header import page_header
from theme import palette, text_style
from utils import range_to_dates
from views.common import SETUP_IN_PROGRESS_KEY, standalone_shell


@dataclass(frozen=True)
class SetupStep:
    title: str
    body: str
    cta: str
    route: str
    done: bool


def _steps(accounts: list[dict], statements: list[dict], allocations: list[dict], month: str) -> list[SetupStep]:
    """The checklist, answered against real data.

    Step three asks for an allocation *in this month* carrying a non-zero
    amount: an envelope with a 0,00 row has been created, not funded, and the
    step says "give your money jobs".
    """
    assigned_this_month = any(
        a["month"] == month and float(a["assigned_amount"]) > 0 for a in allocations
    )
    return [
        SetupStep(
            title="Add your first account",
            body="Checking, savings, credit card or cash — it just needs a name and a currency.",
            cta="Add account",
            route="/accounts",
            done=bool(accounts),
        ),
        SetupStep(
            title="Import a bank statement",
            body="CSV, MT940 or OFX. Envelo files what it recognises and leaves the rest to you.",
            cta="Import",
            route="/import",
            done=bool(statements),
        ),
        SetupStep(
            title="Give your money jobs",
            body="Create envelopes and assign this month's money to them.",
            cta="Envelopes",
            route="/envelopes",
            done=assigned_this_month,
        ),
    ]


def _eyebrow(steps: list[SetupStep]) -> str:
    """"Step 2 of 3" - the step actually being asked for, not a hardcoded 1.

    Counted from the first unfinished step rather than from how many are done,
    so a checklist completed out of order (importing before naming an account
    is perfectly possible) still points at what is left.
    """
    for i, step in enumerate(steps):
        if not step.done:
            return f"Step {i + 1} of {len(steps)}"
    return "All set"


def _badge(p, index: int, done: bool) -> ft.Control:
    content = (
        ft.Icon(ft.Icons.CHECK_ROUNDED, size=15, color=p.ok_ink)
        if done
        else ft.Text(str(index + 1), style=text_style(12.5, 500, p.ink2))
    )
    return ft.Container(
        content=content,
        width=27,
        height=27,
        bgcolor=p.ok_fill if done else p.sf3,
        border_radius=999,
        alignment=ft.Alignment.CENTER,
    )


async def build_first_run_view(page: ft.Page) -> ft.View:
    p = palette(page)
    month = range_to_dates("this")[0].isoformat()

    with collect_failures() as failures:
        accounts, statements, allocations = await asyncio.gather(
            get_accounts(), get_statements(), get_envelope_allocations()
        )

    steps = _steps(accounts, statements, allocations, month)
    # The one step being asked for. Everything else is secondary, including the
    # finished ones - the mock gave *those* the primary button, so the screen
    # shouted loudest about what you had already done.
    next_step = next((i for i, step in enumerate(steps) if not step.done), None)
    # Decided here, from the API's answer, every time this screen is shown - so
    # the "Back to setup" bar disappears by itself once the last step is done.
    # Left alone when the server could not be reached: an outage makes every
    # step look undone, and that must not resurrect a finished checklist.
    if not failures:
        page.session.store.set(SETUP_IN_PROGRESS_KEY, next_step is not None)

    rows: list[ft.Control] = []
    for i, step in enumerate(steps):
        button = (primary_button if i == next_step else secondary_button)(
            p, step.cta, lambda e, route=step.route: page.navigate(route)
        )
        rows.append(
            flat_card(
                p,
                ft.Row(
                    [
                        _badge(p, i, step.done),
                        ft.Column(
                            [
                                ft.Text(step.title, style=text_style(14.5, 600, p.ink)),
                                ft.Text(step.body, style=text_style(13, 400, p.ink3)),
                            ],
                            spacing=3,
                            tight=True,
                            expand=True,
                        ),
                        button,
                    ],
                    spacing=15,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                radius=13,
                border_color=p.ok_border if step.done else p.line,
                padding=ft.Padding.symmetric(horizontal=20, vertical=19),
            )
        )

    if next_step is None:
        # A checklist with everything ticked and no way out is a dead end; the
        # mock could never reach this state, so it never needed one.
        rows.append(
            flat_card(
                p,
                ft.Row(
                    [
                        ft.Text(
                            "Everything is set up. Your budget is ready.",
                            style=text_style(13.5, 500, p.ink),
                            expand=True,
                        ),
                        primary_button(p, "Open your budget", lambda e: page.navigate("/dashboard")),
                    ],
                    spacing=15,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                radius=13,
                border_color=p.ok_border,
                padding=ft.Padding.symmetric(horizontal=20, vertical=19),
            )
        )

    body: list[ft.Control] = [page_header(p, "Set up Envelo", eyebrow_segments=[_eyebrow(steps)])]

    # Ahead of the list, because an unreachable server makes every step look
    # undone - and on this screen that reads as "start over", which is the most
    # expensive wrong conclusion the app can invite.
    if failures:
        body.append(
            notice_banner(
                p,
                "Couldn't reach the server, so this checklist may not reflect what you have already done "
                f"({', '.join(sorted(set(failures)))}).",
            )
        )

    body.append(ft.Column(rows, spacing=11, width=620))

    return standalone_shell(page, "/first-run", body)
