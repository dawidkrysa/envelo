"""Toggle switch - Settings' "Appearance" light/dark row."""

import flet as ft

from theme import Palette


def toggle_switch(p: Palette, value: bool, on_change=None) -> ft.Switch:
    return ft.Switch(
        value=value,
        on_change=on_change,
        active_color=p.sf,
        active_track_color=p.ok,
        inactive_thumb_color=p.sf,
        inactive_track_color=p.sf3,
    )
