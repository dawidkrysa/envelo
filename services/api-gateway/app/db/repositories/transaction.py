import uuid
from datetime import date

from app.db.models import CategorizationSource, Envelope, Transaction
from app.db.repositories.constants import SEED_USER_ID
from app.schemas.transaction import TransactionCreate, TransactionUpdate
from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


async def get_transactions(
    db: AsyncSession,
    accountId: uuid.UUID | None = None,
    envelopeId: uuid.UUID | None = None,
    categoryGroupId: uuid.UUID | None = None,
    dateFrom: date | None = None,
    dateTo: date | None = None,
    skip: int = 0,
    limit: int = 100,
):
    query = select(Transaction)

    if accountId is not None:
        query = query.where(Transaction.account_id == accountId)

    if envelopeId is not None:
        query = query.where(Transaction.envelope_id == envelopeId)

    if categoryGroupId is not None:
        query = query.join(Envelope, Transaction.envelope_id == Envelope.id).where(
            Envelope.category_group_id == categoryGroupId
        )

    if dateFrom is not None:
        query = query.where(Transaction.transaction_date >= dateFrom)

    if dateTo is not None:
        query = query.where(Transaction.transaction_date <= dateTo)

    result = await db.execute(query.offset(skip).limit(limit))

    transaction = result.scalars().all()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


async def create_transaction(db: AsyncSession, data: TransactionCreate):
    transaction = Transaction(**data.model_dump(), user_id=SEED_USER_ID)
    db.add(transaction)
    try:
        await db.commit()
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Invalid reference: account, envelope, payee or statement does not exist.",
        )
    await db.refresh(transaction)
    return transaction


async def update_transaction(
    db: AsyncSession, transactionId: uuid.UUID, data: TransactionUpdate
):
    result = await db.execute(
        select(Transaction).where(Transaction.id == transactionId)
    )
    transaction = result.scalar_one_or_none()
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    values = data.model_dump(exclude_unset=True)
    if "envelope_id" in values or "payee_id" in values:
        values["categorization_source"] = CategorizationSource.MANUAL

    if values:
        try:
            await db.execute(
                update(Transaction)
                .where(Transaction.id == transactionId)
                .values(**values)
            )
            await db.commit()
        except IntegrityError:
            raise HTTPException(
                status_code=409,
                detail="Invalid reference: account, envelope, payee or statement does not exist.",
            )
        await db.refresh(transaction)
    return transaction


async def delete_transaction(db: AsyncSession, transactionId: uuid.UUID):
    result = await db.execute(
        select(Transaction).where(Transaction.id == transactionId)
    )
    transaction = result.scalar_one_or_none()
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    await db.execute(delete(Transaction).where(Transaction.id == transactionId))
    await db.commit()

    return transaction
