"""Import statement - `isImport` + `isStatements` in the design, merged: the
upload form and the history of past imports are one screen now, since the
history is what tells you whether the upload actually worked, and having them
on separate routes meant navigating away to find out.

Picks a CSV, uploads it to `POST /budget/statements/upload`, and reports what
the server did with it. Only CSV is offered - the only format
`services/api-gateway/app/core/config.py::allowed_statement_formats` accepts
today - and there is no preview: the backend parses and commits in one shot,
so nothing here can show "matched"/"guessed" counts before the click without
inventing them.
"""

from datetime import datetime

import flet as ft

from api_client import collect_failures, create_statement, get_accounts, get_statements
from components.badge import badge
from components.button import primary_button, secondary_button
from components.card import bordered_panel, flat_card
from components.notice import notice_banner
from components.page_header import page_header
from components.select_field import select_field
from components.table_header import table_header
from components.toast import toast
from theme import palette, text_style
from views.common import app_shell, page_band

_STATUS_STYLES = {
    "parsed": ("Parsed", "ok_fill", "ok_ink"),
    "failed": ("Failed", "over_fill", "over_ink"),
    "pending": ("Pending", "warn_fill", "warn_ink"),
}


def _imported_label(raw: str) -> str:
    imported = datetime.fromisoformat(raw)
    return f"{imported.day} {imported.strftime('%B %Y')}"


