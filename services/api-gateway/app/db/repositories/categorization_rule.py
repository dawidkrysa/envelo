import uuid

from app.db.models import CategorizationRule, Transaction
from app.db.repositories.envelope import get_owned_envelope
from app.schemas.categorization_rule import (
    CategorizationRuleCreate,
    CategorizationRuleUpdate,
)
from fastapi import HTTPException
from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


async def get_categorization_rules(db: AsyncSession, user_id: uuid.UUID, skip: int = 0, limit: int = 100):
    result = await db.execute(
        select(CategorizationRule).where(CategorizationRule.user_id == user_id).offset(skip).limit(limit)
    )
    rules = result.scalars().all()
    if not rules:
        raise HTTPException(status_code=404, detail="Categorization rules not found")
    return rules


async def get_owned_categorization_rule(
    db: AsyncSession, user_id: uuid.UUID, categorization_rule_id: uuid.UUID
) -> CategorizationRule:
    result = await db.execute(
        select(CategorizationRule).where(
            CategorizationRule.id == categorization_rule_id, CategorizationRule.user_id == user_id
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Categorization rule not found")
    return rule


async def create_categorization_rule(db: AsyncSession, user_id: uuid.UUID, data: CategorizationRuleCreate):
    await get_owned_envelope(db, user_id, data.envelope_id)
    rule = CategorizationRule(**data.model_dump(), user_id=user_id)
    db.add(rule)
    try:
        await db.commit()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Invalid reference: envelope does not exist.")
    await db.refresh(rule)
    return rule


async def update_categorization_rule(
    db: AsyncSession, user_id: uuid.UUID, categorizationRuleId: uuid.UUID, data: CategorizationRuleUpdate
):
    rule = await get_owned_categorization_rule(db, user_id, categorizationRuleId)

    values = data.model_dump(exclude_unset=True)
    if values.get("envelope_id") is not None:
        await get_owned_envelope(db, user_id, values["envelope_id"])
    if values:
        try:
            await db.execute(
                update(CategorizationRule).where(CategorizationRule.id == categorizationRuleId).values(**values)
            )
            await db.commit()
        except IntegrityError:
            raise HTTPException(status_code=409, detail="Invalid reference: envelope does not exist.")
        await db.refresh(rule)
    return rule


async def delete_categorization_rule(db: AsyncSession, user_id: uuid.UUID, categorizationRuleId: uuid.UUID):
    rule = await get_owned_categorization_rule(db, user_id, categorizationRuleId)

    await db.execute(delete(CategorizationRule).where(CategorizationRule.id == categorizationRuleId))
    await db.commit()

    return rule


async def match_envelope_for_transaction(
    db: AsyncSession, user_id: uuid.UUID, payee_id: uuid.UUID | None, payee_name: str | None
) -> uuid.UUID | None:
    """Which envelope an imported transaction belongs in, if we can tell.

    A rule is a phrase matched against the **payee's name**, case-insensitively,
    longest match winning. It used to be matched against the transaction
    description while every screen said "Payee contains" - the UI was describing
    a feature the matcher did not have.

    **An explicit rule beats what the payee did before.** The order used to be
    the other way round, which was defensible while the two looked at different
    things. Now that both key off the payee it is not: a rule written for a payee
    you have already filed anywhere would never fire, so the feature would be
    dead exactly for the payees you have most reason to write a rule about. A
    rule is something you stated; history is something we inferred.

    Both signals are the user's own - their rules, their history - so one
    person's filing habits never decide where another's transactions land.

    Returns `None` when neither has an opinion - an uncategorized transaction is
    a fine outcome, and guessing would cost more to unpick than to do by hand.
    """
    if payee_name:
        categorization_rules = await db.execute(
            select(CategorizationRule).where(CategorizationRule.user_id == user_id)
        )

        matches: list[CategorizationRule] = []
        for row in categorization_rules.scalars():
            if row.phrase.lower() in payee_name.lower():
                matches.append(row)

        if matches:
            return max(matches, key=lambda r: len(r.phrase)).envelope_id

    if payee_id is not None:
        result = await db.execute(
            select(Transaction.envelope_id, func.count(Transaction.payee_id).label("count"))
            .where(
                Transaction.user_id == user_id,
                Transaction.payee_id == payee_id,
                Transaction.envelope_id.isnot(None),
            )
            .group_by(Transaction.envelope_id)
            .order_by(desc("count"))
            .limit(1)
        )
        envelope_id = result.scalar()
        if envelope_id is not None:
            return envelope_id

    return None
