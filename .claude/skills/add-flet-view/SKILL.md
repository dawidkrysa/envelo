---
name: add-flet-view
description: Scaffold a new Flet screen/route in the envelo frontend following the repo's established view/routing/component conventions. Use when adding a new page to the app (e.g. "add a budget goals screen", "new /reports route").
---

Add a new screen to `frontend/src/` following the patterns already used by every existing view (see `frontend/src/views/*.py`). Work through these steps in order:

1. **Create the view file** at `frontend/src/views/<name>.py` with `async def build_<name>_view(page: ft.Page) -> ft.View`. Model it on an existing view close to what's needed:
   - A list/CRUD-style screen → `views/rules.py` or `views/payees.py`.
   - A detail screen → `views/envelope_detail.py`.
   - A screen with no nav (pre-auth/setup) → `views/login.py` / `views/first_run.py`.
   Build the body as `list[ft.Control]`, starting with `components/page_header.page_header(p, title, eyebrow_segments=..., actions=...)`, then pass it to `views.common.app_shell(page, route, active_nav_id, body)` (has the nav) or `standalone_shell(page, route, body)` (no nav) as the return value. Get `p = palette(page)` from `theme.py` at the top.

2. **Register the route** in `frontend/src/routing.py`:
   - Import the builder and add `"/<route>": build_<name>_view` to `VIEW_BUILDERS`.
   - If this screen should pop back to something other than `/` (e.g. it's a sub-page of another section), add an entry to `ROUTE_PARENTS` mapping it to its parent route.

3. **If it's a main-nav destination** (not a sub-page reached via a button/link), add a `NavItem` to the right `NavGroup` in `frontend/src/components/nav_rail.py`'s `NAV_GROUPS`, and add an icon mapping in `ICONS`. If it should also appear in the mobile bottom bar, add its `id` to `MOBILE_NAV_IDS` (max 5 items fit there — check before adding). The `active_nav_id` passed to `app_shell()` must match the `NavItem.id` you used.

4. **Use existing components** from `frontend/src/components/` rather than hand-rolling controls: `button.py` (`primary_button`/`secondary_button`/`ghost_button`/`danger_button`/`link_button` — these are `ft.Container(ink=True, ...)`, not `ft.*Button`), `card.py`, `page_header.py`, `badge.py`, `progress_bar.py`, `modal_dialog.py` (dialogs go in `views/dialogs.py`, opened via `page.show_dialog(...)`, closed via `page.pop_dialog()` — not `page.open()`, which doesn't exist in this Flet version). Check `docs/brandbook.md` for the design spec (colors, spacing, copy tone) before inventing new visual treatment.

5. **Avoid the known `wrap=True` rendering bug**: any `ft.Row(wrap=True)` whose *direct* children include a button `Container`, `ft.Dropdown`, or `ft.TextField` renders as a flat grey box. If a row of buttons/inputs needs to wrap on narrow widths, nest them one level deeper (a non-wrap Row/Column as the direct child) instead of using `wrap=True` directly on the row containing them. See `components/page_header.py`'s `page_header()` for a worked example of the safe pattern (outer Row wraps, inner button Row doesn't).

6. **Use mock data** for now — pull from `frontend/src/mock_data.py` (add a new constant there if needed, shaped like the real schema per `docs/erd.md`) rather than wiring the API client, matching every other view's current state.

7. **Verify**: `frontend/tests/test_views.py` parametrizes `test_builder_returns_view_for_its_route` and the no-default-padding test over every route in `VIEW_BUILDERS` automatically, so a correctly registered route is covered without writing a new test — just run `cd frontend && uv run pytest tests/test_routing.py tests/test_views.py` (skip `test_main.py`; it needs Windows Developer Mode, which is disabled on this machine). Add a dedicated test only if the view has custom interactive behavior (see `test_action_buttons_open_a_dialog` or `test_settings_threshold_slider_updates_its_own_label` for the pattern — build a `stub_page()`, call the builder, then use `find_button()`/`walk()` to locate controls).
