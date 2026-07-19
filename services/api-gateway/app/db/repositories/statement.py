import uuid

from app.db.models import Statement
from app.db.repositories.constants import SEED_USER_ID
from app.schemas.statement import StatementCreate, StatementUpdate
from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


async def get_statements(db: AsyncSession, accountId: uuid.UUID | None = None):
    if accountId is None:
        result = await db.execute(select(Statement))
    else:
        result = await db.execute(
            select(Statement).where(Statement.account_id == accountId)
        )

    statements = result.scalars().all()
    if not statements:
        raise HTTPException(status_code=404, detail="Statements not found")
    return statements


async def delete_statement(db: AsyncSession, statementId: uuid.UUID):
    result = await db.execute(select(Statement).where(Statement.id == statementId))
    statement = result.scalar_one_or_none()
    if statement is None:
        raise HTTPException(status_code=404, detail="Statement not found")

    try:
        await db.execute(delete(Statement).where(Statement.id == statementId))
        await db.commit()
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete statement: it still has associated transactions. Remove or reassign those transactions first.",
        )

    return statement


async def update_statement(
    db: AsyncSession, statementId: uuid.UUID, data: StatementUpdate
):
    result = await db.execute(select(Statement).where(Statement.id == statementId))
    statement = result.scalar_one_or_none()
    if statement is None:
        raise HTTPException(status_code=404, detail="Statement not found")

    values = data.model_dump(exclude_unset=True)
    if values:
        await db.execute(
            update(Statement).where(Statement.id == statementId).values(**values)
        )
        await db.commit()
        await db.refresh(statement)
    return statement


async def create_statement(db: AsyncSession, data: StatementCreate):
    statement = Statement(**data.model_dump(), user_id=SEED_USER_ID)
    db.add(statement)
    await db.commit()
    await db.refresh(statement)
    return statement
