"""Shared page shell - nav rail/bottom bar + scrollable content column reused
by every screen. The design's own device-frame preview chrome (the bordered,
drop-shadowed rectangle simulating a phone/tablet in the design tool) is not
reproduced here: a real app fills its actual window instead of a mockup frame.
"""

import asyncio
from dataclasses import dataclass
from datetime import date

import flet as ft

import auth
from api_client import (
    get_category_groups,
    get_envelope_allocations,
    get_envelopes,
    get_spent_by_envelope,
)
from components.button import secondary_button
from components.nav_rail import CategoryGroupNav, build_nav
from currency import format_money
from mock_data import Envelope, envelope_state
from theme import Palette, content_padding, layout_band, palette, text_style
from utils import range_to_dates, resolve_target, to_envelope

PREFILL_SEARCH_KEY = "prefill_transaction_search"
"""Session key one screen uses to hand a search term to Transactions - the
Payees screen's "History" action.

Declared here rather than in either view so neither has to import the other, the
same role `routing.py`'s tables play for routes. It carries a *search*, not an
exact filter: `GET /budget/transactions` has no payee parameter, so the term
lands in the visible search box where it can be seen and edited, instead of
filtering the list by something invisible.
"""

CATEGORY_GROUPS_COLLAPSED_KEY = "envelo.category_groups_collapsed"
"""Session-store key for whether the sidebar's "Category groups" quick-jump list
is collapsed - session-scoped like `selected_envelope_id`, not a persisted
preference in `preferences.py`. A budget with a dozen groups pushed the user
footer (and Settings, below it) off the bottom of the sidebar with no scrollbar
to hint anything was cut off; collapsing the list is a per-visit fix for that,
not a choice worth surviving a restart."""

SETUP_IN_PROGRESS_KEY = "envelo.setup_in_progress"
"""Session-store flag: this person started the first-run checklist and has not
finished it.

Each checklist step opens the real screen that does the job (Accounts, Import,
Envelopes) rather than a copy of it - but those screens are part of the app
proper and had no way back, so whoever finished step one was left with steps
two and three unreachable. While this is set, `app_shell` shows a "Back to
setup" bar on every main screen. First-run sets it and clears it itself, from
what the API says is done - nothing else needs to remember to.
"""


def page_band(page: ft.Page) -> str:
    return layout_band(getattr(page, "width", None))


@dataclass(frozen=True)
class BudgetSnapshot:
    """The envelope picture as of one month, fetched once and shared with the
    nav rail.

    The nav is chrome built independently of the screen inside it, so it used to
    fetch all of this itself - on the Dashboard that meant the same envelopes,
    allocations and spending were pulled twice per render, ten HTTP calls where
    seven would do. A screen that has already fetched a snapshot now hands it to
    `app_shell`; anything that hasn't still gets one built for it.

    **Money rolls over.** An envelope holds whatever was left in it when the
    month began (`carried_over_by_envelope`) plus whatever was assigned since
    (`assigned_by_envelope`), minus this month's spending. Assign 500 in July,
    spend 300, and August opens with 200 still in the envelope rather than
    starting from nothing.

    That is not a display choice - it is what makes the arithmetic close. The
    budget's identity is `cash = to_assign + sum(available)`, and `to_assign`
    (`GET /budget/envelope-allocations/to-assign`) is cumulative across all
    months. Pairing it with per-month availables left every past month's
    unspent assignment unaccounted for anywhere: not in the envelope, which had
    reset, and not in to-assign, which had already subtracted it. "Safe to
    spend" drifted further below the truth with every month that passed.

    The three parts are kept separate rather than pre-rolled into one pair
    because the Ledger's "Assigned" field is editable and writes *this month's*
    allocation row - a field that showed a running total but saved a monthly one
    would be a bug waiting to happen. Only `available` is cumulative.

    `spent` (cumulative) exists to derive the carry-over and is otherwise not
    what screens should read; `spent_this_month` is the month's activity.
    """

    month: date
    category_groups: list[dict]
    envelopes: list[dict]
    allocations: list[dict]
    spent: dict[str, float]
    spent_this_month: dict[str, float]
    assigned_by_envelope: dict[str, float]
    carried_over_by_envelope: dict[str, float]

    def envelope_models(self, category_group_id: str | None = None) -> list[Envelope]:
        """The display dataclasses, optionally narrowed to one category group.

        Targets are resolved the same way `views/envelopes.py` resolves them -
        a monthly override at or before this month, else the envelope's own flat
        `target_amount` - rather than being left at zero, which is what made
        every envelope on the Dashboard read "no target".

        Group names are filled in from the snapshot's own category groups.
        `EnvelopeView.group_name` has existed all along but arrived empty from
        here, so a screen that wanted to say which group an envelope belongs to
        (Alerts) had to redo the join itself.
        """
        as_of = self.month.isoformat()
        group_names = {cg["id"]: cg["name"] for cg in self.category_groups}
        return [
            to_envelope(
                e,
                self.assigned_by_envelope.get(e["id"], 0.0),
                self.spent_this_month.get(e["id"], 0.0),
                resolve_target(self.allocations, e["id"], as_of, float(e["target_amount"] or 0)),
                self.carried_over_by_envelope.get(e["id"], 0.0),
                group_names.get(e["category_group_id"], ""),
            )
            for e in self.envelopes
            if category_group_id is None or e["category_group_id"] == category_group_id
        ]


