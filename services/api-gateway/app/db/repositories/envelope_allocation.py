import uuid
from datetime import date
from decimal import Decimal

from app.db.models import EnvelopeAllocation
from app.schemas.envelope_allocation import (
    EnvelopeAllocationCreate,
    EnvelopeAllocationTransfer,
    EnvelopeAllocationUpdate,
)
from fastapi import HTTPException
from sqlalchemy import select, update
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


async def get_or_build_envelope_allocation(
    db: AsyncSession, envelopeId: uuid.UUID, month: date
) -> EnvelopeAllocation:
    """Zwraca istniejący wiersz alokacji dla (envelope, month) albo "wirtualny"
    obiekt z assigned_amount=0, jeśli wiersz jeszcze nie istnieje (nie jest
    dodany do sesji - wywołujący decyduje, czy i kiedy go zapisać)."""
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
