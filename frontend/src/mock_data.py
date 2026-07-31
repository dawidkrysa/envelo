"""Static mock data for the Envelo prototype - the Python transcription of the
`GROUPS` / `TX` / `ACCOUNTS` / `HISTORY` mock in the Claude Design import.

Purely for visual demonstration: nothing here is persisted, fetched or
validated. `envelope_view()` mirrors the design's `envView()` helper, turning
a raw envelope + a scratch "assigned" draft into the presentation fields
(state color, progress fraction, formatted strings) every envelope
row/card/flow-bar component renders.
"""

from dataclasses import dataclass

from theme import Palette

MONTH = "July 2026"
DAYS_LEFT = 9
POOL = 137.4  # "left to assign" starting pool


def format_money(n: float) -> str:
    """`1.234,56 €` - the design's default EUR (eu) formatting."""
    sign = "−" if n < 0 else ""
    body = f"{abs(n):,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return f"{sign}{body} €"


def format_short(n: float) -> str:
    """`1.234` - whole euros with thousands separator, used in bar-chart labels."""
    return f"{round(n):,}".replace(",", ".")


@dataclass(frozen=True)
class Envelope:
    id: str
    name: str
    assigned: float
    spent: float
    target: float
    group_id: str = ""
    group_name: str = ""


@dataclass(frozen=True)
class EnvelopeGroup:
    id: str
    name: str
    envelopes: list[Envelope]


GROUPS: list[EnvelopeGroup] = [
    EnvelopeGroup("living", "Living costs", [
        Envelope("rent", "Rent", 1150, 1150, 1150),
        Envelope("groceries", "Groceries", 520, 442.15, 520),
        Envelope("utilities", "Utilities", 145, 98.4, 150),
        Envelope("transport", "Transport", 90, 61.2, 90),
    ]),
    EnvelopeGroup("quality", "Quality of life", [
        Envelope("eatingout", "Eating out", 180, 171.6, 180),
        Envelope("subs", "Subscriptions", 46, 46, 46),
        Envelope("hobbies", "Hobbies", 120, 64, 120),
        Envelope("gifts", "Gifts", 60, 82.5, 60),
    ]),
    EnvelopeGroup("future", "Future", [
        Envelope("savings", "Savings", 400, 0, 600),
        Envelope("holiday", "Holiday fund", 150, 0, 1800),
        Envelope("emergency", "Emergency buffer", 200, 0, 3000),
    ]),
]

# Bar color per group in the nav's "category groups" list and forecast chart.
GROUP_BAR_COLOR = {"living": "ok", "quality": "warn", "future": "ok"}

ACCOUNTS: list[str] = ["ING Checking", "ING Savings", "Revolut Card", "Cash"]


@dataclass(frozen=True)
class Transaction:
    id: int
    date: str  # ISO yyyy-mm-dd
    payee: str
    env_id: str
    account: str
    amount: float
    source: str  # "rule" | "ml" | "manual"


TRANSACTIONS: list[Transaction] = [
    Transaction(1, "2026-07-23", "Albert Heijn", "groceries", "ING Checking", -42.18, "rule"),
    Transaction(2, "2026-07-23", "NS Reizigers", "transport", "ING Checking", -8.6, "rule"),
    Transaction(3, "2026-07-22", "Café de Sluis", "eatingout", "Revolut Card", -34.5, "ml"),
    Transaction(4, "2026-07-22", "Bakkerij Vermeer", "groceries", "Cash", -6.75, "manual"),
    Transaction(5, "2026-07-21", "Spotify", "subs", "Revolut Card", -11.99, "rule"),
    Transaction(6, "2026-07-20", "Coolblue", "hobbies", "ING Checking", -64.0, "ml"),
    Transaction(7, "2026-07-19", "Jumbo", "groceries", "ING Checking", -71.3, "rule"),
    Transaction(8, "2026-07-18", "Vattenfall", "utilities", "ING Checking", -62.4, "rule"),
    Transaction(9, "2026-07-17", "De Bijenkorf", "gifts", "Revolut Card", -82.5, "manual"),
    Transaction(10, "2026-07-16", "Shell Zuidas", "transport", "Revolut Card", -52.6, "rule"),
    Transaction(11, "2026-07-15", "Kestrel BV — salary", "income", "ING Checking", 3180.0, "rule"),
    Transaction(12, "2026-07-14", "HelloFresh", "groceries", "ING Checking", -58.9, "ml"),
    Transaction(13, "2026-07-13", "Netflix", "subs", "Revolut Card", -13.99, "rule"),
    Transaction(14, "2026-07-12", "Pathé Arena", "eatingout", "Revolut Card", -27.0, "ml"),
    Transaction(15, "2026-07-11", "Woningcorporatie Ymere", "rent", "ING Checking", -1150.0, "rule"),
    Transaction(16, "2026-07-10", "Albert Heijn", "groceries", "ING Checking", -38.2, "rule"),
]

