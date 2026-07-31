"""Envelo design tokens - Python counterpart of the Claude Design import
(`Envelo.dc.html`, project "Envelo budget app design").

Flat, calm, IBM Plex Sans. Colors below are literal sRGB conversions of the
design's OKLCH custom properties (--brand, --ok, --warn, --over, ...) so hex
values match the source 1:1 rather than approximating with Material roles.
"""

from dataclasses import dataclass
from pathlib import Path

import flet as ft

_ASSETS_DIR = Path(__file__).parent / "assets"

# ---------------------------------------------------------------------------
# Font. IBM Plex Sans ships in 4 weights in the design (400/500/600/700).
# Flutter does not synthesize missing weight files well, so each weight is
# registered as its own family alias. The four TTFs live at the assets root
# (main.py's assets_dir="assets" resolves to frontend/src/assets/):
#   frontend/src/assets/IBMPlexSans-Regular.ttf
#   frontend/src/assets/IBMPlexSans-Medium.ttf
#   frontend/src/assets/IBMPlexSans-SemiBold.ttf
#   frontend/src/assets/IBMPlexSans-Bold.ttf
# Download from https://fonts.google.com/specimen/IBM+Plex+Sans.
FONT_FAMILY = "IBM Plex Sans"
_WEIGHT_FAMILY = {
    400: "IBM Plex Sans",
    500: "IBM Plex Sans Medium",
    600: "IBM Plex Sans SemiBold",
    700: "IBM Plex Sans Bold",
}
_FT_WEIGHT = {
    400: ft.FontWeight.W_400,
    500: ft.FontWeight.W_500,
    600: ft.FontWeight.W_600,
    700: ft.FontWeight.W_700,
}
FONT_FILES = {
    "IBM Plex Sans": "IBMPlexSans-Regular.ttf",
    "IBM Plex Sans Medium": "IBMPlexSans-Medium.ttf",
    "IBM Plex Sans SemiBold": "IBMPlexSans-SemiBold.ttf",
    "IBM Plex Sans Bold": "IBMPlexSans-Bold.ttf",
}
# Only the weights whose TTF is actually present on disk - see apply_theme()
# for why a registered-but-missing font file is worse than no custom font.
AVAILABLE_FONTS = {name: path for name, path in FONT_FILES.items() if (_ASSETS_DIR / path).is_file()}


def text_style(
    size: float,
    weight: int = 400,
    color: str | None = None,
    letter_spacing: float | None = None,
    italic: bool = False,
) -> ft.TextStyle:
    """`font:{weight} {size}px 'IBM Plex Sans'` from the design, as a TextStyle."""
    family = _WEIGHT_FAMILY.get(weight, FONT_FAMILY)
    if family not in AVAILABLE_FONTS:
        family = None  # fall back to the platform default rather than a 404'd family
    return ft.TextStyle(
        size=size,
        weight=_FT_WEIGHT.get(weight, ft.FontWeight.W_400),
        font_family=family,
        color=color,
        letter_spacing=letter_spacing,
        italic=italic,
    )


# ---------------------------------------------------------------------------
# No spacing scale: the design uses many one-off values (13, 17, 22, 26...)
# left as literals at each call site rather than forced onto a scale, per the
# source's "don't approximate" fidelity.

# Corner radii (px) - the handful that repeat across the design.
RADIUS_CARD_LG = 16  # login card, mobile frame
RADIUS_CARD = 14  # stat cards, ledger/table panels, envelope cards
RADIUS_CARD_SM = 13  # compact rows (setup steps, settings rows, rules)
RADIUS_BUTTON = 9  # buttons, inputs, selects
RADIUS_TILE = 8  # nav items, small icon tiles
RADIUS_BADGE = 6
RADIUS_PILL = 999

# Responsive breakpoints (px) matching the design's tablet/desktop nav switch.
BREAKPOINT_MOBILE = 600
BREAKPOINT_DESKTOP = 900  # design's "tablet" frame is 900px wide


def layout_band(width: float | None) -> str:
    """Breakpoint band for a viewport width - "mobile", "tablet" or "desktop".

    Flet reports page.width as None until the first frame is measured; assume
    desktop until then.
    """
    if not width:
        return "desktop"
    if width < BREAKPOINT_MOBILE:
        return "mobile"
    if width < BREAKPOINT_DESKTOP:
        return "tablet"
    return "desktop"


@dataclass(frozen=True)
class Palette:
    """1:1 mirror of the design's CSS custom properties for one color scheme."""

    sf: str  # --sf   surface / cards
    sf2: str  # --sf2  app canvas panel / table header fill
    sf3: str  # --sf3  progress track / hairline row dividers
    canvas: str  # --canvas  page background behind the frame
    ink: str  # --ink   primary text
    ink2: str  # --ink2  secondary text
    ink3: str  # --ink3  tertiary / metadata text
    line: str  # --line   default 1px border
    line2: str  # --line2  stronger border (buttons, focus rest state)
    brand: str  # --brand   primary action fill
    brand_hover: str  # --brandH
    on_brand: str  # --onBrand
    link: str  # --link
    ok: str  # --ok       healthy accent
    ok_ink: str  # --okInk
    ok_fill: str  # --okFill
    ok_border: str  # --okBorder
    warn: str  # --warn
    warn_ink: str  # --warnInk
    warn_fill: str  # --warnFill
    warn_border: str  # --warnBorder
    over: str  # --over     overspent accent
    over_ink: str  # --overInk
    over_fill: str  # --overFill
    over_border: str  # --overBorder
    rule_fill: str  # --ruleFill   "Rule" source badge
    rule_ink: str  # --ruleInk
    ml_fill: str  # --mlFill     "ML" source badge
    ml_ink: str  # --mlInk
    toast: str  # --toast