def _file_card(p, *, name: str | None, size: int | None, on_pick) -> ft.Control:
    """Reused for both the "nothing picked yet" and "file picked" states -
    `name`/`size` are `None` for the former."""
    if name is None:
        icon, icon_color = ft.Icons.UPLOAD_FILE_OUTLINED, p.ink3
        title, subtitle, button_label = "No file chosen", "CSV files only", "Choose file"
    else:
        icon, icon_color = ft.Icons.DESCRIPTION_OUTLINED, p.ok
        title = name
        subtitle = f"CSV · {(size or 0) / 1024:.1f} kB"
        button_label = "Replace"

    return flat_card(
        p,
        ft.Row(
            [
                ft.Icon(icon, size=22, color=icon_color),
                ft.Column(
                    [
                        ft.Text(title, style=text_style(14, 500, p.ink)),
                        ft.Text(subtitle, style=text_style(12, 400, p.ink3)),
                    ],
                    spacing=3,
                    tight=True,
                    expand=True,
                ),
                secondary_button(p, button_label, on_pick),
            ],
            spacing=14,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        radius=13,
        padding=ft.Padding.symmetric(horizontal=18, vertical=17),
    )


def _history_section(p, page: ft.Page, statements: list[dict], accounts_names: dict[str, str]) -> ft.Control:
    header_row = ft.Row(
        [
            ft.Text("Past imports", style=text_style(15, 600, p.ink)),
            ft.Text(f"{len(statements)} file(s)", style=text_style(12.5, 400, p.ink3)),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    if not statements:
        panel: ft.Control = flat_card(
            p,
            ft.Text("No statements imported yet. Import one above to see it here.", style=text_style(13, 400, p.ink3)),
            radius=12,
            padding=ft.Padding.symmetric(horizontal=17, vertical=18),
        )
        return ft.Column([header_row, panel], spacing=12)

    columns = [
        ("FILE", 2, ft.TextAlign.LEFT),
        ("ACCOUNT", 1, ft.TextAlign.LEFT),
        ("IMPORTED", 1, ft.TextAlign.LEFT),
        ("STATUS", 1, ft.TextAlign.RIGHT),
    ]
    rows: list[ft.Control] = [table_header(p, columns)]
    for st in statements:
        failed = st["status"] == "failed"
        label, fill_attr, ink_attr = _STATUS_STYLES.get(st["status"], ("N/A", "sf3", "ink2"))
        fill, ink = getattr(p, fill_attr), getattr(p, ink_attr)

        # A failed import commits zero transactions (it's all-or-nothing per
        # statement - see app/services/statement_import.py), so there is
        # nothing to navigate to and the row shows why it failed instead of
        # linking out.
        if failed and st.get("error_message"):
            file_cell: ft.Control = ft.Container(
                content=ft.Column(
                    [
                        ft.Text(st["filename"], style=text_style(13.5, 500, p.ink), no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(
                            st["error_message"],
                            style=text_style(11.5, 400, p.over_ink),
                            no_wrap=True,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                    spacing=2,
                    tight=True,
                ),
                tooltip=st["error_message"],
            )
        else:
            file_cell = ft.Container(
                content=ft.Text(st["filename"], style=text_style(13.5, 500, p.ink), no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                ink=True,
                on_click=lambda e: page.navigate("/transactions"),
            )

        rows.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Row(
                            [
                                badge(
                                    st["format"].upper(),
                                    fill=p.sf3,
                                    ink=p.ink2,
                                    size=10,
                                    weight=600,
                                    radius=5,
                                    padding_x=7,
                                    padding_y=2,
                                ),
                                file_cell,
                            ],
                            spacing=10,
                            expand=2,
                        ),
                        ft.Text(
                            accounts_names.get(st["account_id"], "Unknown account"),
                            style=text_style(13, 400, p.ink2),
                            expand=1,
                            no_wrap=True,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(
                            _imported_label(st["imported_at"]),
                            style=text_style(12.5, 400, p.ink3),
                            expand=1,
                        ),
                        ft.Container(
                            content=badge(label, fill=fill, ink=ink, uppercase=False, size=12, weight=500, radius=6),
                            expand=1,
                            alignment=ft.Alignment.CENTER_RIGHT,
                        ),
                    ],
                    spacing=14,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.symmetric(horizontal=18, vertical=14),
                border=ft.Border(bottom=ft.BorderSide(1, p.sf3)),
            )
        )

    return ft.Column([header_row, bordered_panel(p, rows)], spacing=12)


async def build_import_view(page: ft.Page) -> ft.View:
    p = palette(page)
    band = page_band(page)

    with collect_failures() as failures:
        accounts = await get_accounts()
        statements = await get_statements()
    accounts_names = {a["id"]: a["name"] for a in accounts}

    if not accounts:
        body: list[ft.Control] = [page_header(p, "Import statement", eyebrow_segments=["CSV"])]
        body.append(
            notice_banner(p, "Couldn't reach the server, so nothing can be imported right now.")
            if failures
            else flat_card(
                p,
                ft.Text(
                    "No accounts yet. Add the one your statements come from, then come back here.",
                    style=text_style(13, 400, p.ink3),
                ),
                radius=13,
                padding=ft.Padding.symmetric(horizontal=18, vertical=17),
            )
        )
        return await app_shell(page, "/import", "import", body)

    picked: dict | None = None
    file_picker = ft.FilePicker()
    account_select = select_field(p, [(a["id"], a["name"]) for a in accounts], value=accounts[0]["id"])

    file_card_holder = ft.Container()
    status_holder = ft.Container()
    history_holder = ft.Container(content=_history_section(p, page, statements, accounts_names))
    cta = primary_button(p, "Choose a file to import", None)
    cta.opacity = 0.5

    def _set_cta(*, enabled: bool, label: str, handler) -> None:
        cta.content = ft.Text(label, style=text_style(13.5, 600, p.on_brand))
        cta.on_click = handler if enabled else None
        cta.ink = enabled
        cta.opacity = 1.0 if enabled else 0.5

    async def _pick_file(e: ft.ControlEvent) -> None:
        nonlocal picked
        files = await file_picker.pick_files(
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["csv"],
            with_data=True,
        )
        if not files or files[0].bytes is None:
            return
        chosen = files[0]
        picked = {"name": chosen.name, "size": chosen.size, "bytes": chosen.bytes}
        file_card_holder.content = _file_card(p, name=picked["name"], size=picked["size"], on_pick=_pick_file)
        status_holder.content = None
        _set_cta(enabled=True, label="Import statement", handler=_do_upload)
        page.update()

    async def _do_upload(e: ft.ControlEvent) -> None:
        nonlocal picked, statements
        if picked is None or not account_select.value:
            return

        _set_cta(enabled=False, label="Importing…", handler=None)
        page.update()

        result = await create_statement(account_select.value, picked["name"], picked["bytes"])

        if result is None:
            status_holder.content = notice_banner(p, "Couldn't reach the server — check your connection and try again.")
            _set_cta(enabled=True, label="Import statement", handler=_do_upload)
        elif result.get("error"):
            status_holder.content = notice_banner(p, result["error"])
            _set_cta(enabled=True, label="Import statement", handler=_do_upload)
        elif result.get("status") == "failed":
            reason = result.get("error_message") or "the file couldn't be parsed."
            status_holder.content = notice_banner(p, f"Import failed: {reason}")
            _set_cta(enabled=True, label="Import statement", handler=_do_upload)
            statements = await get_statements()
            history_holder.content = _history_section(p, page, statements, accounts_names)
        else:
            account_name = accounts_names.get(account_select.value, "your account")
            status_holder.content = toast(p, f'"{picked["name"]}" imported into {account_name} — see it below.')
            picked = None
            file_card_holder.content = _file_card(p, name=None, size=None, on_pick=_pick_file)
            _set_cta(enabled=False, label="Choose a file to import", handler=None)
            statements = await get_statements()
            history_holder.content = _history_section(p, page, statements, accounts_names)

        page.update()

    file_card_holder.content = _file_card(p, name=None, size=None, on_pick=_pick_file)

    account_card = flat_card(
        p,
        ft.Column(
            [
                ft.Text("IMPORT INTO", style=text_style(11, 500, p.ink3, letter_spacing=0.6)),
                account_select,
            ],
            spacing=7,
        ),
        radius=13,
        padding=ft.Padding.symmetric(horizontal=18, vertical=15),
    )

    top_row = (
        ft.Column([file_card_holder, account_card], spacing=14)
        if band != "desktop"
        else ft.Row(
            [ft.Container(content=file_card_holder, expand=True), ft.Container(content=account_card, expand=True)],
            spacing=14,
        )
    )

    body = [page_header(p, "Import statement", eyebrow_segments=["CSV"], actions=[cta])]

    if failures:
        body.append(notice_banner(p, "Couldn't reach the server, so accounts and past imports may be incomplete."))

    body.append(top_row)
    body.append(status_holder)
    body.append(history_holder)

    return await app_shell(page, "/import", "import", body)
