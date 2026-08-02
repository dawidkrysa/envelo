"""Money formatting across the currency registry.

The non-breaking space PLN groups thousands with is written as `\\u00a0` in every
expectation below rather than pasted literally: it is indistinguishable from a
plain space in an editor, and a test that fails on an invisible character is
close to undebuggable.
"""

from currency import (
    CURRENCIES,
    DEFAULT_CURRENCY,
    current_currency,
    format_amount_bare,
    format_money,
    format_short,
    set_currency,
    symbol,
)


def test_default_currency_is_pln():
    assert current_currency() == DEFAULT_CURRENCY == "pln"
    assert format_money(1234.56) == "1 234,56 zł"


def test_negative_uses_minus_sign_not_hyphen():
    # U+2212, digit-width, so columns of amounts stay aligned.
    assert format_money(-86.42) == "−86,42 zł"


def test_suffix_currency_puts_glyph_after_the_amount():
    set_currency("eur-eu")
    assert format_money(1234.56) == "1.234,56 €"


def test_prefix_currency_puts_glyph_before_the_amount():
    set_currency("usd")
    assert format_money(1234.56) == "$1,234.56"


def test_prefix_currency_keeps_the_sign_outside_the_glyph():
    """Regression: an earlier version built the amount (sign included) first and
    then prepended the glyph, producing `$−86.42`."""
    set_currency("gbp")
    assert format_money(-86.42) == "−£86.42"


def test_separators_are_swapped_not_chained():
    """Regression: `1,234.56` -> replace `,`->`.` -> replace `.`->`,` collapses
    to `1,234,56`. Only shows up when one separator is the other's counterpart,
    which is exactly the EU format."""
    set_currency("eur-eu")
    assert format_amount_bare(1234.56) == "1.234,56"


def test_format_short_drops_decimals_and_the_glyph():
    assert format_short(1234) == "1 234"
    assert format_short(1234.56) == "1 235"


def test_format_money_can_drop_decimals_but_keeps_the_glyph():
    assert format_money(520, decimals=0) == "520 zł"


def test_format_amount_bare_has_no_glyph():
    """What editable `ft.TextField` values are built from - the glyph is a
    separate pinned suffix there."""
    assert format_amount_bare(1234.56) == "1 234,56"
    assert symbol() not in format_amount_bare(1234.56)


def test_unknown_code_falls_back_to_the_default():
    """A code can come from `page.shared_preferences` and so may predate a change
    to the registry - it must not brick startup."""
    set_currency("klingon-darsek")
    assert current_currency() == DEFAULT_CURRENCY


def test_every_registry_entry_is_keyed_by_its_own_code():
    """`current_currency()` returns the key and that is what gets persisted, so a
    stored value must always look back up."""
    assert all(code == cf.code for code, cf in CURRENCIES.items())


def test_every_label_shows_that_currencys_actual_format():
    """The Settings dropdown advertises each option with a sample of its own
    format; a label that disagrees with the separators is a lie users can see."""
    for code, cf in CURRENCIES.items():
        set_currency(code)
        assert cf.label.endswith(format_money(1234.56)), cf.label
