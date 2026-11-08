"""Envelope allocations: how much was assigned to an envelope in a month.

An allocation has no `user_id` of its own - it belongs to whoever owns its
envelope. Every query here therefore reaches the owner through a join to
`Envelope`, and every `envelope_id` taken from a request is checked with
`get_owned_envelope` first.
"""

import uuid
from datetime import date
from decimal import Decimal

from app.db.models import Envelope, EnvelopeAllocation, Transaction
from app.db.repositories.envelope import get_owned_envelope
from app.schemas.envelope_allocation import (
    EnvelopeAllocationCreate,
    EnvelopeAllocationTransfer,
    EnvelopeAllocationUpdate,
)
from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


def _owned_allocations(user_id: uuid.UUID):
    return select(EnvelopeAllocation).join(Envelope, EnvelopeAllocation.envelope_id == Envelope.id).where(
        Envelope.user_id == user_id
    )


async def get_envelope_allocations(db: AsyncSession, user_id: uuid.UUID, envelopeId: uuid.UUID | None = None):
    query = _owned_allocations(user_id)
    if envelopeId is not None:
        query = query.where(EnvelopeAllocation.envelope_id == envelopeId)

    envelope_allocations = (await db.execute(query)).scalars().all()
    if not envelope_allocations:
        raise HTTPException(status_code=404, detail="Envelope Allocation not found")
    return envelope_allocations


async def update_envelope_allocation(
    db: AsyncSession, user_id: uuid.UUID, envelopeAllocationId: uuid.UUID, data: EnvelopeAllocationUpdate
):
    result = await db.execute(_owned_allocations(user_id).where(EnvelopeAllocation.id == envelopeAllocationId))
    envelope_allocation = result.scalar_one_or_none()
    if envelope_allocation is None:
        raise HTTPException(status_code=404, detail="Envelope Allocation not found")

    values = data.model_dump(exclude_unset=True)
    if values.get("envelope_id") is not None:
        await get_owned_envelope(db, user_id, values["envelope_id"])
    if values:
        await db.execute(
            update(EnvelopeAllocation).where(EnvelopeAllocation.id == envelopeAllocationId).values(**values)
        )
        await db.commit()
        await db.refresh(envelope_allocation)
    return envelope_allocation


async def create_envelope_allocation(db: AsyncSession, user_id: uuid.UUID, data: EnvelopeAllocationCreate):
    await get_owned_envelope(db, user_id, data.envelope_id)
    envelope_allocation = EnvelopeAllocation(**data.model_dump())
    db.add(envelope_allocation)
    try:
        await db.commit()
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="An allocation for this envelope and month already exists.",
        )
    await db.refresh(envelope_allocation)
    return envelope_allocation


async def get_to_assign(db: AsyncSession, user_id: uuid.UUID) -> Decimal:
    """Money that has arrived but has not been given a job yet.

    The identity this has to satisfy is `cash = to_assign + sum(available)`,
    where an envelope's available is `assigned - spent`. Solving for to_assign:

        to_assign = cash - sum(assigned) + spending charged to an envelope

    That last term is the correction: spending leaves the account *and* the
    envelope it was charged to, so subtracting the full `sum(assigned)` on its
    own counts every categorised purchase twice. Without it the figure drifted
    further below the truth with every transaction imported, and the Dashboard's
    "Safe to spend" drifted with it.

    Uncategorised spending is deliberately not added back: it reduces cash and
    belongs to no envelope, so it genuinely leaves less money to assign.

    All three sums are the user's own: their transactions, and the allocations
    of their envelopes.
    """
    total_transactions = await db.scalar(select(func.sum(Transaction.amount)).where(Transaction.user_id == user_id))
    total_assigned = await db.scalar(
        select(func.sum(EnvelopeAllocation.assigned_amount))
        .join(Envelope, EnvelopeAllocation.envelope_id == Envelope.id)
        .where(Envelope.user_id == user_id)
    )
    envelope_spending = await db.scalar(
        select(func.sum(-Transaction.amount)).where(
            Transaction.user_id == user_id,
            Transaction.amount < 0,
            Transaction.envelope_id.is_not(None),
        )
    )
    return (
        (total_transactions or Decimal("0")) - (total_assigned or Decimal("0")) + (envelope_spending or Decimal("0"))
    )


async def get_or_build_envelope_allocation(db: AsyncSession, envelopeId: uuid.UUID, month: date) -> EnvelopeAllocation:
    """The envelope's allocation for `month`, or an unsaved zero one.

    Does not check ownership - callers must have checked the envelope already.
    """
    result = await db.execute(
        select(EnvelopeAllocation).where(
            EnvelopeAllocation.envelope_id == envelopeId,
            EnvelopeAllocation.month == month,
        )
    )
    envelope_allocation = result.scalar_one_or_none()
    if envelope_allocation is not None:
        return envelope_allocation

    return EnvelopeAllocation(envelope_id=envelopeId, month=month, assigned_amount=Decimal("0"))


async def transfer_envelope_allocation(db: AsyncSession, user_id: uuid.UUID, data: EnvelopeAllocationTransfer):
    # Both ends must be the caller's: otherwise this would move money into, or
    # out of, someone else's budget.
    await get_owned_envelope(db, user_id, data.from_envelope_id)
    await get_owned_envelope(db, user_id, data.to_envelope_id)

    source_allocation = await get_or_build_envelope_allocation(db, data.from_envelope_id, data.month)
    target_allocation = await get_or_build_envelope_allocation(db, data.to_envelope_id, data.month)

    if data.from_envelope_id == data.to_envelope_id:
        raise HTTPException(status_code=400, detail="Cannot transfer to the same envelope")

    if data.amount <= 0 or source_allocation.assigned_amount < data.amount:
        raise HTTPException(
            status_code=409,
            detail="Transferred amount cannot be greater than assigned_amount",
        )

    if target_allocation.id is None:
        db.add(target_allocation)

    source_allocation.assigned_amount -= data.amount
    target_allocation.assigned_amount += data.amount

    await db.commit()
    await db.refresh(source_allocation)
    await db.refresh(target_allocation)

    return [source_allocation, target_allocation]
