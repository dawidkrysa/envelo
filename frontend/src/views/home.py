"""Home ("/") - the app's entry point. This static prototype has no real
auth, so "/" simply shows the Login screen; "Sign in" moves on to the
Dashboard."""

import flet as ft

from views.login import build_login_view


async def build_home_view(page: ft.Page) -> ft.View:
    view = await build_login_view(page)
    view.route = "/"
    return view
