from routing import VIEW_BUILDERS, stack_for_route


def test_stack_for_route_home():
    assert stack_for_route("/") == ["/"]


def test_stack_for_route_accounts_pops_back_to_settings():
    assert stack_for_route("/accounts") == ["/", "/settings", "/accounts"]


def test_stack_for_route_unknown_falls_back_to_home():
    assert stack_for_route("/does-not-exist") == ["/"]


def test_all_demo_routes_registered():
    expected = {
        "/login",
        "/dashboard",
        "/envelopes",
        "/envelopes/detail",
        "/transactions",
        "/import",
        "/statements",
        "/rules",
        "/payees",
        "/accounts",
        "/alerts",
        "/forecast",
        "/settings",
    }
    assert expected <= set(VIEW_BUILDERS)


def test_stack_for_route_top_level_screen_sits_on_home():
    assert stack_for_route("/dashboard") == ["/", "/dashboard"]


def test_stack_for_route_envelope_detail_pops_back_to_list():
    assert stack_for_route("/envelopes/detail") == ["/", "/envelopes", "/envelopes/detail"]


def test_stack_for_route_import_pops_back_to_transactions():
    assert stack_for_route("/import") == ["/", "/transactions", "/import"]


def test_stack_for_route_manage_screens_pop_back_to_settings():
    for route in ("/payees", "/rules", "/accounts"):
        assert stack_for_route(route) == ["/", "/settings", route]
