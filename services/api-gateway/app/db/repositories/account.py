import uuid

from app.db.models import Account
from app.db.repositories.constants import SEED_USER_ID
from app.schemas.account import AccountCreate, AccountUpdate
from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


async def get_accounts(db: AsyncSession, skip: int = 0, limit: int = 100):
    result = await db.execute(select(Account).offset(skip).limit(limit))
    accounts = result.scalars().all()
    if not accounts:
        raise HTTPException(status_code=404, detail="Accounts not found")
    return accounts


async def delete_account(db: AsyncSession, accountId: uuid.UUID):
    result = await db.execute(select(Account).where(Account.id == accountId))
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    try:
        await db.execute(delete(Account).where(Account.id == accountId))
        await db.commit()
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete account: it still has associated statements or transactions. Archive the account instead, or remove its transaction history first.",
        )

    return account


async def update_account(db: AsyncSession, accountId: uuid.UUID, data: AccountUpdate):
    result = await db.execute(select(Account).where(Account.id == accountId))
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    values = data.model_dump(exclude_unset=True)
    if values:
        await db.execute(
            update(Account).where(Account.id == accountId).values(**values)
        )
        await db.commit()
        await db.refresh(account)
    return account


async def create_account(db: AsyncSession, data: AccountCreate):
    account = Account(**data.model_dump(), user_id=SEED_USER_ID)
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account
