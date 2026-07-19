import uuid

from app.db.models import Payee
from app.db.repositories.constants import SEED_USER_ID
from app.schemas.payee import PayeeCreate, PayeeUpdate
from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


async def get_payees(db: AsyncSession, skip: int = 0, limit: int = 100):
    result = await db.execute(select(Payee).offset(skip).limit(limit))
    payees = result.scalars().all()
    if not payees:
        raise HTTPException(status_code=404, detail="Payees not found")
    return payees


async def delete_payee(db: AsyncSession, payeeId: uuid.UUID):
    result = await db.execute(select(Payee).where(Payee.id == payeeId))
    payee = result.scalar_one_or_none()
    if payee is None:
        raise HTTPException(status_code=404, detail="Payee not found")

    try:
        await db.execute(delete(Payee).where(Payee.id == payeeId))
        await db.commit()
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete payee: it still has associated transactions. Remove or reassign those transactions first.",
        )

    return payee


async def update_payee(db: AsyncSession, payeeId: uuid.UUID, data: PayeeUpdate):
    result = await db.execute(select(Payee).where(Payee.id == payeeId))
    payee = result.scalar_one_or_none()
    if payee is None:
        raise HTTPException(status_code=404, detail="Payee not found")

    values = data.model_dump(exclude_unset=True)
    if values:
        await db.execute(update(Payee).where(Payee.id == payeeId).values(**values))
        await db.commit()
        await db.refresh(payee)
    return payee


async def create_payee(db: AsyncSession, data: PayeeCreate):
    payee = Payee(**data.model_dump(), user_id=SEED_USER_ID)
    db.add(payee)
    await db.commit()
    await db.refresh(payee)
    return payee


async def get_or_create_payee(db: AsyncSession, name: str) -> Payee:
    normalized_name = name.strip()

    result = await db.execute(
        select(Payee).where(func.lower(Payee.name) == normalized_name.lower())
    )
    payee = result.scalar_one_or_none()
    if payee is not None:
        return payee

    payee = Payee(name=normalized_name, user_id=SEED_USER_ID)
    db.add(payee)
    await db.commit()
    await db.refresh(payee)
    return payee