LIGHT = Palette(
    sf="#FFFFFF",
    sf2="#F6F8F6",
    sf3="#ECF0EE",
    canvas="#EDF1EE",
    ink="#19221D",
    ink2="#46504A",
    ink3="#585F5B",
    line="#DAE0DC",
    line2="#C8D0CB",
    brand="#1D3A2A",
    brand_hover="#0E2B1B",
    on_brand="#FFFFFF",
    link="#2E5740",
    ok="#14874E",
    ok_ink="#00582C",
    ok_fill="#DBF4E3",
    ok_border="#BEE2C9",
    warn="#CD9219",
    warn_ink="#784500",
    warn_fill="#FFF1C8",
    warn_border="#EBCD95",
    over="#C53637",
    over_ink="#A51E24",
    over_fill="#FFE8E4",
    over_border="#FFBDB7",
    rule_fill="#DDF3E5",
    rule_ink="#00502F",
    ml_fill="#EEE6FF",
    ml_ink="#5D408A",
    toast="#17221C",
)

DARK = Palette(
    sf="#1C221E",
    sf2="#252C28",
    sf3="#2F3632",
    canvas="#0D1310",
    ink="#F1F4F2",
    ink2="#D2D7D4",
    ink3="#A4ABA7",
    line="#353D38",
    line2="#505753",
    brand="#5EC386",
    brand_hover="#72D699",
    on_brand="#091A11",
    link="#7BDCA6",
    ok="#4EBE7D",
    ok_ink="#87E2A8",
    ok_fill="#183525",
    ok_border="#2E5740",
    warn="#E7B140",
    warn_ink="#FCCD73",
    warn_fill="#47340D",
    warn_border="#72551F",
    over="#EF6661",
    over_ink="#FFA8A0",
    over_fill="#542523",
    over_border="#8A423D",
    rule_fill="#183525",
    rule_ink="#91DFB2",
    ml_fill="#342A46",
    ml_ink="#CEB6FC",
    toast="#303733",
)


def palette(page: ft.Page) -> Palette:
    """Resolve the active Palette from the page's current theme mode."""
    mode = page.theme_mode
    if mode == ft.ThemeMode.DARK:
        return DARK
    if mode == ft.ThemeMode.LIGHT:
        return LIGHT
    return DARK if page.platform_brightness == ft.Brightness.DARK else LIGHT


def _theme(p: Palette) -> ft.Theme:
    return ft.Theme(
        font_family=FONT_FAMILY,
        color_scheme=ft.ColorScheme(
            primary=p.brand,
            on_primary=p.on_brand,
            secondary=p.ok,
            on_secondary=p.on_brand,
            tertiary=p.link,
            error=p.over,
            on_error=p.on_brand,
            surface=p.sf,
            on_surface=p.ink,
            on_surface_variant=p.ink3,
            outline=p.line2,
            outline_variant=p.line,
        ),
        page_transitions=ft.PageTransitionsTheme(
            android=ft.PageTransitionTheme.NONE,
            ios=ft.PageTransitionTheme.NONE,
            linux=ft.PageTransitionTheme.NONE,
            macos=ft.PageTransitionTheme.NONE,
            windows=ft.PageTransitionTheme.NONE,
        ),
    )


LIGHT_THEME = _theme(LIGHT)
DARK_THEME = _theme(DARK)


def head_padding(band: str) -> ft.Padding:
    """`pageHeadStyle` padding per breakpoint band."""
    if band == "mobile":
        return ft.Padding(left=16, top=18, right=16, bottom=16)
    if band == "tablet":
        return ft.Padding(left=26, top=26, right=26, bottom=20)
    return ft.Padding(left=36, top=30, right=36, bottom=22)


def content_padding(band: str) -> ft.Padding:
    """`padStyle` content padding per breakpoint band.

    `top` matches `head_padding()` so the page header (the first thing in
    every screen's content) isn't flush against the window's top edge.
    """
    top = head_padding(band).top
    if band == "mobile":
        return ft.Padding(left=16, top=top, right=16, bottom=96)
    if band == "tablet":
        return ft.Padding(left=26, top=top, right=26, bottom=40)
    return ft.Padding(left=36, top=top, right=36, bottom=48)


def apply_theme(page: ft.Page) -> None:
    if AVAILABLE_FONTS:
        page.fonts = AVAILABLE_FONTS
    page.theme = LIGHT_THEME
    page.dark_theme = DARK_THEME
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = LIGHT.canvas