async def fetch_budget_snapshot() -> BudgetSnapshot:
    """The envelopes, assignments and spending behind the current month.

    Concurrently: the nav is rebuilt on every screen and after every write, so
    serial round trips here were a tax on all of them.

    Both spending figures come from the server's aggregate rather than from
    summing a fetched list - `GET /budget/transactions` is paged, so a
    client-side sum understates every total once a month holds more rows than
    one page. The cumulative one simply leaves `dateFrom` off.
    """
    date_from, date_to = range_to_dates("this")
    category_groups, envelopes, allocations, spent, spent_this_month = await asyncio.gather(
        get_category_groups(),
        get_envelopes(),
        get_envelope_allocations(),
        get_spent_by_envelope(date_to=date_to),
        get_spent_by_envelope(date_from=date_from, date_to=date_to),
    )
    month = date_from.isoformat()
    assigned: dict[str, float] = {}
    assigned_before: dict[str, float] = {}
    for a in allocations:
        bucket = assigned if a["month"] == month else (assigned_before if a["month"] < month else None)
        if bucket is not None:
            bucket[a["envelope_id"]] = bucket.get(a["envelope_id"], 0.0) + float(a["assigned_amount"])

    # What was left in each envelope when the month began: everything assigned
    # before it, minus everything spent before it. The second term is the
    # cumulative total less this month's, so no third round trip is needed.
    #
    # Allocations dated *after* this month are ignored on both sides - assigning
    # next month's money should not make this month look richer.
    carried_over = {
        envelope_id: assigned_before.get(envelope_id, 0.0)
        - (spent.get(envelope_id, 0.0) - spent_this_month.get(envelope_id, 0.0))
        for envelope_id in set(assigned_before) | set(spent)
    }

    return BudgetSnapshot(
        month=date_from,
        category_groups=category_groups,
        envelopes=envelopes,
        allocations=allocations,
        spent=spent,
        spent_this_month=spent_this_month,
        assigned_by_envelope=assigned,
        carried_over_by_envelope=carried_over,
    )


def category_group_nav(p: Palette, page: ft.Page, snapshot: BudgetSnapshot) -> tuple[list[CategoryGroupNav], int]:
    """Real "left" per category group for the sidebar's quick-jump list, plus how
    many envelopes need attention - mirrors the assigned/spent math
    `views/envelopes.py` does for its own Ledger/Cards/Flow tabs.

    The attention count comes back from here rather than being computed by the
    caller because this is where the real envelopes already are: it used to be
    `len(attention_envelopes())` over the static mock, so the sidebar badge
    showed the same 3 forever, next to group totals that were real.
    """
    items = []
    attention = 0
    for cg in snapshot.category_groups:
        group_envs = snapshot.envelope_models(cg["id"])
        left = sum(e.assigned - e.spent for e in group_envs)
        off_track = [e for e in group_envs if envelope_state(e) != "ok"]
        attention += len(off_track)
        items.append(
            CategoryGroupNav(
                name=cg["name"],
                left_str=f"{format_money(left)} left",
                bar_color=p.warn if off_track else p.ok_border,
                on_click=lambda e, gid=cg["id"]: page.navigate("/envelopes"),
            )
        )
    return items, attention


