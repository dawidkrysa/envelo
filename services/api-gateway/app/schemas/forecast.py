"""Schemas for `GET /budget/forecast`.

Deliberately shaped around *what a forecast says* rather than around how the
current one is computed, so the arithmetic behind it can be replaced by a real
predictive model without any consumer changing. Every number a client needs to
draw the screen is in here; nothing here has to be recomputed client-side.
"""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ForecastEnvelopeRead(BaseModel):
    """One envelope's month-end outlook.

    `funded` is the baseline the projection is judged against - what the
    envelope actually holds (carried over from earlier months plus assigned this
    one), not just this month's assignment. Comparing a month-end projection
    against a monthly top-up would call an envelope "trending over" while it
    still had last month's money sitting in it.
    """

    envelope_id: uuid.UUID
    category_group_id: uuid.UUID
    carried_over: Decimal
    assigned: Decimal
    funded: Decimal
    spent: Decimal
    projected: Decimal

    model_config = ConfigDict(from_attributes=True)


class ForecastGroupRead(BaseModel):
    """One category group's outlook, in the groups' own `sort_order`.

    A rollup rather than something the client sums for itself: today it happens
    to be the sum of the group's envelopes, but a model that learns at group
    level ("December is always heavy on Gifts") need not agree with the sum of
    its parts, and the client should not have to know which of the two it is
    looking at.
    """

    category_group_id: uuid.UUID
    funded: Decimal
    spent: Decimal
    projected: Decimal

    model_config = ConfigDict(from_attributes=True)


class ForecastRead(BaseModel):
    """The whole month's outlook: totals, per group, per envelope.

    `method` names the estimator that produced it (`"linear-pace"` today) so a
    screen can say how the numbers were arrived at instead of presenting a
    straight-line guess with the authority of a prediction. Clients should treat
    an unknown value as "some model", not as an error - new estimators will
    appear here.

    `as_of` is the day the projection is anchored to and `elapsed_fraction` how
    much of the month that covers; for a month already over, the fraction is 1
    and `projected` is simply what was spent.
    """

    month: date
    as_of: date
    elapsed_fraction: Decimal
    method: str
    funded_total: Decimal
    spent_total: Decimal
    projected_total: Decimal
    category_groups: list[ForecastGroupRead]
    envelopes: list[ForecastEnvelopeRead]

    model_config = ConfigDict(from_attributes=True)
