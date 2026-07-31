"""Login - `isLogin` in the design: sign-in / create-account card. Any input
"signs in" straight to the dashboard - there is no real auth here.

Pre-auth, so this sits outside the app shell: no nav rail, and not listed as
a destination in it.
"""

import flet as ft

from components.button import link_button, primary_button
from components.input_field import text_input
from components.nav_rail import brand_mark
from theme import RADIUS_CARD_LG, palette, text_style
from views.common import page_band, standalone_shell


async def build_login_view(page: ft.Page) -> ft.View:
    p = palette(page)
    band = page_band(page)
    state = {"mode": "login"}

    copy = {
        "login": {"title": "Welcome back", "sub": "Sign in to pick up where you left off.", "cta": "Sign in", "alt": "Create an account instead"},
        "register": {
            "title": "Create your account",
            "sub": "One account, all your envelopes. Nothing is shared with anyone.",
            "cta": "Create account",
            "alt": "I already have an account",
        },
    }

    title = ft.Text(copy["login"]["title"], style=text_style(20, 600, p.ink))
    subtitle = ft.Text(copy["login"]["sub"], style=text_style(13, 400, p.ink3))
    cta_text = ft.Text(copy["login"]["cta"], style=text_style(13.5, 600, p.on_brand))
    alt_link = ft.Text(copy["login"]["alt"], style=text_style(12.5, 500, p.link))

    def toggle_mode(e: ft.ControlEvent) -> None:
        state["mode"] = "register" if state["mode"] == "login" else "login"
        c = copy[state["mode"]]
        title.value, subtitle.value, cta_text.value, alt_link.value = c["title"], c["sub"], c["cta"], c["alt"]
        page.update()

    def submit(e: ft.ControlEvent) -> None:
        # Register lands on the first-run setup checklist (add an account,
        # import, budget) rather than a dashboard with nothing in it yet;
        # sign-in returns straight to a budget that already has data.
        page.navigate("/dashboard" if state["mode"] == "login" else "/first-run")

    card = ft.Container(
        content=ft.Column(
            [
                ft.Column([title, subtitle], spacing=5, tight=True),
                text_input(p, placeholder="you@example.com", height=42, expand=True),
                text_input(p, placeholder="••••••••••", height=42, password=True, expand=True),
                primary_button(p, cta_text, submit, expand=True, height=44),
                link_button(p, alt_link, toggle_mode),
            ],
            spacing=17,
            # Explicit stretch rather than relying on TextField/Container's
            # incidental "fill when unconstrained" default - guarantees the
            # email/password fields and the Sign in/Create account button
            # always span the same width as the card, even if a future
            # tweak (an intrinsic-width child, a Row wrapper, ...) would
            # otherwise break that coincidence.
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
        width=392,
        bgcolor=p.sf,
        border=ft.Border.all(1, p.line),
        border_radius=RADIUS_CARD_LG,
        padding=26,
    )

    # `expand=True` would throw here - the content column this sits in is
    # scrollable (unbounded height), and a flex child needs a bounded main
    # axis. A fixed min-height (matching the design's own `loginMinH`) centers
    # the card without relying on flex.
    #
    # The brand mark + card group is wrapped in a Row (not just a
    # Container(alignment=center)): nothing else in this screen's body has a
    # flex/expand descendant to force the ancestor Columns up to
    # standalone_shell's content column to full width, so a plain Container
    # here just shrinks to the card's own width and sits at the body
    # column's left edge instead of centering - a Row defaults to
    # mainAxisSize.max and claims the full width on its own, which is what
    # actually makes Alignment.CENTER have something to center within.
    body: list[ft.Control] = [
        ft.Container(
            content=ft.Row(
                [
                    ft.Column(
                        # Larger than the sidebar's compact lockup: standing
                        # alone above a 392px-wide card, the nav-sized mark
                        # read as an afterthought rather than a hero brand
                        # moment.
                        [brand_mark(p, scale=1.5), card],
                        spacing=26,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            alignment=ft.Alignment.CENTER,
            height=740 if band == "mobile" else 640,
            padding=ft.Padding.symmetric(vertical=40),
        )
    ]

    return standalone_shell(page, "/login", body)
