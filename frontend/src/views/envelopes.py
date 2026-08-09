"""Envelopes - `isEnvelopes` in the design: the assign bar, alerts, and the
Ledger/Cards/Flow variant tabs over every category group.

Tab selection, sort, the "needs attention only" filter and group
collapse/expand are local visual state - each interaction just re-renders this
screen's content container. Everything to do with money is real and goes through
the API Gateway.

Two refresh paths, deliberately:

* `refresh_envelopes()` re-fetches everything and rebuilds the tab. Used when the
  shape of the screen changes - a dialog saved something, a group was renamed or
  deleted, an envelope was dragged into another group.
* `refresh_amounts()` patches a single ledger row plus the screen-wide totals.
  Used by the inline Assigned/Target fields, because rebuilding the tab would
  destroy the `ft.TextField` the user is currently typing in.

An envelope is moved between category groups by dragging it - the handle in each
ledger row (or the whole card in the Cards tab) is an `ft.Draggable`, and every
group section is an `ft.DragTarget`.
"""

import asyncio
from collections.abc import Callable

import flet as ft

from api_client import (
    create_envelope_allocation,
    delete_category_group,
    get_to_assign,
    update_envelope,
    update_envelope_allocation,
)
from components.alert_row import AlertItem, alert_banner
from components.button import link_button, primary_button, secondary_button
from components.card import bordered_panel, flat_card
from components.envelope_card import envelope_card
from components.envelope_flow_row import envelope_flow_row
from components.envelope_row import DRAG_GROUP, envelope_ledger_row, refresh_envelope_ledger_row
from components.page_header import page_header
from components.select_field import select_field
from components.stat_display import stat_block
from components.table_header import table_header
from components.tabs import segmented_tabs
from currency import format_amount_bare, format_money
from dates import days_left_label, month_label
from mock_data import (
    Envelope,
    envelope_state,
    envelope_view,
)
from theme import CONTROL_HEIGHT, palette, text_style
from utils import parse_amount, range_to_dates, resolve_target, to_envelope
from views.common import app_shell, fetch_budget_snapshot, page_band
from views.dialogs import (
    assign_dialog,
    confirm_delete_dialog,
    move_dialog,
    new_envelope_dialog,
    new_group_dialog,
)

_SORTERS = {
    # Against what the envelope actually holds (carry-over included), not
    # against this month's top-up on its own.
    "left": lambda e: e.available,
    "used": lambda e: -(e.spent / max(e.funded, 1)),
    "name": lambda e: e.name,
}


