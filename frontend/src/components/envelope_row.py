"""Envelope ledger row - the table row inside the Envelopes screen's "Ledger"
tab, with per-breakpoint column counts (name/state, assigned, target, spent,
left, progress+%).

Two things make this more than a layout function:

* the row carries its own drag handle, so an envelope can be dropped onto another
  category group's section;
* it hands back references to every cell whose text is *derived* from the amounts
  (`LedgerRowCells`, stashed on the returned container's `data`), so the screen
  can refresh a row after an inline edit without rebuilding it - rebuilding
  destroys the `ft.TextField` the user is typing in.
"""

from collections.abc import Callable
from dataclasses import dataclass

import flet as ft

from components.input_field import amount_input
from components.progress_bar import progress_bar
from currency import format_amount_bare
from mock_data import EnvelopeView
from theme import Palette, text_style

DRAG_GROUP = "envelope"
"""Shared by the row's `ft.Draggable` and the group sections' `ft.DragTarget`s -
Flet only offers a drop when both sides name the same group."""


@dataclass
class LedgerRowCells:
    """The parts of a row that change when its amounts change. Everything else
    (name, drag handle, the text fields themselves) is left alone on refresh."""

    state: ft.Text
    left: ft.Text
    spent: ft.Text | None = None
    progress: ft.Container | None = None


def _drag_handle(p: Palette, envelope_id: str, name: str) -> ft.Control:
    """Only the handle is draggable, never the whole row.

    A `Draggable` wrapping the row would install a pan recognizer competing in the
    same gesture arena as the assign/target `ft.TextField`s' own drag-to-select
    gesture, so selecting text would start dragging the envelope instead.
    `affinity=VERTICAL` narrows that but does not remove it - a vertical drag
    started inside the field still wins. A separate handle keeps the two apart.
    """
    return ft.Draggable(
        group=DRAG_GROUP,
        data=envelope_id,
        content=ft.Container(
            content=ft.Icon(ft.Icons.DRAG_INDICATOR, size=15, color=p.ink3),
            width=18,
            tooltip="Drag to another category group",
        ),
        content_feedback=ft.Container(
            content=ft.Text(name, style=text_style(13, 500, p.ink)),
            bgcolor=p.sf,
            border=ft.Border.all(1, p.ok),
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            opacity=0.9,
        ),
    )


def envelope_ledger_row(
    p: Palette,
    ev: EnvelopeView,
    band: str,
    *,
    on_open: Callable[[ft.ControlEvent], None] | None = None,
    on_assign_change: Callable[[ft.ControlEvent], None] | None = None,
    on_target_change: Callable[[ft.ControlEvent], None] | None = None,
    currency_symbol: str | None = None,
    draggable: bool = True,
) -> ft.Container:
    not_mobile = band != "mobile"
    is_desktop = band == "desktop"

    state_text = ft.Text(
        ev.state_label, style=text_style(11.5, 400, ev.state_ink), no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS
    )
    name_block = ft.Column(
        [
            ft.Container(
                content=ft.Text(
                    ev.name, style=text_style(14, 500, p.ink), no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS
                ),
                ink=True,
                on_click=on_open,
            ),
            state_text,
        ],
        spacing=3,
        tight=True,
        expand=True,
    )
    # The handle lives inside the ENVELOPE column rather than in a column of its
    # own, so the row still lines up with `table_header`'s existing columns.
    name_col = ft.Row(
        ([_drag_handle(p, ev.id, ev.name)] if draggable else []) + [name_block],
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        expand=2,
    )

    cells: list[ft.Control] = [name_col]
    spent_text: ft.Text | None = None
    progress_holder: ft.Container | None = None

    if not_mobile:
        # on_submit as well as on_blur: pressing Enter is how most people commit
        # a value in a table, and it used to do nothing at all here.
        cells.append(
            ft.Container(
                content=amount_input(
                    p,
                    value=format_amount_bare(ev.assigned),
                    currency_symbol=currency_symbol,
                    on_blur=on_assign_change,
                    on_submit=on_assign_change,
                ),
                # The field has a fixed width while its column is a flex cell, so
                # without this it hugs the left edge while the ASSIGNED/TARGET
                # header labels are right-aligned - the visible drift between the
                # two. Right-aligning lines the field's right edge up with the
                # header, and with the right-aligned SPENT/LEFT columns.
                alignment=ft.Alignment.CENTER_RIGHT,
                expand=1,
            )
        )
        cells.append(
            ft.Container(
                content=amount_input(
                    p,
                    value=ev.target_str,
                    currency_symbol=currency_symbol,
                    on_blur=on_target_change,
                    on_submit=on_target_change,
                ),
                # The field has a fixed width while its column is a flex cell, so
                # without this it hugs the left edge while the ASSIGNED/TARGET
                # header labels are right-aligned - the visible drift between the
                # two. Right-aligning lines the field's right edge up with the
                # header, and with the right-aligned SPENT/LEFT columns.
                alignment=ft.Alignment.CENTER_RIGHT,
                expand=1,
            )
        )
        spent_text = ft.Text(
            ev.spent_str, style=text_style(13.5, 400, p.ink2), text_align=ft.TextAlign.RIGHT, expand=1
        )
        cells.append(spent_text)

    left_text = ft.Text(
        ev.left_str, style=text_style(14.5, 500, ev.left_ink), text_align=ft.TextAlign.RIGHT, expand=1
    )
    cells.append(left_text)

    if is_desktop:
        progress_holder = ft.Container(content=_progress_cell(p, ev), expand=2)
        cells.append(progress_holder)

    row = ft.Container(
        # spacing must match `table_header`'s 14 (and `transaction_row`'s): the
        # gaps sit between the same flex cells, so a 2px difference per gap
        # accumulates across the row and walks every column out of line with its
        # own header - worst at the far right.
        content=ft.Row(cells, spacing=14, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=18, vertical=13),
        border=ft.Border(bottom=ft.BorderSide(1, p.sf3)),
    )
    # `data` is server-side only (never serialized to the client), so parking the
    # cell references here costs nothing on the wire.
    row.data = LedgerRowCells(state=state_text, left=left_text, spent=spent_text, progress=progress_holder)
    return row


def _progress_cell(p: Palette, ev: EnvelopeView) -> ft.Control:
    return ft.Row(
        [
            ft.Container(content=progress_bar(p, ev.fill_fraction, color=ev.bar_color), expand=True),
            ft.Text(ev.pct_str, style=text_style(11.5, 500, p.ink2), width=38, text_align=ft.TextAlign.RIGHT),
        ],
        spacing=11,
        expand=2,
    )


def refresh_envelope_ledger_row(row: ft.Container, p: Palette, ev: EnvelopeView) -> None:
    """Re-render only the derived cells of an existing row.

    Used after an inline amount edit: the two `ft.TextField`s keep their identity
    (and therefore the user's focus and caret), while everything computed from the
    amounts catches up. The progress cell is swapped wholesale rather than poked
    at, because `progress_bar()` wraps the actual `ft.ProgressBar` in layout rows
    that this module has no business reaching into.
    """
    cells = row.data
    if not isinstance(cells, LedgerRowCells):
        return
    cells.state.value = ev.state_label
    cells.state.style = text_style(11.5, 400, ev.state_ink)
    cells.left.value = ev.left_str
    cells.left.style = text_style(14.5, 500, ev.left_ink)
    if cells.spent is not None:
        cells.spent.value = ev.spent_str
    if cells.progress is not None:
        cells.progress.content = _progress_cell(p, ev)
