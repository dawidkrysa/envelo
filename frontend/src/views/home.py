"""Home ("/") - the app's entry point, and the base of every view stack.

It shows the Login screen. A signed-in session never lands here:
`main.route_change` forwards "/" to the dashboard, so popping back to the
bottom of the stack does not appear to sign anyone out."""

import flet as ft

from views.login import build_login_view


async def build_home_view(page: ft.Page) -> ft.View:
    view = await build_login_view(page)
    view.route = "/"
    return view
