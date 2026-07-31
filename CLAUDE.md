# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project shape

Envelo is a monorepo, currently two runnable services (the README frames it as a "modular monolith gradually split into microservices" — the Auth/Ingestion/Analytics split in `docs/architecture.md` is aspirational, not yet real):

- `frontend/` — Flet 0.86 (Python) UI, managed with `uv` + `pyproject.toml`. `frontend/requirements.txt` only pins `flet==0.86.2` for reference; it is not the source of truth for deps.
- `services/api-gateway/` — FastAPI + SQLAlchemy 2.0 (async) + Alembic, managed with plain pip + `requirements.txt` (no pyproject.toml here). Holds all budgeting logic today.
- `docs/` — `architecture.md`, `erd.md`, `migrations.md`, and `brandbook.md` (design source of truth for the frontend — see below).

**No CI exists** (`.github/workflows` is absent) and **no linter/formatter is configured** anywhere in the repo (no ruff/black/eslint config, despite the README's aspirational tech-stack table). Don't assume either gates changes.

## Frontend (Flet)

- Two entrypoints that must behave the same but stay separate: `main.py` (used by `flet run` / `flet test`, keeps the `if __name__ == "__main__"` guard) and `asgi.py` (Docker/uvicorn production entrypoint, `export_asgi_app=True`).
- Routing: `routing.py` has `VIEW_BUILDERS` (route → `async def build_x_view(page) -> ft.View`) and `ROUTE_PARENTS` (back-stack parent for routes that shouldn't pop straight to `/`). Add both when adding a route.
- `views/common.py` provides the shared shell: `app_shell()` (main screens with nav) and `standalone_shell()` (Login/First-run, no nav). Both set `padding=0, spacing=0` on the returned `ft.View` deliberately — `ft.View` defaults to 10px of both, which gaps the header from the nav rail. The content column inside is already scrollable (`ft.ScrollMode.AUTO`); views must not set their own `scroll=`.
- No CSS media queries in Flet — responsiveness is driven by `theme.layout_band(page.width)` → `"mobile"/"tablet"/"desktop"`. `page.width` is `None` before the first frame, so band helpers default to desktop. Views are rebuilt on `page.on_resize` only when the band changes, not on every resize.
- Buttons (`components/button.py`) are `ft.Container(ink=True, ...)` wrapping `ft.Text`, not `ft.*Button` widgets — relevant when locating buttons in tests or by control type.
- **Known rendering bug**: an `ft.Row(wrap=True)` whose *direct* children include an interactive control (button `Container`, `ft.Dropdown`, `ft.TextField`) paints as a flat grey box instead of real content, in flet-web and presumably flet-desktop. Nesting the control one level deeper (inside a non-wrap child Row/Column) is fine. Don't put interactive controls as direct children of a `wrap=True` Row — use a fixed/horizontally-scrolling row instead.
- `ft.LineChart`/`ft.BarChart` don't exist in this Flet version (they're in the separate `flet-charts` package, not a dependency here). Charts/graphs are built from `ft.ProgressBar` or plain containers.
- `docs/brandbook.md` is the source of truth for design tokens; `theme.py` ports it 1:1. If they disagree, fix `theme.py`, not the brandbook. Money is formatted EU-style (`1.234,56 €`, comma decimals, trailing " €", `−` minus sign) — see `mock_data.py`'s formatter.
- All views currently render mock data from `mock_data.py`. `api_client.get_health()` exists and is tested (`tests/test_api_client.py`) but isn't called from `main.py`/`routing.py` yet — there is no real backend call wired into the app at all so far.
- `gallery.py` is a standalone visual QA screen showing every component (`flet run src/gallery.py`) — not part of the routed app.

## Backend (api-gateway)

- All FastAPI routes for every entity live in the single `app/main.py` (~530 lines) — there is no `app/routers/` package. Only the repository layer (`app/db/repositories/`) is split one file per entity.
- Repository functions call `db.commit()` themselves, not the router — relevant when reasoning about transaction boundaries or test rollback behavior.
- Route path params are `camelCase` (e.g. `/{accountId}`) to match frontend/JS conventions, even though function/variable names stay `snake_case` — a deliberate PEP8 mismatch, not an inconsistency to fix.
- Categorization: `match_envelope_for_transaction()` (`app/db/repositories/categorization_rule.py`) first tries the payee's most-frequent past envelope, then falls back to phrase-matching `CategorizationRule.phrase` against the transaction description (case-insensitive substring), preferring the longest matching phrase on ties.
- Alembic: run from `services/api-gateway` (`alembic upgrade head`, `alembic revision --autogenerate -m "..."`). `alembic_version` intentionally lives in the `budget` schema, not `public`. `migrations/env.py` builds the DB URL from `Settings`, not `alembic.ini`.

## Testing

- Backend tests (`services/api-gateway`, run via `pytest`) use a **real Postgres**, not mocks — `tests/conftest.py` wraps each test in a transaction with a `SAVEPOINT` that's rolled back after, so `db.commit()` calls never actually persist. Assume Postgres is already running (`docker compose up -d postgres`) rather than starting it yourself.
- `pytest.ini` sets `asyncio_mode = auto`.
- Frontend tests (`frontend`, run via `uv run pytest`): `test_routing.py`, `test_mock_data.py`, `test_api_client.py`, `test_views.py` are pure/logic-level and reliable locally. `test_main.py` drives a real rendered Flet app via the `flet[test]` integration-test plugin — on this machine it fails with "Building with plugins requires symlink support" because **Windows Developer Mode is disabled**. Treat `test_main.py` failures as this known environment limitation, not a code bug, unless Developer Mode has since been enabled.
