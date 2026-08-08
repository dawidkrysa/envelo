from pathlib import Path

import flet as ft

from currency import CURRENCY_STORAGE_KEY, DEFAULT_CURRENCY, set_currency
from preferences import (
    ALERT_THRESHOLD_STORAGE_KEY,
    DARK_MODE_STORAGE_KEY,
    DEFAULT_ALERT_THRESHOLD,
    set_alert_threshold,
    set_dark_mode,
)
from routing import build_view, stack_for_route
from theme import apply_theme, layout_band

# src/assets is served at the web root, so favicon.png overrides the stock
# Flet icon in the browser tab and fonts/icon.png resolve for the app build.
# Without this nothing under assets/ is served at all.
#
# Anchored to this file rather than left as a bare "assets": a relative path
# resolves against the process's current working directory, which depends on
# how the app is launched (repo root vs frontend/ vs frontend/src/) - and a
# wrong cwd doesn't error, it just serves 404s for every asset, fonts
# included, with no obvious cause.
ASSETS_DIR = str(Path(__file__).parent / "assets")


async def _saved(page: ft.Page, key: str):
    """One stored preference, or `None` if it cannot be read.

    Failures are swallowed: shared preferences are unavailable in some hosts (and
    in tests), and an unreadable preference is not a reason to refuse to start.
    """
    try:
        return await page.shared_preferences.get(key)
    except Exception:
        return None


async def _restore_preferences(page: ft.Page) -> None:
    """Load what the Settings screen saved, before anything renders.

    Every screen formats its amounts - and resolves its envelope states, and the
    colors that follow from them - at build time, so this has to happen before the
    first `route_change()`. Otherwise the app paints once with the defaults and
    only picks up the saved values on the next navigation.
    """
    currency = await _saved(page, CURRENCY_STORAGE_KEY)
    set_currency(currency if isinstance(currency, str) else DEFAULT_CURRENCY)

    threshold = await _saved(page, ALERT_THRESHOLD_STORAGE_KEY)
    set_alert_threshold(DEFAULT_ALERT_THRESHOLD if threshold is None else threshold)

    set_dark_mode(await _saved(page, DARK_MODE_STORAGE_KEY))


async def main(page: ft.Page):
    page.title = "Envelo"
    await _restore_preferences(page)
    apply_theme(page)

    async def route_change(e=None):
        page.views.clear()
        for route in stack_for_route(page.route):
            page.views.append(await build_view(route, page))
        page.update()

    async def view_pop(e):
        if e.view is not None:
            page.views.remove(e.view)
            top_view = page.views[-1]
            await page.push_route(top_view.route)

    # Flet has no CSS media queries: views are built for one breakpoint band
    # (mobile / compact / desktop), so switching between the sidebar and the
    # bottom bar means rebuilding them. Only a band change triggers that -
    # resizing within a band leaves the tree alone.
    band = layout_band(page.width)

    async def resize(e: ft.PageResizeEvent):
        nonlocal band
        new_band = layout_band(e.width)
        if new_band != band:
            band = new_band
            await route_change()

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    page.on_resize = resize
    await route_change()


if __name__ == "__main__":
    ft.run(main, assets_dir=ASSETS_DIR)
