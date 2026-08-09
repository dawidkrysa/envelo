"""Current-month date arithmetic for the budget period every screen renders.

Its own module rather than a section of `utils.py` because `utils.py` imports
`mock_data`, and `mock_data.envelope_view()` needs `days_left_label()` - putting
these helpers in `utils.py` would make that a circular import. Nothing here
imports from the repo, so both sides can use it freely.

Every helper takes an optional `today` so callers (and tests) can pin the date;
it defaults to the real one.
"""

import calendar
from datetime import date


def _today(today: date | None = None) -> date:
    return today or date.today()


def days_in_month(today: date | None = None) -> int:
    """Length of `today`'s month, e.g. 31 in August."""
    d = _today(today)
    return calendar.monthrange(d.year, d.month)[1]


def days_left_in_month(today: date | None = None) -> int:
    """Days remaining after `today`, e.g. 29 on 2 August.

    A real date subtraction, not `last_day.day - today.day`: the latter only
    happens to agree while both dates sit in the same month, and silently
    returns 0 for any other range (see `utils.range_to_dates("last3")`, whose
    end date is today).
    """
    d = _today(today)
    last_day = calendar.monthrange(d.year, d.month)[1]
    return (date(d.year, d.month, last_day) - d).days


def days_elapsed_in_month(today: date | None = None) -> int:
    """Days already finished this month - `today` itself is still running, so
    the 2nd counts as 1 day elapsed. Pairs with `days_in_month()` to give the
    month-elapsed fraction the Forecast screen paces spending against."""
    d = _today(today)
    return d.day - 1


def month_elapsed_fraction(today: date | None = None) -> float:
    """How much of the month is behind us, as a `0 < f <= 1` fraction - the
    denominator for pacing a month-to-date total up to a month-end projection.

    Counts `today` itself as elapsed (`day / days_in_month`) rather than reusing
    `days_elapsed_in_month()`: that one returns 0 on the 1st, and every caller
    divides by this, so it would be a division by zero exactly once a month.
    """
    d = _today(today)
    return d.day / days_in_month(d)


def month_label(today: date | None = None) -> str:
    """`August 2026` - the budget period shown in page-header eyebrows."""
    d = _today(today)
    return d.strftime("%B %Y")


def month_end_label(today: date | None = None) -> str:
    """`31 August` - the day a month-end projection is aimed at.

    The Forecast chart's legend used to read "Projected by the 31st" whatever the
    month, which is a date February does not have.
    """
    d = _today(today)
    return f"{days_in_month(d)} {d.strftime('%B')}"


def days_left_label(today: date | None = None) -> str:
    """`29 days left` / `1 day left` - the countdown in headers and in an
    envelope's warning state label."""
    days = days_left_in_month(today)
    return f"{days} day left" if days == 1 else f"{days} days left"
