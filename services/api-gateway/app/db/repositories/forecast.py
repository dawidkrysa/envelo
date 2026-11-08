"""Month-end outlook per envelope and category group.

Not an entity - there is no `forecasts` table and nothing here writes. It lives
in its own repository module rather than inside `envelope_allocation.py` or
`transaction.py` because it reads both and belongs to neither, and because it is
the one place a real predictive model will replace: swap `_project` (and the
`method` string it reports) and every consumer keeps working.

The current estimator is deliberately the dumbest one that is honest: spending so
far this month, scaled up by how much of the month is left. It knows nothing
about weekly rhythms, a rent payment that has already gone out, or that December
is not like November - which is exactly why the method is named in the response
instead of being implied.
"""

import calendar
import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.db.models import CategoryGroup, Envelope, EnvelopeAllocation
from app.db.repositories.transaction import get_spent_by_envelope
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

LINEAR_PACE = "linear-pace"
"""The estimator behind `_project`, reported as `ForecastRead.method`. Bump this
to a new name when the arithmetic changes so clients can tell the two apart -
silently changing what the numbers mean under a stable label is worse than
adding a value they do not recognise yet."""

_CENTS = Decimal("0.01")


def _month_bounds(month: date) -> tuple[date, date]:
    last_day = calendar.monthrange(month.year, month.month)[1]
    return month.replace(day=1), date(month.year, month.month, last_day)


def _project(spent: Decimal, elapsed_fraction: Decimal) -> Decimal:
    """Month-to-date spending paced out to the end of the month.

    Nothing spent projects to nothing. The mock this replaced guessed
    `assigned * 0.15` for an untouched envelope, which put an invented 60,00 zł
    of "projected spending" on a savings envelope that exists precisely so it
    will not be spent. With no evidence, the honest projection is zero.
    """
    if spent <= 0:
        return Decimal("0").quantize(_CENTS)
    return (spent / elapsed_fraction).quantize(_CENTS)


async def _assigned_by_envelope(
    db: AsyncSession, user_id: uuid.UUID, month: date, before: bool
) -> dict[str, Decimal]:
    """Assignments for one month, or everything assigned before it.

    Allocations dated *after* the month asked about are excluded from both:
    assigning next month's money should not make this month look better funded
    than it is.
    """
    total = func.sum(EnvelopeAllocation.assigned_amount)
    # Allocations have no owner column; they are the user's through their envelope.
    query = (
        select(EnvelopeAllocation.envelope_id, total)
        .join(Envelope, EnvelopeAllocation.envelope_id == Envelope.id)
        .where(Envelope.user_id == user_id)
        .group_by(EnvelopeAllocation.envelope_id)
    )
    query = query.where(
        EnvelopeAllocation.month < month if before else EnvelopeAllocation.month == month
    )
    result = await db.execute(query)
    return {envelope_id: amount for envelope_id, amount in result.all()}


async def get_forecast(
    db: AsyncSession,
    user_id: uuid.UUID,
    month: date | None = None,
    asOf: date | None = None,
) -> dict:
    """Where this month lands if spending carries on as it has.

    `asOf` pins the day the projection is anchored to - it defaults to today and
    is clamped into the month, so a past month reports its actual spending as
    its projection rather than extrapolating from a fraction of a month that has
    long since ended. Being able to pass it is what makes the figure
    reproducible: without it the only way to test the pacing would be to freeze
    the clock.
    """
    month_start, month_end = _month_bounds(month or date.today())
    anchor = min(asOf or date.today(), month_end)
    anchor = max(anchor, month_start)

    days_in_month = (month_end - month_start).days + 1
    elapsed_days = (anchor - month_start).days + 1
    # Rounded before it is used, not only before it is reported: the response
    # publishes this fraction, and a client that divides `spent` by it has to
    # arrive back at `projected`. A projection you cannot re-derive from the
    # numbers printed beside it reads as an error in one of the two.
    elapsed_fraction = (Decimal(elapsed_days) / Decimal(days_in_month)).quantize(
        Decimal("0.0001")
    )

    envelope_rows = (
        await db.execute(
            select(Envelope.id, Envelope.category_group_id).where(Envelope.user_id == user_id).order_by(Envelope.name)
        )
    ).all()
    group_ids = (
        await db.execute(select(CategoryGroup.id).where(CategoryGroup.user_id == user_id).order_by(CategoryGroup.sort_order))
    ).scalars().all()

    assigned = await _assigned_by_envelope(db, user_id, month_start, before=False)
    assigned_before = await _assigned_by_envelope(db, user_id, month_start, before=True)

    # Both spending figures come from the same aggregate as every other screen,
    # so "spent" here can never disagree with the Envelopes ledger.
    spent_now = {
        row["envelope_id"]: row["spent"]
        for row in await get_spent_by_envelope(db, user_id, month_start, month_end)
    }
    spent_before = {
        row["envelope_id"]: row["spent"]
        for row in await get_spent_by_envelope(db, user_id, None, month_start - timedelta(days=1))
    }

    zero = Decimal("0")
    envelopes = []
    for envelope_id, category_group_id in envelope_rows:
        this_month = assigned.get(envelope_id, zero)
        carried_over = assigned_before.get(envelope_id, zero) - spent_before.get(
            envelope_id, zero
        )
        spent = spent_now.get(envelope_id, zero)
        envelopes.append(
            {
                "envelope_id": envelope_id,
                "category_group_id": category_group_id,
                "carried_over": carried_over,
                "assigned": this_month,
                "funded": carried_over + this_month,
                "spent": spent,
                "projected": _project(spent, elapsed_fraction),
            }
        )

    # Most at risk first: how far each envelope is projected to run past what it
    # holds. Ranking belongs to whatever produced the projection - a model with a
    # notion of confidence would order these differently, and a client that
    # re-sorted by its own rule would quietly overrule it.
    envelopes.sort(key=lambda e: e["projected"] - e["funded"], reverse=True)

    groups = []
    for group_id in group_ids:
        members = [e for e in envelopes if e["category_group_id"] == group_id]
        groups.append(
            {
                "category_group_id": group_id,
                "funded": sum((e["funded"] for e in members), zero),
                "spent": sum((e["spent"] for e in members), zero),
                "projected": sum((e["projected"] for e in members), zero),
            }
        )

    return {
        "month": month_start,
        "as_of": anchor,
        "elapsed_fraction": elapsed_fraction,
        "method": LINEAR_PACE,
        "funded_total": sum((e["funded"] for e in envelopes), zero),
        "spent_total": sum((e["spent"] for e in envelopes), zero),
        "projected_total": sum((e["projected"] for e in envelopes), zero),
        "category_groups": groups,
        "envelopes": envelopes,
    }
