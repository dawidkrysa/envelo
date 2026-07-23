import flet as ft


async def build_accounts_view(page: ft.Page) -> ft.View:
    return ft.View(
        route="/accounts",
        controls=[
            ft.AppBar(title="Accounts"),
            ft.Text("Accounts screen placeholder - budget data lands in a later issue."),
        ],
    )
