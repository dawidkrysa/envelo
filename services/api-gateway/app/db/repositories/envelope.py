import uuid

from app.db.models import CategorizationRule, Envelope, EnvelopeAllocation, Transaction
from app.db.repositories.constants import SEED_USER_ID
from app.schemas.envelope import EnvelopeCreate, EnvelopeUpdate
from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession


async def get_envelopes(db: AsyncSession, categoryGroupId: uuid.UUID | None):
    if categoryGroupId is None:
        result = await db.execute(select(Envelope))
    else:
        result = await db.execute(
            select(Envelope).where(Envelope.category_group_id == categoryGroupId)
        )

    envelopes = result.scalars().all()
    if not envelopes:
        raise HTTPException(status_code=404, detail="Envelope not found")
    return envelopes


async def delete_envelope(db: AsyncSession, envelopeId: uuid.UUID):
    """Delete an envelope and let go of what pointed at it.

    Its transactions are *uncategorised*, not deleted: they really happened, and
    refusing the delete until the user reassigns every one of them (which is
    what the old 409 did) made an envelope created by mistake permanent as soon
    as a single import touched it. Its allocations and categorisation rules are
    removed outright - both describe an envelope that is about to stop existing.

    The budget still balances afterwards. Dropping the allocations returns
    `assigned` to the pool, and uncategorising the spending removes it from the
    correction term in `get_to_assign`, so `to_assign` gains exactly the
    envelope's `available` - which is precisely what the envelope stops
    contributing to `sum(available)`.
    """
    result = await db.execute(select(Envelope).where(Envelope.id == envelopeId))
    envelope = result.scalar_one_or_none()
    if envelope is None:
        raise HTTPException(status_code=404, detail="Envelope not found")

    await db.execute(
        update(Transaction).where(Transaction.envelope_id == envelopeId).values(envelope_id=None)
    )
    await db.execute(delete(EnvelopeAllocation).where(EnvelopeAllocation.envelope_id == envelopeId))
    await db.execute(delete(CategorizationRule).where(CategorizationRule.envelope_id == envelopeId))
    await db.execute(delete(Envelope).where(Envelope.id == envelopeId))
    await db.commit()

    return envelope


async def update_envelope(
    db: AsyncSession, envelopeId: uuid.UUID, data: EnvelopeUpdate
):
    result = await db.execute(select(Envelope).where(Envelope.id == envelopeId))
    envelope = result.scalar_one_or_none()
    if envelope is None:
        raise HTTPException(status_code=404, detail="Envelope not found")

    values = data.model_dump(exclude_unset=True)
    if values:
        await db.execute(
            update(Envelope).where(Envelope.id == envelopeId).values(**values)
        )
        await db.commit()
        await db.refresh(envelope)
    return envelope


async def create_envelope(db: AsyncSession, data: EnvelopeCreate):
    envelope = Envelope(**data.model_dump(), user_id=SEED_USER_ID)
    db.add(envelope)
    await db.commit()
    await db.refresh(envelope)
    return envelope
