from mock_data import (
    envelope_by_id,
    envelope_state,
)

# Money formatting moved to `currency.py` - see tests/test_currency.py.


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
