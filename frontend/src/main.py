import flet as ft
from routing import build_view, stack_for_route


async def main(page: ft.Page):
    page.title = "Envelo"

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

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    await route_change()


if __name__ == "__main__":
    ft.run(main)
