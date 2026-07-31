"""Bar charts - Envelope detail's "Assigned per month" history and Forecast's
assigned-vs-projected comparison. No charting library: the design itself
computes plain pixel-height bars, so this mirrors that directly."""

from dataclasses import dataclass

import flet as ft

from theme import Palette, text_style


@dataclass(frozen=True)
class HistoryBar:
    label: str
    amount_label: str
    height_px: float
    color: str


def history_bar_chart(p: Palette, bars: list[HistoryBar], *, chart_height: float = 104) -> ft.Row:
    columns = []
    for b in bars:
        columns.append(
            ft.Column(
                [
                    ft.Text(b.amount_label, style=text_style(10.5, 500, p.ink3)),
                    ft.Container(height=b.height_px, bgcolor=b.color, border_radius=ft.BorderRadius(5, 5, 0, 0), width=999),
                    ft.Text(b.label, style=text_style(10.5, 400, p.ink3, letter_spacing=0.3)),
                ],
                spacing=7,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            )
        )
    return ft.Row(columns, spacing=10, alignment=ft.MainAxisAlignment.END, vertical_alignment=ft.CrossAxisAlignment.END, height=chart_height)


@dataclass(frozen=True)
class ForecastGroupBar:
    label: str
    amount_label: str
    assigned_height_px: float
    projected_height_px: float
    color: str


def forecast_bar_chart(p: Palette, bars: list[ForecastGroupBar], *, chart_height: float = 96) -> ft.Column:
    columns = []
    for b in bars:
        columns.append(
            ft.Column(
                [
                    ft.Text(b.amount_label, style=text_style(10.5, 500, p.ink3)),
                    ft.Row(
                        [
                            ft.Container(height=b.assigned_height_px, bgcolor=p.sf3, border_radius=ft.BorderRadius(4, 4, 0, 0), expand=True),
                            ft.Container(height=b.projected_height_px, bgcolor=b.color, border_radius=ft.BorderRadius(4, 4, 0, 0), expand=True),
                        ],
                        spacing=3,
                        alignment=ft.MainAxisAlignment.END,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                        height=chart_height,
                    ),
                    ft.Text(b.label, style=text_style(10.5, 400, p.ink3), text_align=ft.TextAlign.CENTER),
                ],
                spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            )
        )
    legend = ft.Row(
        [
            ft.Row([ft.Container(width=9, height=9, bgcolor=p.sf3, border_radius=2), ft.Text("Assigned", style=text_style(11.5, 400, p.ink3))], spacing=6),
            ft.Row([ft.Container(width=9, height=9, bgcolor=p.ok, border_radius=2), ft.Text("Projected by the 31st", style=text_style(11.5, 400, p.ink3))], spacing=6),
        ],
        spacing=16,
    )
    return ft.Column(
        [
            ft.Row(columns, spacing=14, vertical_alignment=ft.CrossAxisAlignment.END),
            legend,
        ],
        spacing=14,
    )