async def build_envelopes_view(page: ft.Page) -> ft.View:
    p = palette(page)
    band = page_band(page)
    state = {"variant": "ledger", "attention_only": False, "sort": "default", "collapsed": {}}

    date_from, date_to = range_to_dates("this")

    async def _load() -> tuple:
        # Concurrently, not one after another: these do not depend on each
        # other, and run in series they were most of this screen's ~1.5s build
        # time. The snapshot is the same one the nav rail uses - it carries this
        # month's assignments and spending plus what each envelope carried over
        # from earlier months - and is handed to `app_shell` so the rail does
        # not fetch it all a second time.
        return await asyncio.gather(fetch_budget_snapshot(), get_to_assign())

    snapshot, to_assign = await _load()

    envelopes = snapshot.envelopes
    category_groups = snapshot.category_groups
    allocations = snapshot.allocations
    spent_by_envelope_map = snapshot.spent_this_month

    groups_by_id = {cg["id"]: cg["name"] for cg in category_groups}
    envelopes_by_id = {e["id"]: e for e in envelopes}
    allocation_by_envelope = {a["envelope_id"]: a for a in allocations if a["month"] == date_from.isoformat()}

    # Ledger rows by envelope id, so an inline edit can refresh just the row it
    # touched. Rebuilt whenever the ledger is; empty while another tab is shown.
    row_holders: dict[str, ft.Container] = {}
    # The container behind each group's drop zone, so it can be highlighted while
    # an envelope hovers over it.
    drop_holders: dict[str, ft.Container] = {}

    def _assigned_amount(envelope_id: str) -> float:
        """This month's allocation only - the value the Ledger's Assigned field
        shows and writes back. Money left over from earlier months is
        `_carried_over()`, deliberately kept apart: a field that displayed a
        running total but saved a monthly amount would silently wipe out the
        difference on the first edit."""
        alloc = allocation_by_envelope.get(envelope_id)
        return float(alloc["assigned_amount"]) if alloc else 0.0

    def _carried_over(envelope_id: str) -> float:
        return snapshot.carried_over_by_envelope.get(envelope_id, 0.0)

    def _envelope_model(raw: dict) -> Envelope:
        return to_envelope(
            raw,
            _assigned_amount(raw["id"]),
            spent_by_envelope_map.get(raw["id"], 0),
            _target_amount(raw["id"]),
            _carried_over(raw["id"]),
        )

    def _target_amount(envelope_id: str) -> float:
        """The target that applies to `date_from`'s month - an explicit
        monthly override (set via the Ledger's inline Target field) if one
        exists at or before this month, else the envelope's flat
        `target_amount` (its bootstrap default from the Add/Edit envelope
        dialog, unaffected by monthly overrides)."""
        e = next((e for e in envelopes if e["id"] == envelope_id), None)
        fallback = float(e["target_amount"]) if e and e["target_amount"] is not None else 0.0
        return resolve_target(allocations, envelope_id, date_from.isoformat(), fallback)

    async def _upsert_allocation(envelope_id: str, amount: float) -> dict | None:
        """Set this month's assigned amount for one envelope - PUT if it
        already has an allocation row for this month, POST a new one if
        not. Shared by every "assign an amount" action on this screen
        (inline edit, Fill all to target, Reset, ...).

        Returns the saved allocation row, or `None` if the write failed - callers
        use that to leave the screen exactly as it was rather than showing a
        change that never reached the server."""
        alloc = allocation_by_envelope.get(envelope_id)
        payload = {"assigned_amount": f"{amount:.2f}"}
        if alloc is not None:
            return await update_envelope_allocation(alloc["id"], payload)
        return await create_envelope_allocation(
            {**payload, "envelope_id": envelope_id, "month": date_from.isoformat()}
        )

    async def _upsert_target(envelope_id: str, amount: float) -> dict | None:
        """Set this month's target for one envelope going forward - same
        "PUT if this month already has a row, POST a new one if not" shape
        as `_upsert_allocation`, just for `target_amount`. Never touches
        another month's row, so past months keep whatever target applied
        at the time."""
        alloc = allocation_by_envelope.get(envelope_id)
        payload = {"target_amount": f"{amount:.2f}"}
        if alloc is not None:
            return await update_envelope_allocation(alloc["id"], payload)
        return await create_envelope_allocation(
            {**payload, "envelope_id": envelope_id, "month": date_from.isoformat(), "assigned_amount": "0.00"}
        )

    def _open_detail(envelope_id: str) -> Callable[[ft.ControlEvent], None]:
        def handler(e: ft.ControlEvent) -> None:
            # routing.py has no dynamic-segment mechanism, so the clicked
            # envelope's id rides along in the session store rather than the
            # URL. Note `page.session.store`, not `page.session`: the latter
            # is the Session object and has no key-value methods.
            page.session.store.set("selected_envelope_id", envelope_id)
            page.navigate("/envelopes/detail")

        return handler

    def _group_envs(cat_id: str) -> list[Envelope]:
        envs = [_envelope_model(e) for e in envelopes if e["category_group_id"] == cat_id]
        if state["attention_only"]:
            envs = [e for e in envs if envelope_state(e) != "ok"]
        if state["sort"] in _SORTERS:
            envs = sorted(envs, key=_SORTERS[state["sort"]])
        return envs

    def _group_has_any_envelopes(cat_id: str) -> bool:
        """Distinguishes a genuinely empty group (0 envelopes, should still
        show so a just-created group doesn't look like it silently failed)
        from one that only looks empty because "Needs attention only" or
        the sort/filter state narrowed `_group_envs()` down to nothing
        (still fine to hide - that's the filter doing its job)."""
        return any(e["category_group_id"] == cat_id for e in envelopes)

    async def refresh_envelopes() -> None:
        """Re-fetch everything and rebuild the tab content + assign bar -
        a full re-fetch rather than a local optimistic update, so nothing
        here keeps a "pending" local copy that could drift from the
        server. Costs one round trip per write; fine at this data volume."""
        nonlocal envelopes, category_groups, allocations, to_assign, snapshot
        nonlocal groups_by_id, envelopes_by_id, spent_by_envelope_map, allocation_by_envelope
        snapshot, to_assign = await _load()
        envelopes = snapshot.envelopes
        category_groups = snapshot.category_groups
        allocations = snapshot.allocations
        spent_by_envelope_map = snapshot.spent_this_month
        groups_by_id = {cg["id"]: cg["name"] for cg in category_groups}
        envelopes_by_id = {e["id"]: e for e in envelopes}
        allocation_by_envelope = {a["envelope_id"]: a for a in allocations if a["month"] == date_from.isoformat()}
        assign_bar_holder.content = build_assign_bar()
        alerts_holder.content = build_alerts_section()
        rerender()
        await _refresh_nav()

    async def _refresh_nav() -> None:
        refresh_nav = getattr(page, "refresh_nav", None)
        if refresh_nav is not None:
            await refresh_nav()

    async def refresh_amounts(envelope_id: str, saved: dict) -> None:
        """Apply one saved allocation without rebuilding the ledger.

        `refresh_envelopes()` above replaces the whole tab, which destroys and
        recreates both `ft.TextField`s in every row. That is fine for actions that
        end in a dialog closing, but not for an inline edit: blurring the Assigned
        field to tab into Target would wipe out the Target field the user just
        moved into, along with anything typed there. So the row the user touched
        is patched in place instead, and only the totals that genuinely depend on
        every envelope (Left to assign, alerts, the sidebar) are re-fetched.
        """
        # Merged onto what was already known rather than stored as-is: the saved
        # row is whatever JSON the server returned, and the local caches are
        # keyed/filtered by `envelope_id` and `month`, so a response missing
        # either would poison `resolve_target()` for every other envelope.
        previous = allocation_by_envelope.get(envelope_id, {})
        row = {"envelope_id": envelope_id, "month": date_from.isoformat(), **previous, **saved}
        allocation_by_envelope[envelope_id] = row
        for stale in [a for a in allocations if a.get("id") == row.get("id")]:
            allocations.remove(stale)
        allocations.append(row)

        nonlocal to_assign
        to_assign = await get_to_assign()
        assign_bar_holder.content = build_assign_bar()
        alerts_holder.content = build_alerts_section()

        row = row_holders.get(envelope_id)
        raw = envelopes_by_id.get(envelope_id)
        if row is not None and raw is not None:
            refresh_envelope_ledger_row(row, p, envelope_view(p, _envelope_model(raw)))
        page.update()
        await _refresh_nav()

    async def _save_assigned(envelope_id: str, amount: float) -> None:
        saved = await _upsert_allocation(envelope_id, amount)
        if saved is not None:
            await refresh_amounts(envelope_id, saved)

    def _on_assign_change(envelope_id: str) -> Callable[[ft.ControlEvent], None]:
        """Skips the write when the value has not changed - without it, merely
        tabbing through the ledger fired a write plus five GETs per field.

        The comparison reads the stored amount at event time rather than closing
        over what the row was built with: an inline edit deliberately does not
        rebuild the row, so a captured value goes stale the moment the first edit
        lands, and editing back to the previous amount would be dropped."""

        def handler(e: ft.ControlEvent) -> None:
            current = _assigned_amount(envelope_id)
            amount = parse_amount(e.control.value)
            if amount is None:
                # Unreadable input: put back what is actually stored rather than
                # leaving a value on screen that no longer matches the server.
                e.control.value = format_amount_bare(current)
                page.update()
                return
            if abs(float(amount) - current) < 0.005:
                # Re-render it anyway: "60" becomes "60,00", so the column stays
                # aligned and the next comparison sees the canonical form.
                e.control.value = format_amount_bare(current)
                page.update()
                return
            page.run_task(_save_assigned, envelope_id, float(amount))

        return handler

    def _on_fill_to_target(envelope_id: str, target: float) -> Callable[[ft.ControlEvent], None]:
        def handler(e: ft.ControlEvent) -> None:
            if target:
                page.run_task(_save_assigned, envelope_id, target)

        return handler

    async def _save_target(envelope_id: str, amount: float) -> None:
        saved = await _upsert_target(envelope_id, amount)
        if saved is not None:
            await refresh_amounts(envelope_id, saved)

    def _on_target_change(envelope_id: str) -> Callable[[ft.ControlEvent], None]:
        """Same live-value comparison as `_on_assign_change`, for the Target
        column."""

        def handler(e: ft.ControlEvent) -> None:
            current = _target_amount(envelope_id)
            amount = parse_amount(e.control.value)
            if amount is None or abs(float(amount) - current) < 0.005:
                e.control.value = format_amount_bare(current) if current else ""
                page.update()
                return
            page.run_task(_save_target, envelope_id, float(amount))

        return handler

    async def _move_to_group(envelope_id: str, category_group_id: str) -> None:
        """Reassign an envelope to another category group (the drag & drop drop
        handler). A full `refresh_envelopes()` is right here, unlike for an inline
        amount edit: the row has to physically move to another section, and no
        field is focused mid-drag."""
        if await update_envelope(envelope_id, {"category_group_id": category_group_id}) is None:
            return
        await refresh_envelopes()

    def _on_drop_into_group(cat_id: str) -> Callable[[ft.DragTargetEvent], None]:
        def handler(e: ft.DragTargetEvent) -> None:
            envelope_id = getattr(e.src, "data", None)
            envelope = envelopes_by_id.get(envelope_id) if envelope_id else None
            # A drop back onto its own group is a no-op, not a round trip.
            if envelope is None or envelope["category_group_id"] == cat_id:
                _set_drop_highlight(cat_id, False)
                return
            _set_drop_highlight(cat_id, False)
            page.run_task(_move_to_group, envelope_id, cat_id)

        return handler

    async def _fill_all_to_target() -> None:
        for e in envelopes:
            target = _target_amount(e["id"])
            if target:
                await _upsert_allocation(e["id"], target)
        await refresh_envelopes()

    async def _reset_all_assigned() -> None:
        for envelope_id in list(allocation_by_envelope):
            await _upsert_allocation(envelope_id, 0)
        await refresh_envelopes()

    def _open_assign(envelope_id: str | None = None) -> Callable[[ft.ControlEvent], None]:
        def handler(e: ft.ControlEvent) -> None:
            page.show_dialog(
                assign_dialog(
                    page,
                    envelopes=envelopes,
                    to_assign=to_assign,
                    on_assign=_save_assigned,
                    envelope_id=envelope_id,
                    current_amount=_assigned_amount(envelope_id) if envelope_id else None,
                )
            )

        return handler

    def _open_move(
        *, from_id: str | None = None, to_id: str | None = None, amount: float | None = None
    ) -> Callable[[ft.ControlEvent], None]:
        def handler(e: ft.ControlEvent) -> None:
            page.show_dialog(
                move_dialog(
                    page, envelopes=envelopes, on_moved=refresh_envelopes, from_id=from_id, to_id=to_id, amount=amount
                )
            )

        return handler

    def _open_add_envelope(cat_id: str | None = None) -> Callable[[ft.ControlEvent], None]:
        def handler(e: ft.ControlEvent) -> None:
            page.show_dialog(
                new_envelope_dialog(
                    page,
                    category_groups=category_groups,
                    default_category_group_id=cat_id,
                    on_saved=refresh_envelopes,
                )
            )

        return handler

    def _open_rename_group(cat_id: str) -> Callable[[ft.ControlEvent], None]:
        def handler(e: ft.ControlEvent) -> None:
            group = next(cg for cg in category_groups if cg["id"] == cat_id)
            page.show_dialog(
                new_group_dialog(page, category_group=group, on_saved=refresh_envelopes)
            )

        return handler

    def _open_delete_group(cat_id: str, cat_name: str) -> Callable[[ft.ControlEvent], None]:
        async def do_delete() -> str | None:
            result = await delete_category_group(cat_id)
            if result is None:
                return "Couldn't delete — try again."
            if isinstance(result, dict) and result.get("error"):
                return result["error"]
            await refresh_envelopes()
            return None

        def handler(e: ft.ControlEvent) -> None:
            page.show_dialog(
                confirm_delete_dialog(
                    page,
                    title="Delete category group?",
                    message=f'Delete "{cat_name}"? This can\'t be undone.',
                    on_confirm=do_delete,
                )
            )

        return handler

    def _alerts() -> list[AlertItem]:
        all_envs = [_envelope_model(e) for e in envelopes]
        ranked = sorted(
            [e for e in all_envs if envelope_state(e) != "ok"],
            key=lambda e: 1 if envelope_state(e) == "over" else 0,
            reverse=True,
        )
        items = []
        for e in ranked[:2]:
            ev = envelope_view(p, e)
            over = ev.state == "over"
            overspend = e.spent - e.funded
            message = (
                f"{e.name} is {format_money(overspend)} over its plan"
                if over
                else f"{e.name} is at {ev.pct}% — {ev.state_label}"
            )
            items.append(
                AlertItem(
                    message=message,
                    cta="Cover it" if over else "Move money",
                    dot_color=p.over if over else p.warn,
                    on_fix=_open_move(to_id=e.id, amount=overspend if overspend > 0 else None),
                )
            )
        return items

    # Reserved on every drop zone so switching it to a visible colour cannot
    # shift the layout by 2px mid-drag.
    _NO_HIGHLIGHT = ft.Border.all(2, "transparent")

    def _set_drop_highlight(cat_id: str, on: bool) -> None:
        """Outline the group, never fill it.

        Filling the whole section with `ok_fill` tinted every envelope inside it,
        which read as "all of these are selected" while only the one under the
        cursor was moving. An outline says the same thing about where the drop
        will land without making any claim about the rows."""
        holder = drop_holders.get(cat_id)
        if holder is None:
            return
        holder.border = ft.Border.all(2, p.ok) if on else _NO_HIGHLIGHT
        page.update()

    def _source_group_of(e) -> str | None:
        """Which group the envelope being dragged currently sits in.

        `DragWillAcceptEvent` resolves the source `Draggable`, and each handle
        carries its envelope id as `data` - so the group is known while hovering,
        not just on drop."""
        envelope_id = getattr(getattr(e, "src", None), "data", None)
        envelope = envelopes_by_id.get(envelope_id) if envelope_id else None
        return envelope["category_group_id"] if envelope else None

    def _on_will_accept(cat_id: str) -> Callable[[ft.DragWillAcceptEvent], None]:
        def handler(e: ft.DragWillAcceptEvent) -> None:
            # Hovering an envelope over its own group promises nothing - the drop
            # is already a documented no-op - so it must not light up as if it
            # were about to move something.
            _set_drop_highlight(cat_id, _source_group_of(e) != cat_id)

        return handler

    def _drop_target(cat_id: str, content: ft.Control) -> ft.Control:
        """Make a whole category-group section accept dropped envelopes.

        The section rather than just its header strip: a 44px header is a poor
        target to aim at mid-drag, and an empty group would have no other surface
        to drop onto at all. The highlight is what tells the user where the
        envelope will land, so it is not decoration - without it a drag over a
        long ledger gives no feedback at all.
        """
        holder = ft.Container(content=content, border=_NO_HIGHLIGHT, border_radius=10)
        drop_holders[cat_id] = holder
        return ft.DragTarget(
            group=DRAG_GROUP,
            content=holder,
            on_will_accept=_on_will_accept(cat_id),
            on_leave=lambda e, gid=cat_id: _set_drop_highlight(gid, False),
            on_accept=_on_drop_into_group(cat_id),
        )

    def ledger_content() -> ft.Control:
        row_holders.clear()
        drop_holders.clear()
        columns = [("ENVELOPE", 2, ft.TextAlign.LEFT)]
        if band != "mobile":
            columns += [
                ("ASSIGNED", 1, ft.TextAlign.RIGHT),
                ("TARGET", 1, ft.TextAlign.RIGHT),
                ("SPENT", 1, ft.TextAlign.RIGHT),
            ]
        columns.append(("LEFT", 1, ft.TextAlign.RIGHT))
        if band == "desktop":
            columns.append(("PROGRESS", 2, ft.TextAlign.LEFT))

        rows: list[ft.Control] = [table_header(p, columns)]
        for cat_id, cat_name in groups_by_id.items():
            envs = _group_envs(cat_id)
            if not envs and _group_has_any_envelopes(cat_id):
                # Every envelope in this group got filtered out (e.g.
                # "Needs attention only") - hide the group, same as before.
                continue
            left = sum(e.assigned - e.spent for e in envs)
            collapsed = state["collapsed"].get(cat_id, False)
            section: list[ft.Control] = []

            def toggle(e: ft.ControlEvent, gid: str = cat_id) -> None:
                state["collapsed"][gid] = not state["collapsed"].get(gid, False)
                rerender()

            section.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Text("▸" if collapsed else "▾", style=text_style(11, 500, p.ink3)),
                                    ft.Text(cat_name, style=text_style(13.5, 600, p.ink)),
                                ],
                                spacing=9,
                            ),
                            ft.Row(
                                [
                                    ft.Text(f"{format_money(left)} left", style=text_style(13, 500, p.ink2)),
                                    link_button(p, "Rename", _open_rename_group(cat_id)),
                                    link_button(p, "Delete", _open_delete_group(cat_id, cat_name), color=p.over_ink),
                                ],
                                spacing=14,
                            ),
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
            if not collapsed and not envs:
                section.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Text("No envelopes in this group yet.", style=text_style(12.5, 400, p.ink3)),
                                link_button(p, "+ Add envelope", _open_add_envelope(cat_id)),
                            ],
                            spacing=14,
                        ),
                        padding=ft.Padding.symmetric(horizontal=18, vertical=16),
                        border=ft.Border(bottom=ft.BorderSide(1, p.sf3)),
                    )
                )
            elif not collapsed:
                for e in envs:
                    row = envelope_ledger_row(
                        p,
                        envelope_view(p, e),
                        band,
                        on_open=_open_detail(e.id),
                        on_assign_change=_on_assign_change(e.id),
                        on_target_change=_on_target_change(e.id),
                    )
                    row_holders[e.id] = row
                    section.append(row)

            rows.append(_drop_target(cat_id, ft.Column(section, spacing=0)))

        rows.append(
            ft.Container(
                content=ft.Text("+ Add category group", style=text_style(13, 500, p.ink3)),
                padding=ft.Padding.symmetric(horizontal=18, vertical=14),
                bgcolor=p.sf,
                ink=True,
                on_click=lambda e: page.show_dialog(
                    new_group_dialog(page, category_groups=category_groups, on_saved=refresh_envelopes)
                ),
            )
        )
        return bordered_panel(p, rows)

    def cards_content() -> ft.Control:
        row_holders.clear()
        drop_holders.clear()
        sections = []
        for cat_id, cat_name in groups_by_id.items():
            envs = _group_envs(cat_id)
            if not envs and _group_has_any_envelopes(cat_id):
                # Every envelope in this group got filtered out (e.g.
                # "Needs attention only") - hide the group, same as before.
                continue
            left = sum(e.assigned - e.spent for e in envs)
            header = ft.Row(
                [
                    ft.Row(
                        [
                            ft.Text(cat_name.upper(), style=text_style(13, 600, p.ink3, letter_spacing=0.6)),
                            link_button(p, "Rename", _open_rename_group(cat_id)),
                            link_button(p, "Delete", _open_delete_group(cat_id, cat_name), color=p.over_ink),
                        ],
                        spacing=14,
                    ),
                    ft.Text(f"{format_money(left)} left", style=text_style(12.5, 500, p.ink2)),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
            if not envs:
                body: ft.Control = ft.Container(
                    content=ft.Row(
                        [
                            ft.Text("No envelopes in this group yet.", style=text_style(12.5, 400, p.ink3)),
                            link_button(p, "+ Add envelope", _open_add_envelope(cat_id)),
                        ],
                        spacing=14,
                    ),
                    padding=ft.Padding.symmetric(vertical=8),
                )
            else:
                cards = [
                    ft.Container(
                        content=envelope_card(
                            p,
                            envelope_view(p, e),
                            on_open=_open_detail(e.id),
                            on_assign=_open_assign(e.id),
                            on_move=_open_move(from_id=e.id),
                            draggable=True,
                        ),
                        col={"xs": 12, "sm": 6, "lg": 4},
                    )
                    for e in envs
                ]
                body = ft.ResponsiveRow(cards, spacing=14, run_spacing=14)
            sections.append(_drop_target(cat_id, ft.Column([header, body], spacing=12)))
        return ft.Column(sections, spacing=26)

    def flow_content() -> ft.Control:
        envs = [e for cat_id in groups_by_id for e in _group_envs(cat_id)]
        rows = [
            envelope_flow_row(
                p,
                envelope_view(p, e),
                on_open=_open_detail(e.id),
                on_fill_target=_on_fill_to_target(e.id, e.target),
                on_move=_open_move(from_id=e.id),
                on_cover=_open_move(
                    to_id=e.id, amount=(e.spent - e.assigned) if (e.spent - e.assigned) > 0 else None
                ),
            )
            for e in envs
        ]
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
        toolbar_right_row.controls = build_toolbar_right()
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

    def build_assign_bar() -> ft.Control:
        to_assign_color = p.over_ink if to_assign < 0 else (p.ink2 if to_assign == 0 else p.ok_ink)
        to_assign_hint = (
            "You have assigned more than you have — take some back."
            if to_assign < 0
            else ("Every euro has a job. Nice." if to_assign == 0 else "Give this a job before the month starts.")
        )
        return flat_card(
            p,
            ft.Row(
                [
                    ft.Container(
                        content=stat_block(
                            p,
                            "Left to assign",
                            format_money(to_assign),
                            value_size=42,
                            value_color=to_assign_color,
                            note=to_assign_hint,
                        ),
                        ink=True,
                        on_click=_open_assign(),
                    ),
                    ft.Row(
                        [
                            secondary_button(p, "Fill all to target", lambda e: page.run_task(_fill_all_to_target)),
                            ft.Container(
                                content=ft.Text("Reset", style=text_style(12.5, 500, p.ink3)),
                                height=40,
                                padding=ft.Padding.symmetric(horizontal=13),
                                alignment=ft.Alignment.CENTER,
                                ink=True,
                                on_click=lambda e: page.run_task(_reset_all_assigned),
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
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

    assign_bar_holder = ft.Container(content=build_assign_bar())

    def build_alerts_section() -> ft.Control | None:
        alerts = _alerts()
        return alert_banner(p, alerts) if alerts else None

    alerts_holder = ft.Container(content=build_alerts_section())

    def build_toolbar_right() -> list[ft.Control]:
        controls: list[ft.Control] = []
        if band != "mobile":
            # Explicit `CONTROL_HEIGHT` on the button: buttons still default to
            # 40, which is fine on their own, but not beside a select - see that
            # constant for why a select cannot be shorter than 48.
            controls.append(
                secondary_button(
                    p,
                    "Needs attention only",
                    toggle_attention,
                    active=state["attention_only"],
                    height=CONTROL_HEIGHT,
                )
            )
            controls.append(
                select_field(
                    p,
                    [
                        ("default", "Sort: group order"),
                        ("left", "Sort: least money left"),
                        ("used", "Sort: most used"),
                        ("name", "Sort: name"),
                    ],
                    # Read from state, never hardcoded: `rerender()` rebuilds this
                    # toolbar, so a literal here resets the dropdown to "group
                    # order" the moment sorting by anything else re-renders the
                    # screen - the selection was applied but never shown.
                    value=state["sort"],
                    on_select=on_sort,
                )
            )
        return controls

    toolbar_right_row = ft.Row(
        build_toolbar_right(), spacing=9, vertical_alignment=ft.CrossAxisAlignment.CENTER
    )

    body: list[ft.Control] = [
        page_header(
            p,
            "Envelopes",
            eyebrow_segments=[month_label(), days_left_label()],
            actions=[
                secondary_button(p, "Move money", _open_move()),
                primary_button(p, "Add envelope", _open_add_envelope()),
            ],
        ),
        assign_bar_holder,
    ]

    body.append(alerts_holder)

    body.append(
        ft.Row(
            [tabs_holder, toolbar_right_row],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            wrap=True,
            spacing=16,
        )
    )
    body.append(variant_holder)

    return await app_shell(page, "/envelopes", "envelopes", body, snapshot=snapshot)
