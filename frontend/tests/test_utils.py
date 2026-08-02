"""`utils.parse_amount` - what a user's keystrokes become before they reach the API.

The bugs this covers were all silent: a mistyped separator used to be stored as a
plausible-but-wrong number, and `0` was dropped entirely. Every case here is a
value someone can actually type into the ledger's inline amount field.
"""

import pytest

from currency import format_amount_bare, set_currency
from utils import parse_amount


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Comma decimals - what the EU/PLN formatters render.
        ("42,50", "42.50"),
        ("42,5", "42.5"),
        ("1.234,56", "1234.56"),
        # Dot decimals - what a numeric keypad produces. Used to be read as a
        # thousands separator, silently storing 12050 instead of 120.50.
        ("120.50", "120.50"),
        ("1,234.56", "1234.56"),
        # Plain, ungrouped - the most common way to type an amount.
        ("1234", "1234"),
        ("1500,00", "1500.00"),
        # Grouping only.
        ("1.500", "1500"),
        ("12,345", "12345"),
        ("1.234.567", "1234567"),
    ],
)
def test_parses_both_decimal_conventions(raw, expected):
    assert parse_amount(raw) == expected


def test_zero_is_a_valid_amount():
    """Un-assigning an envelope means typing 0. This used to return None, so the
    edit was silently discarded - the core of "changing Assigned does nothing"."""
    assert parse_amount("0") == "0"
    assert parse_amount("0,00") == "0.00"


@pytest.mark.parametrize("raw", ["-86,42", "−86,42"])
def test_accepts_both_minus_signs(raw):
    """`currency.format_amount_bare` writes U+2212 into the field, so a negative
    value has to survive being read straight back out of it."""
    assert parse_amount(raw) == "-86.42"


@pytest.mark.parametrize("raw", ["1 234,56", "1 234,56"])
def test_strips_group_spaces(raw):
    """PLN groups thousands with a non-breaking space, and that is what ends up
    in the text field - blurring an untouched field must not read as malformed."""
    assert parse_amount(raw) == "1234.56"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "abc",
        "12a",
        "-",
        "1,2,3",  # stray separator: must not be read as grouping -> 12.30
        "1,23,456",  # uneven groups
        "1.23.4",
        "1.2345",  # more than two decimals
    ],
)
def test_rejects_malformed_input(raw):
    assert parse_amount(raw) is None


@pytest.mark.parametrize("code", ["pln", "eur-eu", "eur-us", "usd", "gbp"])
@pytest.mark.parametrize("value", [0, 5, 42.5, 1234.56, -86.42, 1234567.89])
def test_round_trips_every_rendered_amount(code, value):
    """The field is filled by `format_amount_bare` and read back by `parse_amount`;
    if the two ever disagree, editing an amount corrupts it. This is the test that
    catches a formatter change breaking the parser."""
    set_currency(code)
    assert parse_amount(format_amount_bare(value)) == f"{value:.2f}"