# Assigned-per-month history (Feb-Jun) for the envelope-detail bar chart.
HISTORY = {"Feb": 480, "Mar": 500, "Apr": 500, "May": 520, "Jun": 540}


def all_envelopes() -> list[Envelope]:
    out = []
    for g in GROUPS:
        for e in g.envelopes:
            out.append(Envelope(e.id, e.name, e.assigned, e.spent, e.target, g.id, g.name))
    return out


def envelope_by_id(env_id: str) -> Envelope | None:
    return next((e for e in all_envelopes() if e.id == env_id), None)


def envelope_name(env_id: str) -> str:
    e = envelope_by_id(env_id)
    return e.name if e else "Income"


def date_short(iso_date: str) -> str:
    _, m, d = iso_date.split("-")
    return f"{d}.{m}"


def envelope_state(e: Envelope) -> str:
    if e.spent > e.assigned:
        return "over"
    if e.assigned > 0 and e.spent < e.assigned and e.spent / e.assigned >= 0.8:
        return "warn"
    return "ok"


@dataclass(frozen=True)
class EnvelopeView:
    """Presentation fields for one envelope, mirroring the design's `envView()`."""

    id: str
    name: str
    group_name: str
    assigned: float
    spent: float
    target: float
    left: float
    state: str
    fill_fraction: float
    pct: int
    assigned_str: str
    spent_str: str
    left_str: str
    bar_label: str
    left_of_label: str
    spent_label: str
    pct_str: str
    target_note: str
    bar_color: str
    left_ink: str
    state_ink: str
    state_label: str
    card_border: str
    pill_fill: str
    pill_ink: str
    pill_label: str
    flow_fill: str


def envelope_view(p: Palette, e: Envelope) -> EnvelopeView:
    left = e.assigned - e.spent
    state = envelope_state(e)
    fraction = min(e.spent / e.assigned, 1.6) if e.assigned > 0 else 0.0
    pct = round((e.spent / e.assigned) * 100) if e.assigned > 0 else 0

    color = {"over": p.over, "warn": p.warn}.get(state, p.ok)
    labels = {
        "ok": "Nothing spent yet" if e.spent == 0 else ("Fully spent as planned" if e.spent == e.assigned else "On track"),
        "warn": f"{DAYS_LEFT} days left",
        "over": f"{format_money(e.spent - e.assigned)} over",
    }
    pill_fill, pill_ink, pill_label = {
        "over": (p.over_fill, p.over_ink, "Over"),
        "warn": (p.warn_fill, p.warn_ink, f"{pct}%"),
    }.get(state, (p.ok_fill, p.ok_ink, "On track"))

    return EnvelopeView(
        id=e.id,
        name=e.name,
        group_name=e.group_name,
        assigned=e.assigned,
        spent=e.spent,
        target=e.target,
        left=left,
        state=state,
        fill_fraction=min(fraction, 1.0),
        pct=pct,
        assigned_str=format_money(e.assigned),
        spent_str=format_money(e.spent),
        left_str=format_money(left),
        bar_label=f"{format_money(e.spent)} of {format_money(e.assigned)}",
        left_of_label=f"left of {format_money(e.assigned)}",
        spent_label=f"{format_money(e.spent)} spent",
        pct_str=f"{pct}%",
        target_note=f"target {format_short(e.target)} €" if e.target else "no target",
        bar_color=color,
        left_ink=p.over_ink if state == "over" else (p.ink2 if left == 0 else p.ink),
        state_ink=p.over_ink if state == "over" else (p.warn_ink if state == "warn" else p.ink3),
        state_label=labels[state],
        card_border=p.over_border if state == "over" else (p.warn_border if state == "warn" else p.line),
        pill_fill=pill_fill,
        pill_ink=pill_ink,
        pill_label=pill_label,
        flow_fill=p.over_fill if state == "over" else (p.warn_fill if state == "warn" else "transparent"),
    )


def attention_envelopes() -> list[Envelope]:
    return [e for e in all_envelopes() if envelope_state(e) != "ok"]


# --- Statements / rules / payees / accounts / settings mock rows -----------

STATEMENTS = [
    {"filename": "ING_checking_2026-07.csv", "format": "CSV", "account": "ING Checking", "date": "24 July 2026", "count": 18},
    {"filename": "revolut_2026-07.ofx", "format": "OFX", "account": "Revolut Card", "date": "22 July 2026", "count": 31},
    {"filename": "ING_checking_2026-06.csv", "format": "CSV", "account": "ING Checking", "date": "2 July 2026", "count": 46},
    {"filename": "ing_savings_q2.940", "format": "MT940", "account": "ING Savings", "date": "1 July 2026", "count": 7},
    {"filename": "revolut_2026-06.ofx", "format": "OFX", "account": "Revolut Card", "date": "30 June 2026", "count": 28},
]

