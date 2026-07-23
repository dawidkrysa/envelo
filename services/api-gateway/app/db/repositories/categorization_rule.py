import uuid

from app.db.models import CategorizationRule, Transaction
from app.db.repositories.constants import SEED_USER_ID
from app.schemas.categorization_rule import (
    CategorizationRuleCreate,
    CategorizationRuleUpdate,
)
from fastapi import HTTPException
from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


async def get_categorization_rules(db: AsyncSession, skip: int = 0, limit: int = 100):
    result = await db.execute(select(CategorizationRule).offset(skip).limit(limit))
    rules = result.scalars().all()
    if not rules:
        raise HTTPException(status_code=404, detail="Categorization rules not found")
    return rules


async def create_categorization_rule(db: AsyncSession, data: CategorizationRuleCreate):
    rule = CategorizationRule(**data.model_dump(), user_id=SEED_USER_ID)
    db.add(rule)
    try:
        await db.commit()
    except IntegrityError:
        raise HTTPException(
            status_code=409, detail="Invalid reference: envelope does not exist."
        )
    await db.refresh(rule)
    return rule


async def update_categorization_rule(
    db: AsyncSession, categorizationRuleId: uuid.UUID, data: CategorizationRuleUpdate
):
    result = await db.execute(
        select(CategorizationRule).where(CategorizationRule.id == categorizationRuleId)
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Categorization rule not found")

    values = data.model_dump(exclude_unset=True)
    if values:
        try:
            await db.execute(
                update(CategorizationRule)
                .where(CategorizationRule.id == categorizationRuleId)
                .values(**values)
            )
            await db.commit()
        except IntegrityError:
            raise HTTPException(
                status_code=409, detail="Invalid reference: envelope does not exist."
            )
        await db.refresh(rule)
    return rule


async def delete_categorization_rule(db: AsyncSession, categorizationRuleId: uuid.UUID):
    result = await db.execute(
        select(CategorizationRule).where(CategorizationRule.id == categorizationRuleId)
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Categorization rule not found")

    await db.execute(
        delete(CategorizationRule).where(CategorizationRule.id == categorizationRuleId)
    )
    await db.commit()

    return rule


async def match_envelope_for_transaction(
    db: AsyncSession, payee_id: uuid.UUID | None, description: str | None
) -> uuid.UUID | None:

    if payee_id is not None:
        result = await db.execute(
            select(
                Transaction.envelope_id, func.count(Transaction.payee_id).label("count")
            )
            .where(
                Transaction.payee_id == payee_id, Transaction.envelope_id.isnot(None)
            )
            .group_by(Transaction.envelope_id)
            .order_by(desc("count"))
            .limit(1)
        )
        envelope_id = result.scalar()
        if envelope_id is not None:
            return envelope_id

    if description is not None:
        categorization_rules = await db.execute(
            select(CategorizationRule).where(CategorizationRule.user_id == SEED_USER_ID)
        )

        matches: list[CategorizationRule] = []
        for row in categorization_rules.scalars():
            if row.phrase.lower() in description.lower():
                matches.append(row)

        if matches:
            return max(matches, key=lambda r: len(r.phrase)).envelope_id
        return None

    return None
