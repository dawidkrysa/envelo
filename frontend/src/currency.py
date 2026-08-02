"""Currency registry and money formatting for every amount shown in the app.

`docs/brandbook.md` defines the money format; this module generalises it so the
Settings screen can switch between locales at runtime. PLN is the default.

The selected currency is **module-level state**, not per-`ft.Page`: `format_money`
is called from ~25 places that have no `page` in scope, and threading one through
all of them for a setting nothing else can change would be a large diff for no
benefit today. The cost is that under `flet run` as a web server every browser
session shares one process, so one session's choice would affect another. Envelo
is single-user today (the backend hardcodes `SEED_USER_ID`), so this is fine -
revisit it when real auth lands and sessions stop being interchangeable.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CurrencyFormat:
    """One locale's money format: which glyph, which side, which separators."""

    code: str
    """Registry key, e.g. `"pln"` - what `current_currency()` returns and what is
    persisted to `page.shared_preferences`. Always equal to this entry's key in
    `CURRENCIES`, so a stored value can always be looked back up."""

    symbol: str
    """Currency glyph, e.g. `"zł"`."""

    suffix: bool
    """`True` puts the glyph after the amount (`1 234,56 zł`), `False` before
    it (`$1,234.56`)."""

    group_sep: str
    """Thousands separator. PLN uses a non-breaking space (` `) rather than a
    plain one so the amount never wraps mid-number."""

    decimal_sep: str
    """Decimal separator."""

    label: str
    """Settings dropdown option text, including a sample of this very format -
    keep it in sync with what the separators above actually produce."""


CURRENCIES: dict[str, CurrencyFormat] = {
    "pln": CurrencyFormat(
        code="pln", symbol="zł", suffix=True, group_sep=" ", decimal_sep=",", label="Złoty — 1 234,56 zł"
    ),
    "eur-eu": CurrencyFormat(
        code="eur-eu", symbol="€", suffix=True, group_sep=".", decimal_sep=",", label="Euro (EU) — 1.234,56 €"
    ),
    "eur-us": CurrencyFormat(
        code="eur-us", symbol="€", suffix=False, group_sep=",", decimal_sep=".", label="Euro (US) — €1,234.56"
    ),
    "usd": CurrencyFormat(
        code="usd", symbol="$", suffix=False, group_sep=",", decimal_sep=".", label="US Dollar — $1,234.56"
    ),
    "gbp": CurrencyFormat(
        code="gbp", symbol="£", suffix=False, group_sep=",", decimal_sep=".", label="British Pound — £1,234.56"
    ),
}

DEFAULT_CURRENCY = "pln"

CURRENCY_STORAGE_KEY = "envelo.currency"
"""`page.shared_preferences` key the Settings screen writes and `main.py` reads
back at startup. Named here so the two sides cannot drift apart."""

# U+2212 MINUS SIGN, not an ASCII hyphen: it is as wide as a digit, so columns of
# amounts stay aligned. Same choice the design import made.
MINUS = "−"

_current = DEFAULT_CURRENCY


def current_currency() -> str:
    """Registry key of the currency every formatter below is using right now."""
    return _current


def set_currency(code: str) -> None:
    """Switch the app-wide currency. An unknown code falls back to the default
    rather than raising - the value can come from `page.shared_preferences`, so
    it may predate a change to `CURRENCIES` and must not brick startup."""
    global _current
    _current = code if code in CURRENCIES else DEFAULT_CURRENCY


def symbol() -> str:
    """Current currency's glyph, for controls that render it separately from the
    amount (e.g. the ledger's inline assign field)."""
    return CURRENCIES[_current].symbol


def _grouped(value: float, decimals: int = 2) -> str:
    """`1234.56` -> `1 234,56` - an unsigned amount with the current currency's
    separators applied.

    Python's `,` format spec always emits `,` for groups and `.` for decimals, so
    both have to be swapped. That is done through a `§` sentinel because a naive
    two-step replace destroys any format where one separator is the other's
    counterpart: `1,234.56` -> (`,`->`.`) `1.234.56` -> (`.`->`,`) `1,234,56`.
    """
    cf = CURRENCIES[_current]
    body = f"{value:,.{decimals}f}"
    return body.replace(",", "§").replace(".", cf.decimal_sep).replace("§", cf.group_sep)


def format_money(n: float, *, decimals: int = 2) -> str:
    """`1 234,56 zł` - a full amount with its currency glyph.

    The sign always leads (`−$86,42`, never `$−86,42`), which is why the glyph is
    attached here rather than inside `format_amount_bare`.
    """
    cf = CURRENCIES[_current]
    sign = MINUS if n < 0 else ""
    body = _grouped(abs(n), decimals)
    return f"{sign}{body} {cf.symbol}" if cf.suffix else f"{sign}{cf.symbol}{body}"


def format_short(n: float) -> str:
    """`1 234` - whole units, grouped, **no currency glyph**. Used for bar-chart
    labels and anywhere the caller appends the symbol itself."""
    sign = MINUS if n < 0 else ""
    return f"{sign}{_grouped(abs(n), decimals=0)}"


def format_amount_bare(n: float) -> str:
    """`1 234,56` - the number alone, for editable `ft.TextField` values where the
    glyph is rendered as a separate pinned suffix."""
    sign = MINUS if n < 0 else ""
    return f"{sign}{_grouped(abs(n))}"
