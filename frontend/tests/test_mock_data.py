from mock_data import (
    envelope_by_id,
    envelope_state,
    format_money,
    format_short,
)


def test_format_money_groups_thousands_eu_style():
    assert format_money(1234.56) == "1.234,56 €"


def test_format_money_negative_uses_minus_sign():
    assert format_money(-86.42) == "−86,42 €"


def test_format_short_groups_thousands_without_decimals():
    assert format_short(1234) == "1.234"


def test_envelope_states_cover_all_three_design_states():
    from mock_data import all_envelopes

    states = {envelope_state(e) for e in all_envelopes()}
    assert states == {"ok", "warn", "over"}


def test_envelope_state_thresholds():
    # groceries: 442.15 / 520 = 85% -> warn
    assert envelope_state(envelope_by_id("groceries")) == "warn"
    # gifts: spent 82.5 > assigned 60 -> over
    assert envelope_state(envelope_by_id("gifts")) == "over"
    # rent: spent == assigned exactly -> ok ("fully spent as planned", not warn)
    assert envelope_state(envelope_by_id("rent")) == "ok"


def test_envelope_by_id_unknown_returns_none():
    assert envelope_by_id("does-not-exist") is None
