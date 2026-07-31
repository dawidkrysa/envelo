from pathlib import Path

import flet as ft

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


async def main(page: ft.Page):
    page.title = "Envelo"
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
