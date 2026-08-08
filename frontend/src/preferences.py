"""Client-side user preferences that have no home on the backend.

There is no user-settings table in the API (the gateway hardcodes a single
owner), so anything the user chooses about *how the app behaves* is stored in
`page.shared_preferences` and restored by `main.py` before the first render.

Currency deliberately stays in `currency.py` rather than moving here: its stored
value and its formatters are the same concern, and splitting them would leave
`format_money` reaching into another module for the one thing it needs. This
module is for preferences that no single module owns - the alert threshold is
read by `envelope_state()`, written by Settings, and stated in words on Alerts.

Same module-level-state tradeoff as `currency.py`, for the same reason and with
the same caveat: `envelope_state()` is called from a dozen places with no `page`
in scope, so threading one through them all would be a large diff for a
single-user app. Under `flet run` as a web server every browser session shares
one process, so one session's threshold would apply to another. Revisit when real
auth lands and sessions stop being interchangeable.
"""

DEFAULT_ALERT_THRESHOLD = 80
"""Percent of an envelope that has to be gone before it counts as a warning."""

MIN_ALERT_THRESHOLD = 50
MAX_ALERT_THRESHOLD = 100
"""The range Settings' slider offers. Enforced here as well, because the value
can also arrive from `page.shared_preferences` - written by an older build, or
by hand - and a threshold of 0 would paint every envelope amber forever."""

ALERT_THRESHOLD_STORAGE_KEY = "envelo.alert_threshold"
"""`page.shared_preferences` key the Settings screen writes and `main.py` reads
back at startup. Named here so the two sides cannot drift apart."""

DARK_MODE_STORAGE_KEY = "envelo.dark_mode"
"""`page.shared_preferences` key for the appearance toggle. Appearance was the
one Settings control that looked like it worked and did not survive a reload:
`theme.apply_theme()` set light unconditionally at startup, so a dark-mode user
was handed a white screen every time they opened the app."""

_alert_threshold = DEFAULT_ALERT_THRESHOLD

_dark_mode = False


def alert_threshold() -> int:
    """The warning threshold as a percentage - what Settings shows on its slider
    and what Alerts states in words."""
    return _alert_threshold


def alert_fraction() -> float:
    """The same threshold as a `0..1` fraction, for comparing against
    `spent / funded` in `envelope_state()`."""
    return _alert_threshold / 100


def dark_mode() -> bool:
    """Whether the app should paint dark. Read by `theme.apply_theme()` at
    startup and by the Settings toggle."""
    return _dark_mode


def set_dark_mode(value) -> bool:
    """Anything unreadable means light, for the same reason as the threshold
    above: the value comes out of shared preferences and may be missing or
    stale, and neither is a reason to refuse to start."""
    global _dark_mode
    _dark_mode = value is True
    return _dark_mode


def set_alert_threshold(value) -> int:
    """Set the threshold, clamped into range; returns what was actually stored.

    Anything unreadable falls back to the default rather than raising: the value
    can come out of shared preferences, so it may be missing, stale or garbage,
    and none of that is a reason to refuse to start.
    """
    global _alert_threshold
    try:
        parsed = int(round(float(value)))
    except (TypeError, ValueError):
        parsed = DEFAULT_ALERT_THRESHOLD
    _alert_threshold = max(MIN_ALERT_THRESHOLD, min(MAX_ALERT_THRESHOLD, parsed))
    return _alert_threshold
