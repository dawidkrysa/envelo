import uuid
from datetime import date
from decimal import Decimal

from app.db.models import EnvelopeAllocation, Transaction
from app.schemas.envelope_allocation import (
    EnvelopeAllocationCreate,
    EnvelopeAllocationTransfer,
    EnvelopeAllocationUpdate,
)
from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


async def get_envelope_allocations(
    db: AsyncSession, envelopeId: uuid.UUID | None = None
):
    if envelopeId is None:
        result = await db.execute(select(EnvelopeAllocation))
    else:
        result = await db.execute(
            select(EnvelopeAllocation).where(
                EnvelopeAllocation.envelope_id == envelopeId
            )
        )

    envelope_allocations = result.scalars().all()
    if not envelope_allocations:
        raise HTTPException(status_code=404, detail="Envelope Allocation not found")
    return envelope_allocations


async def update_envelope_allocation(
    db: AsyncSession, envelopeAllocationId: uuid.UUID, data: EnvelopeAllocationUpdate
):
    result = await db.execute(
        select(EnvelopeAllocation).where(EnvelopeAllocation.id == envelopeAllocationId)
    )
    envelope_allocation = result.scalar_one_or_none()
    if envelope_allocation is None:
        raise HTTPException(status_code=404, detail="Envelope Allocation not found")

    values = data.model_dump(exclude_unset=True)
    if values:
        await db.execute(
            update(EnvelopeAllocation)
            .where(EnvelopeAllocation.id == envelopeAllocationId)
            .values(**values)
        )
        await db.commit()
        await db.refresh(envelope_allocation)
    return envelope_allocation


async def create_envelope_allocation(db: AsyncSession, data: EnvelopeAllocationCreate):
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


async def get_to_assign(db: AsyncSession) -> Decimal:
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
    """
    total_transactions = await db.scalar(select(func.sum(Transaction.amount)))
    total_assigned = await db.scalar(select(func.sum(EnvelopeAllocation.assigned_amount)))
    envelope_spending = await db.scalar(
        select(func.sum(-Transaction.amount)).where(
            Transaction.amount < 0,
            Transaction.envelope_id.is_not(None),
        )
    )
    return (
        (total_transactions or Decimal("0"))
        - (total_assigned or Decimal("0"))
        + (envelope_spending or Decimal("0"))
    )


async def get_or_build_envelope_allocation(
    db: AsyncSession, envelopeId: uuid.UUID, month: date
) -> EnvelopeAllocation:
    result = await db.execute(
        select(EnvelopeAllocation).where(
            EnvelopeAllocation.envelope_id == envelopeId,
            EnvelopeAllocation.month == month,
        )
    )
    envelope_allocation = result.scalar_one_or_none()
    if envelope_allocation is not None:
        return envelope_allocation

    return EnvelopeAllocation(
        envelope_id=envelopeId, month=month, assigned_amount=Decimal("0")
    )


async def transfer_envelope_allocation(
    db: AsyncSession, data: EnvelopeAllocationTransfer
):
    source_allocation = await get_or_build_envelope_allocation(
        db, data.from_envelope_id, data.month
    )
    target_allocation = await get_or_build_envelope_allocation(
        db, data.to_envelope_id, data.month
    )

    if data.from_envelope_id == data.to_envelope_id:
        raise HTTPException(
            status_code=400, detail="Cannot transfer to the same envelope"
        )

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
