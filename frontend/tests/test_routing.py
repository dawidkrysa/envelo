from routing import stack_for_route


def test_stack_for_route_home():
    assert stack_for_route("/") == ["/"]


def test_stack_for_route_accounts_includes_home_underneath():
    assert stack_for_route("/accounts") == ["/", "/accounts"]


def test_stack_for_route_unknown_falls_back_to_home():
    assert stack_for_route("/does-not-exist") == ["/"]