RULES = [
    {"pattern": "Albert Heijn", "envelope": "Groceries", "hits": "46 matches"},
    {"pattern": "Jumbo", "envelope": "Groceries", "hits": "22 matches"},
    {"pattern": "NS Reizigers", "envelope": "Transport", "hits": "31 matches"},
    {"pattern": "Shell", "envelope": "Transport", "hits": "9 matches"},
    {"pattern": "Spotify", "envelope": "Subscriptions", "hits": "12 matches"},
    {"pattern": "Ymere", "envelope": "Rent", "hits": "12 matches"},
]

PAYEES = [
    {"name": "Albert Heijn", "envelope": "Groceries", "count": 46, "total": 1842.55, "last": "23 July 2026"},
    {"name": "Jumbo", "envelope": "Groceries", "count": 22, "total": 918.4, "last": "19 July 2026"},
    {"name": "NS Reizigers", "envelope": "Transport", "count": 31, "total": 264.9, "last": "23 July 2026"},
    {"name": "Café de Sluis", "envelope": "Eating out", "count": 8, "total": 212.5, "last": "22 July 2026"},
    {"name": "Spotify", "envelope": "Subscriptions", "count": 12, "total": 143.88, "last": "21 July 2026"},
    {"name": "Coolblue", "envelope": "Hobbies", "count": 5, "total": 428.0, "last": "20 July 2026"},
    {"name": "Woningcorporatie Ymere", "envelope": "Rent", "count": 12, "total": 13800.0, "last": "11 July 2026"},
]

ACCOUNTS_LIST = [
    {"name": "ING Checking", "type": "Checking", "balance": 2418.62, "meta": "EUR · last import 24 July"},
    {"name": "ING Savings", "type": "Savings", "balance": 9250.0, "meta": "EUR · last import 1 July"},
    {"name": "Revolut Card", "type": "Credit card", "balance": -318.44, "meta": "EUR · last import 22 July"},
    {"name": "Cash", "type": "Cash", "balance": 85.0, "meta": "EUR · updated by hand"},
]

IMPORT_ROWS = [
    {"date": "23.07", "payee": "Albert Heijn 1284", "envelope": "Groceries", "amount": -42.18, "state": "ok"},
    {"date": "23.07", "payee": "NS Reizigers", "envelope": "Transport", "amount": -8.6, "state": "ok"},
    {"date": "22.07", "payee": "Café de Sluis", "envelope": "Eating out", "amount": -34.5, "state": "warn"},
    {"date": "21.07", "payee": "Spotify AB", "envelope": "Subscriptions", "amount": -11.99, "state": "ok"},
    {"date": "20.07", "payee": "Coolblue", "envelope": "Hobbies", "amount": -64, "state": "warn"},
    {"date": "19.07", "payee": "SEPA overboeking 8841", "envelope": "Pick an envelope", "amount": -120, "state": "none"},
]

ALERT_HISTORY = [
    {"title": "Gifts went 22,50 € over its plan", "meta": "Yesterday, 17:42 · Gifts · sent by email", "cta": "Open", "over": True},
    {"title": "Groceries reached 85% with 9 days left", "meta": "Yesterday, 09:15 · Groceries · sent by email", "cta": "Open", "over": False},
    {"title": "Eating out reached 95% with 11 days left", "meta": "20 July, 20:03 · Eating out · sent by email", "cta": "Open", "over": False},
    {"title": "Forecast: you are on pace to overspend by 118,20 €", "meta": "18 July, 08:00 · Whole budget", "cta": "Forecast", "over": True},
    {"title": "Subscriptions reached 100% with 14 days left", "meta": "17 July, 12:31 · Subscriptions", "cta": "Open", "over": False},
    {"title": "Transport reached 80% with 19 days left", "meta": "12 July, 07:55 · Transport", "cta": "Open", "over": False},
]

SETUP_STEPS = [
    {"n": 1, "title": "Add your first account", "body": "Checking, savings, credit card or cash — it just needs a name and a currency.", "cta": "Add account", "done": True},
    {"n": 2, "title": "Import a bank statement", "body": "CSV, MT940 or OFX. You will see every row before anything is saved.", "cta": "Import", "done": False},
    {"n": 3, "title": "Give your money jobs", "body": "Create envelopes and assign this month's money to them.", "cta": "Envelopes", "done": False},
]
