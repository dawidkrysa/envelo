import pytest

import currency


@pytest.fixture(autouse=True)
def _reset_currency():
    """The selected currency is module-level state in `currency.py` (deliberately
    - see that module's docstring), so a test that calls `set_currency()` would
    otherwise leak its choice into every test that runs after it and change what
    `format_money()` returns there. Restore the default after each test."""
    yield
    currency.set_currency(currency.DEFAULT_CURRENCY)


@pytest.fixture(autouse=True)
def _stub_nav_category_groups(monkeypatch):
    """`views.common.category_group_nav()` (called by every `app_shell()`,
    i.e. every routed view) hits four API endpoints to compute the
    sidebar's "Category groups" list. Stub them to empty by default so view
    tests stay hermetic and fast - a test that cares about the sidebar's
    content can override any of these itself with its own `monkeypatch`."""

    async def _empty(*args, **kwargs):
        return []

    async def _empty_map(*args, **kwargs):
        return {}

    monkeypatch.setattr("views.common.get_category_groups", _empty)
    monkeypatch.setattr("views.common.get_envelopes", _empty)
    monkeypatch.setattr("views.common.get_envelope_allocations", _empty)
    monkeypatch.setattr("views.common.get_spent_by_envelope", _empty_map)
