from pathlib import Path

import flet as ft

from currency import CURRENCY_STORAGE_KEY, DEFAULT_CURRENCY, set_currency
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


async def _restore_currency(page: ft.Page) -> None:
    """Load the currency saved by the Settings screen before anything renders.

    Every screen formats its amounts at build time, so this has to happen before
    the first `route_change()` or the app would paint once in the default currency
    and only switch on the next navigation. Failures are swallowed: shared
    preferences are unavailable in some hosts (and in tests), and an unreadable
    preference is not a reason to refuse to start.
    """
    try:
        saved = await page.shared_preferences.get(CURRENCY_STORAGE_KEY)
    except Exception:
        saved = None
    set_currency(saved if isinstance(saved, str) else DEFAULT_CURRENCY)


async def main(page: ft.Page):
    page.title = "Envelo"
    await _restore_currency(page)
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