def _content_column(page: ft.Page, band: str, body: list[ft.Control]) -> ft.Column:
    content = ft.Container(
        content=ft.Column(body, spacing=20),
        padding=content_padding(band),
    )
    return ft.Column([content], scroll=ft.ScrollMode.AUTO, expand=True, spacing=0)


async def app_shell(
    page: ft.Page,
    route: str,
    active_nav_id: str,
    body: list[ft.Control],
    snapshot: BudgetSnapshot | None = None,
) -> ft.View:
    """Every main screen: nav + a scrollable content column with the correct
    per-breakpoint padding (`padStyle` in the design).

    `snapshot` is an optimisation only: a screen that has already fetched the
    month's envelopes passes them in so the nav doesn't fetch them a second
    time. Screens that don't have one leave it out and the shell fetches its
    own, so no caller is obliged to care.
    """
    p = palette(page)
    band = page_band(page)

    def navigate(target: str) -> None:
        page.navigate(target)

    def toggle_category_groups(e: ft.ControlEvent) -> None:
        page.session.store.set(
            CATEGORY_GROUPS_COLLAPSED_KEY,
            not page.session.store.get(CATEGORY_GROUPS_COLLAPSED_KEY),
        )
        page.run_task(refresh_nav)

    async def build_nav_control(data: BudgetSnapshot | None) -> ft.Control:
        category_groups, attention_count = category_group_nav(p, page, data or await fetch_budget_snapshot())
        return build_nav(
            p,
            band,
            active_nav_id,
            navigate,
            attention_count=attention_count,
            category_groups=category_groups,
            category_groups_collapsed=bool(page.session.store.get(CATEGORY_GROUPS_COLLAPSED_KEY)),
            on_toggle_category_groups=toggle_category_groups,
            user_email=auth.signed_in_email(page),
        )

    nav_holder = ft.Container(content=await build_nav_control(snapshot))

    async def refresh_nav() -> None:
        """The nav is only rebuilt from scratch on a full route change
        otherwise, so a view that renames/deletes a group or otherwise
        changes an envelope's assigned/spent amount without navigating
        away (e.g. `views/envelopes.py`'s `refresh_envelopes`) calls this
        - via `page.refresh_nav` - to keep the sidebar's names/totals from
        going stale while you stay on the page.

        Always re-fetches, never reuses the snapshot the shell was built
        with: the whole point of this call is that the numbers in it have
        just changed.
        """
        nav_holder.content = await build_nav_control(None)
        page.update()

    page.refresh_nav = refresh_nav

    if page.session.store.get(SETUP_IN_PROGRESS_KEY):
        body = [_setup_bar(p, lambda e: page.navigate("/first-run")), *body]
    main = _content_column(page, band, body)

    if band == "mobile":
        shell: ft.Control = ft.Column([main, nav_holder], expand=True, spacing=0)
    else:
        shell = ft.Row([nav_holder, main], expand=True, spacing=0, vertical_alignment=ft.CrossAxisAlignment.STRETCH)

    return ft.View(
        route=route,
        controls=[shell],
        padding=0,
        spacing=0,
        bgcolor=p.canvas,
    )


def _setup_bar(p: Palette, on_back) -> ft.Container:
    # A plain (non-wrap) Row: a button as a direct child of `wrap=True` paints
    # as a grey box in flet-web (see CLAUDE.md).
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.CHECKLIST_ROUNDED, size=17, color=p.ok_ink),
                ft.Text(
                    "You're setting up Envelo - come back to the checklist when this step is done.",
                    style=text_style(13, 400, p.ink),
                    expand=True,
                ),
                secondary_button(p, "Back to setup", on_back, height=34),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=p.ok_fill,
        border=ft.Border.all(1, p.ok_border),
        border_radius=12,
        padding=ft.Padding.only(left=14, right=8, top=8, bottom=8),
    )


def standalone_shell(page: ft.Page, route: str, body: list[ft.Control]) -> ft.View:
    """A screen with no nav rail - Login and First-run sit outside the app
    proper (pre-auth / pre-setup), so they aren't part of the persistent nav
    and don't show the sidebar."""
    p = palette(page)
    band = page_band(page)
    main = _content_column(page, band, body)

    return ft.View(
        route=route,
        controls=[main],
        padding=0,
        spacing=0,
        bgcolor=p.canvas,
    )
