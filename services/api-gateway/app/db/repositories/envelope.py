import uuid

from app.db.models import CategorizationRule, Envelope, EnvelopeAllocation, Transaction
from app.db.repositories.category_group import get_owned_category_group
from app.schemas.envelope import EnvelopeCreate, EnvelopeUpdate
from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession


async def get_envelopes(db: AsyncSession, user_id: uuid.UUID, categoryGroupId: uuid.UUID | None):
    query = select(Envelope).where(Envelope.user_id == user_id)
    if categoryGroupId is not None:
        query = query.where(Envelope.category_group_id == categoryGroupId)
    envelopes = (await db.execute(query)).scalars().all()
    if not envelopes:
        raise HTTPException(status_code=404, detail="Envelope not found")
    return envelopes


async def get_owned_envelope(db: AsyncSession, user_id: uuid.UUID, envelope_id: uuid.UUID) -> Envelope:
    """The user's envelope, or 404 - also when it exists but is someone else's.

    Also what every other repository calls before accepting an `envelope_id`
    from a request: the foreign key only proves the envelope exists, not whose
    it is.
    """
    result = await db.execute(select(Envelope).where(Envelope.id == envelope_id, Envelope.user_id == user_id))
    envelope = result.scalar_one_or_none()
    if envelope is None:
        raise HTTPException(status_code=404, detail="Envelope not found")
    return envelope


async def delete_envelope(db: AsyncSession, user_id: uuid.UUID, envelopeId: uuid.UUID):
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

    The cascade below filters only by envelope: once ownership of the envelope
    is established, everything pointing at it is the same user's.
    """
    envelope = await get_owned_envelope(db, user_id, envelopeId)

    await db.execute(update(Transaction).where(Transaction.envelope_id == envelopeId).values(envelope_id=None))
    await db.execute(delete(EnvelopeAllocation).where(EnvelopeAllocation.envelope_id == envelopeId))
    await db.execute(delete(CategorizationRule).where(CategorizationRule.envelope_id == envelopeId))
    await db.execute(delete(Envelope).where(Envelope.id == envelopeId))
    await db.commit()

    return envelope


async def update_envelope(db: AsyncSession, user_id: uuid.UUID, envelopeId: uuid.UUID, data: EnvelopeUpdate):
    envelope = await get_owned_envelope(db, user_id, envelopeId)

    values = data.model_dump(exclude_unset=True)
    if values.get("category_group_id") is not None:
        await get_owned_category_group(db, user_id, values["category_group_id"])
    if values:
        await db.execute(update(Envelope).where(Envelope.id == envelopeId).values(**values))
        await db.commit()
        await db.refresh(envelope)
    return envelope


async def create_envelope(db: AsyncSession, user_id: uuid.UUID, data: EnvelopeCreate):
    await get_owned_category_group(db, user_id, data.category_group_id)
    envelope = Envelope(**data.model_dump(), user_id=user_id)
    db.add(envelope)
    await db.commit()
    await db.refresh(envelope)
    return envelope
