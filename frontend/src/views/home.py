import flet as ft
from api_client import get_health


async def build_home_view(page: ft.Page) -> ft.View:
    connected = await get_health()

    return ft.View(
        route="/",
        controls=[
            ft.AppBar(title="Envelo"),
            ft.Text(
                "API Gateway: connected" if connected else "API Gateway: unreachable",
                color=ft.Colors.GREEN if connected else ft.Colors.RED,
            ),
            ft.Button("Accounts", on_click=lambda e: page.navigate("/accounts")),
        ],
    )
