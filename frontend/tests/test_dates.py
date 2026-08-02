"""Current-month arithmetic. Every case pins `today` explicitly - these helpers
exist because the screens used to show a frozen `DAYS_LEFT = 9`, so a test that
depended on the real clock would defeat the point."""

from datetime import date

from dates import (
    days_elapsed_in_month,
    days_in_month,
    days_left_in_month,
    days_left_label,
    month_elapsed_fraction,
    month_label,
)


def test_days_left_counts_the_rest_of_the_month():
    # The reported bug: on 2 August the app still said "9 days left".
    assert days_left_in_month(date(2026, 8, 2)) == 29


def test_days_left_is_zero_on_the_last_day():
    assert days_left_in_month(date(2026, 8, 31)) == 0


def test_days_left_handles_a_short_month():
    assert days_left_in_month(date(2026, 2, 1)) == 27
    assert days_in_month(date(2026, 2, 1)) == 28


def test_days_left_label_is_singular_only_at_one():
    assert days_left_label(date(2026, 8, 30)) == "1 day left"
    assert days_left_label(date(2026, 8, 29)) == "2 days left"
    assert days_left_label(date(2026, 8, 31)) == "0 days left"


def test_days_elapsed_excludes_today():
    assert days_elapsed_in_month(date(2026, 8, 1)) == 0
    assert days_elapsed_in_month(date(2026, 8, 2)) == 1


def test_month_elapsed_fraction_is_never_zero():
    """Forecast divides month-to-date spending by this, and
    `days_elapsed_in_month()` is 0 on the 1st - so the projection would blow up
    once a month if that were used as the denominator."""
    assert month_elapsed_fraction(date(2026, 8, 1)) > 0
    assert month_elapsed_fraction(date(2026, 8, 31)) == 1.0


def test_month_label():
    assert month_label(date(2026, 8, 2)) == "August 2026"
