from collections.abc import Awaitable, Callable

import flet as ft
from views.accounts import build_accounts_view
from views.home import build_home_view

ViewBuilder = Callable[[ft.Page], Awaitable[ft.View]]

VIEW_BUILDERS: dict[str, ViewBuilder] = {
    "/": build_home_view,
    "/accounts": build_accounts_view,
}


def stack_for_route(route: str) -> list[str]:
    """Ordered list of routes that should be on the view stack for `route`.

    "/" is always the base of the stack; any other known route is pushed on
    top of it.
    """
    if route in VIEW_BUILDERS and route != "/":
        return ["/", route]
    return ["/"]


async def build_view(route: str, page: ft.Page) -> ft.View:
    return await VIEW_BUILDERS[route](page)
