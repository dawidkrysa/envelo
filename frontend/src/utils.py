import calendar
import re
from datetime import date

from mock_data import Envelope, Transaction

# Integer part as typed, grouping separators still in place: either a plain run of
# digits (`1234`, how amounts are usually typed) or uniform three-digit groups
# (`1.234.567`, how they are rendered back). A stray separator (`1,2,3`) matches
# neither and is rejected rather than quietly read as grouping.
_GROUPED_RE = re.compile(r"^-?(\d+|\d{1,3}([.,]\d{3})+)$")

# The normalized result, ready for pydantic's Decimal.
_AMOUNT_RE = re.compile(r"^-?\d+(\.\d{1,2})?$")


def _shift_months(d: date, months: int) -> date:
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def range_to_dates(s: str) -> tuple[date, date]:
    current = date.today()
    year = current.year
    month = current.month
    last_day = calendar.monthrange(year, month)[1]
    match s:
        case "this":
            return (date(year, month, 1), date(year, month, last_day))
        case "last3":
            return (_shift_months(current, -3), current)
        case "year":
            return (_shift_months(current, -12), current)
    return (date(year, month, 1), date(year, month, last_day))


def to_envelope(
    e: dict,
    assigned: float,
    spent: float,
    target: float = 0,
    carried_over: float = 0.0,
    group_name: str = "",
) -> Envelope:
    """An API envelope row -> the display dataclass. `assigned`/`spent` are this
    month's figures; `carried_over` is what was already in the envelope when the
    month began (see `Envelope` and `views/common.BudgetSnapshot`).

    `group_id` comes off the row itself; `group_name` has to be passed because
    resolving it needs the category groups, which this function has no business
    fetching. Callers that already hold them (anything built from a
    `BudgetSnapshot`) pass it; the rest leave it empty, as before.
    """
    return Envelope(
        id=e["id"],
        name=e["name"],
        assigned=assigned,
        spent=spent,
        target=target,
        carried_over=carried_over,
        group_id=e.get("category_group_id", "") or "",
        group_name=group_name,
    )


def to_transaction(
    t: dict,
    payees_by_id: dict[str, str],
    envelopes_by_id: dict[str, str],
    accounts_by_id: dict[str, str] | None = None,
) -> Transaction:
    """An API transaction row -> the display dataclass every transaction
    row/card renders. Ids are resolved against the lookup maps the caller
    already fetched; `accounts_by_id` is optional because the Dashboard's
    compact list does not show the account."""
    accounts_by_id = accounts_by_id or {}
    return Transaction(
        id=t["id"],
        date=t["transaction_date"],
        payee=payees_by_id.get(t["payee_id"], "Unknown"),
        env_id=envelopes_by_id.get(t["envelope_id"], "Uncategorized"),
        account=accounts_by_id.get(t["account_id"], "Unknown"),
        amount=float(t["amount"]),
        source=t["categorization_source"] or "manual",
    )


def spent_by_envelope(transactions: list[dict]) -> dict[str, float]:
    """Money out per envelope. Only negative amounts count: an incoming
    transaction (salary, a refund) is not spending, and letting it net off would
    make an envelope look like it had room it does not have."""
    spent: dict[str, float] = {}
    for t in transactions:
        amount = float(t["amount"])
        spent[t["envelope_id"]] = spent.get(t["envelope_id"], 0.0) + (abs(amount) if amount < 0 else 0.0)
    return spent


def in_month(transactions: list[dict], date_from: date, date_to: date) -> list[dict]:
    """Client-side date filter, for screens that fetch transactions once and need
    both "this month's spending" and "the latest few, whenever they were"."""
    return [t for t in transactions if date_from.isoformat() <= t["transaction_date"][:10] <= date_to.isoformat()]


def resolve_target(allocations: list[dict], envelope_id: str, as_of_month: str, fallback: float) -> float:
    """The target that applies in `as_of_month`: the most recent allocation
    row at or before that month with a non-null `target_amount`, or
    `fallback` (the envelope's own flat `target_amount`, its bootstrap
    default) if no monthly override has ever been set. Editing a target
    only ever writes the *current* month's row going forward, so past
    months keep resolving to whatever was true at the time - there's
    nothing to retroactively rewrite."""
    candidates = sorted(
        (
            a
            for a in allocations
            if a["envelope_id"] == envelope_id and a["month"] <= as_of_month and a.get("target_amount") is not None
        ),
        key=lambda a: a["month"],
    )
    if candidates:
        return float(candidates[-1]["target_amount"])
    return fallback


def parse_amount(raw: str) -> str | None:
    """A typed-in amount -> a numeric string pydantic's `Decimal` can parse
    (`"1.234,56"` -> `"1234.56"`), or `None` if it is empty or malformed.

    Zero is a valid amount: un-assigning an envelope means typing `0`, and
    `EnvelopeAllocation.assigned_amount` is `ge=0`. Callers for whom zero makes
    no sense (assign/move dialogs) guard on the returned value themselves.

    Accepts whatever the formatters in `currency.py` produce, in any locale, so
    a value can be read straight back out of the field it was rendered into -
    including PLN's non-breaking group space and the U+2212 minus sign.

    Which separator is the decimal one is decided by what follows the *last*
    separator: three digits means grouping (`1.500` -> `1500`), anything else
    means decimals (`120.50` -> `120.50`). `1.500` is therefore 1500, never 1.5 -
    genuinely ambiguous without a locale, resolved the way this app's own EU
    formatting writes it. Everything left over is then grouping, and has to be
    uniform three-digit groups or the whole input is rejected: a typo must not
    silently turn into a plausible number, which is exactly how `120.50` used to
    be stored as 12050.
    """
    text = raw.strip().replace("−", "-").replace("\xa0", "").replace(" ", "")
    if not text:
        return None

    # Mark the decimal separator with a sentinel before touching the grouping
    # ones - a straight two-step replace would collapse `1,234.56` into
    # `1,234,56`, since each separator is the other's counterpart.
    last = max(text.rfind("."), text.rfind(","))
    if last != -1 and len(text) - last - 1 != 3:
        text = text[:last] + "§" + text[last + 1 :]

    head, sep, decimals = text.partition("§")
    if not _GROUPED_RE.match(head):
        return None

    text = head.replace(".", "").replace(",", "") + (f".{decimals}" if sep else "")
    if not _AMOUNT_RE.match(text):
        return None
    return text


def parse_date(raw: str) -> str | None:
    text = raw.strip()
    try:
        date.fromisoformat(text)
    except ValueError:
        return None
    return text
