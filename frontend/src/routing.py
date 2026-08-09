from collections.abc import Awaitable, Callable

import flet as ft

from views.accounts import build_accounts_view
from views.alerts import build_alerts_view
from views.dashboard import build_dashboard_view
from views.envelope_detail import build_envelope_detail_view
from views.envelopes import build_envelopes_view
from views.first_run import build_first_run_view
from views.forecast import build_forecast_view
from views.home import build_home_view
from views.login import build_login_view
from views.payees import build_payees_view
from views.rules import build_rules_view
from views.settings import build_settings_view
from views.statement_import import build_import_view
from views.transactions import build_transactions_view

ViewBuilder = Callable[[ft.Page], Awaitable[ft.View]]

VIEW_BUILDERS: dict[str, ViewBuilder] = {
    "/": build_home_view,
    "/login": build_login_view,
    "/dashboard": build_dashboard_view,
    "/envelopes": build_envelopes_view,
    "/envelopes/detail": build_envelope_detail_view,
    "/transactions": build_transactions_view,
    "/forecast": build_forecast_view,
    "/alerts": build_alerts_view,
    "/import": build_import_view,
    "/rules": build_rules_view,
    "/accounts": build_accounts_view,
    "/payees": build_payees_view,
    "/settings": build_settings_view,
    "/first-run": build_first_run_view,
}

# Routes whose back gesture should land somewhere other than "/". Any route
# not listed here sits directly on top of the home view.
ROUTE_PARENTS: dict[str, str] = {
    "/envelopes/detail": "/envelopes",
    "/import": "/transactions",
    "/rules": "/settings",
    "/payees": "/settings",
    "/accounts": "/settings",
    "/alerts": "/dashboard",
}


def stack_for_route(route: str) -> list[str]:
    """Ordered list of routes that should be on the view stack for `route`.

    "/" is always the base of the stack; a route with an entry in
    ROUTE_PARENTS gets its parent chain in between, so popping a detail
    view lands on its list rather than all the way back home.
    """
    if route not in VIEW_BUILDERS or route == "/":
        return ["/"]
    stack = [route]
    while route in ROUTE_PARENTS:
        route = ROUTE_PARENTS[route]
        stack.append(route)
    stack.append("/")
    return list(reversed(stack))


async def build_view(route: str, page: ft.Page) -> ft.View:
    return await VIEW_BUILDERS[route](page)
