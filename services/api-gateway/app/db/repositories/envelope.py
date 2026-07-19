import uuid

from app.db.models import Envelope
from app.db.repositories.constants import SEED_USER_ID
from app.schemas.envelope import EnvelopeCreate, EnvelopeUpdate
from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
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
    result = await db.execute(select(Envelope).where(Envelope.id == envelopeId))
    envelope = result.scalar_one_or_none()
    if envelope is None:
        raise HTTPException(status_code=404, detail="Envelope not found")

    try:
        await db.execute(delete(Envelope).where(Envelope.id == envelopeId))
        await db.commit()
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete envelope: it still has associated transactions. Move or delete those transactions first.",
        )

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
