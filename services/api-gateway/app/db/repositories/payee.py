import uuid
from decimal import Decimal

from app.db.models import Payee, Transaction
from app.schemas.payee import PayeeCreate, PayeeMerge, PayeeUpdate
from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


async def get_payees(db: AsyncSession, user_id: uuid.UUID, skip: int = 0, limit: int = 100):
    result = await db.execute(select(Payee).where(Payee.user_id == user_id).offset(skip).limit(limit))
    payees = result.scalars().all()
    if not payees:
        raise HTTPException(status_code=404, detail="Payees not found")
    return payees


async def get_payee_stats(db: AsyncSession, user_id: uuid.UUID):
    """What each payee actually amounts to: how many transactions, their signed
    total, the most recent one, and where they usually get filed.

    None of this fits on `PayeeRead`, and none of it can be worked out by the
    client: `GET /budget/transactions` returns one page, so a payee with more
    history than that would have been counted and summed short - silently, and
    increasingly, as the budget grew.

    `top_envelope_id` is the payee's most frequent envelope, the same signal
    `match_envelope_for_transaction` falls back on, so the screen shows the place
    an unrecognised transaction from this payee would actually land.

    Every payee is listed, including one nothing has been spent on yet - a payee
    created by hand is real, and dropping it here would make this screen disagree
    with `GET /budget/payees`.
    """
    payees = (await db.execute(select(Payee).where(Payee.user_id == user_id).order_by(Payee.name))).scalars().all()

    totals = {
        payee_id: (total, count, last_date)
        for payee_id, total, count, last_date in (
            await db.execute(
                select(
                    Transaction.payee_id,
                    func.sum(Transaction.amount),
                    func.count(Transaction.id),
                    func.max(Transaction.transaction_date),
                )
                .where(Transaction.user_id == user_id, Transaction.payee_id.is_not(None))
                .group_by(Transaction.payee_id)
            )
        ).all()
    }

    # One row per (payee, envelope) with its count; the winner per payee is
    # picked below. Done in one query rather than one per payee - the latter is
    # a round trip per row of the screen.
    per_envelope = (
        await db.execute(
            select(
                Transaction.payee_id,
                Transaction.envelope_id,
                func.count(Transaction.id).label("count"),
            )
            .where(
                Transaction.user_id == user_id,
                Transaction.payee_id.is_not(None),
                Transaction.envelope_id.is_not(None),
            )
            .group_by(Transaction.payee_id, Transaction.envelope_id)
        )
    ).all()

    top_envelope: dict[uuid.UUID, tuple[int, uuid.UUID]] = {}
    for payee_id, envelope_id, count in per_envelope:
        best = top_envelope.get(payee_id)
        if best is None or count > best[0]:
            top_envelope[payee_id] = (count, envelope_id)

    return [
        {
            "payee_id": payee.id,
            "total": totals.get(payee.id, (Decimal("0"), 0, None))[0],
            "transaction_count": totals.get(payee.id, (Decimal("0"), 0, None))[1],
            "last_transaction_date": totals.get(payee.id, (Decimal("0"), 0, None))[2],
            "top_envelope_id": (
                top_envelope[payee.id][1] if payee.id in top_envelope else None
            ),
        }
        for payee in payees
    ]


async def merge_payees(db: AsyncSession, user_id: uuid.UUID, data: PayeeMerge):
    """Fold one payee into another: its transactions are repointed, then it is
    deleted.

    Imports create a payee per spelling, so the same shop arrives as "BIEDRONKA
    1234" and "Biedronka" and the history that drives categorization is split
    between them. Merging is how that gets repaired, and it has to move the
    transactions rather than just delete the duplicate - deleting is refused
    while a payee has any (`delete_payee` above), and would lose the history even
    if it were not.
    """
    if data.from_payee_id == data.into_payee_id:
        raise HTTPException(status_code=400, detail="Cannot merge a payee into itself")

    result = await db.execute(
        select(Payee).where(Payee.id.in_([data.from_payee_id, data.into_payee_id]), Payee.user_id == user_id)
    )
    found = {payee.id: payee for payee in result.scalars()}
    for payee_id in (data.from_payee_id, data.into_payee_id):
        if payee_id not in found:
            raise HTTPException(status_code=404, detail="Payee not found")

    await db.execute(
        update(Transaction)
        .where(Transaction.payee_id == data.from_payee_id)
        .values(payee_id=data.into_payee_id)
    )
    await db.execute(delete(Payee).where(Payee.id == data.from_payee_id))
    await db.commit()

    return found[data.into_payee_id]


async def get_owned_payee(db: AsyncSession, user_id: uuid.UUID, payee_id: uuid.UUID) -> Payee:
    """The user's payee, or 404 - also when it exists but is someone else's."""
    result = await db.execute(select(Payee).where(Payee.id == payee_id, Payee.user_id == user_id))
    payee = result.scalar_one_or_none()
    if payee is None:
        raise HTTPException(status_code=404, detail="Payee not found")
    return payee


async def delete_payee(db: AsyncSession, user_id: uuid.UUID, payeeId: uuid.UUID):
    payee = await get_owned_payee(db, user_id, payeeId)

    try:
        await db.execute(delete(Payee).where(Payee.id == payeeId))
        await db.commit()
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete payee: it still has associated transactions. Remove or reassign those transactions first.",
        )

    return payee


async def update_payee(db: AsyncSession, user_id: uuid.UUID, payeeId: uuid.UUID, data: PayeeUpdate):
    payee = await get_owned_payee(db, user_id, payeeId)

    values = data.model_dump(exclude_unset=True)
    if values:
        await db.execute(update(Payee).where(Payee.id == payeeId).values(**values))
        await db.commit()
        await db.refresh(payee)
    return payee


async def create_payee(db: AsyncSession, user_id: uuid.UUID, data: PayeeCreate):
    payee = Payee(**data.model_dump(), user_id=user_id)
    db.add(payee)
    await db.commit()
    await db.refresh(payee)
    return payee


async def get_or_create_payee(db: AsyncSession, user_id: uuid.UUID, name: str) -> Payee:
    normalized_name = name.strip()

    # `.first()` with an explicit order, not `.scalar_one_or_none()`: there is no
    # unique constraint on `payees.name`, so two payees can legitimately share
    # one. `scalar_one_or_none()` raised MultipleResultsFound on that, turning a
    # duplicate name - data the schema allows - into a 500 for every statement
    # import that mentioned it. Oldest wins, so repeated imports keep resolving
    # to the same payee instead of drifting between them.
    result = await db.execute(
        select(Payee)
        .where(Payee.user_id == user_id, func.lower(Payee.name) == normalized_name.lower())
        .order_by(Payee.id)
        .limit(1)
    )
    payee = result.scalars().first()
    if payee is not None:
        return payee

    payee = Payee(name=normalized_name, user_id=user_id)
    db.add(payee)
    await db.commit()
    await db.refresh(payee)
    return payee
