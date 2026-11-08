import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from app.db.models import CategorizationSource, Envelope, Payee, Transaction
from app.db.repositories.account import get_owned_account
from app.db.repositories.envelope import get_owned_envelope
from app.db.repositories.payee import get_owned_payee
from app.db.repositories.statement import get_owned_statement
from app.schemas.transaction import TransactionCreate, TransactionUpdate
from fastapi import HTTPException
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


def _as_amount(text: str) -> Decimal | None:
    """`"42,50"` / `"42.50"` -> `Decimal("42.50")`, or `None` if it is not a
    number. Lets a free-text search match on amount as well as on words."""
    try:
        return Decimal(text.replace(" ", "").replace("\xa0", "").replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _filtered_transactions(
    query,
    user_id: uuid.UUID,
    accountId: uuid.UUID | None,
    envelopeId: uuid.UUID | None,
    categoryGroupId: uuid.UUID | None,
    dateFrom: date | None,
    dateTo: date | None,
    q: str | None = None,
):
    """Apply the list filters to a query.

    Shared by `get_transactions` and `count_transactions` so the page and the
    total it is counted against can never be built from different criteria -
    a paginated list whose count disagrees with its rows is worse than no count.

    The user filter lives here for the same reason: neither the page nor its
    count can be built without it.
    """
    query = query.where(Transaction.user_id == user_id)

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

    if q and q.strip():
        # Free-text search across the columns a person actually reads in the
        # table. An OUTER join to Payee, because `payee_id` is nullable and an
        # inner join would silently drop every uncategorised row from the
        # results - including from the count.
        needle = f"%{q.strip()}%"
        matches = [Transaction.description.ilike(needle), Payee.name.ilike(needle)]
        amount = _as_amount(q)
        if amount is not None:
            # Compared as an absolute value: the table shows "−42,50 zł", and
            # nobody types the minus when searching for a payment.
            matches.append(func.abs(Transaction.amount) == abs(amount))
        query = query.outerjoin(Payee, Transaction.payee_id == Payee.id).where(or_(*matches))

    return query


async def get_transactions(
    db: AsyncSession,
    user_id: uuid.UUID,
    accountId: uuid.UUID | None = None,
    envelopeId: uuid.UUID | None = None,
    categoryGroupId: uuid.UUID | None = None,
    dateFrom: date | None = None,
    dateTo: date | None = None,
    q: str | None = None,
    skip: int = 0,
    limit: int = 100,
):
    """One page of transactions, newest first.

    Returns an empty list when nothing matches - not a 404. This endpoint answers
    "which transactions match these filters", and "none" is a valid answer to
    that; a 404 made an empty month indistinguishable from a broken request, and
    made the last page of a paginated list an error.
    """
    query = _filtered_transactions(
        select(Transaction), user_id, accountId, envelopeId, categoryGroupId, dateFrom, dateTo, q
    )

    # Newest first, with the id as a tiebreaker. Without an ORDER BY the rows a
    # LIMIT returns are whatever the planner produced, so "the latest 100" was
    # really "an arbitrary 100" and paging through `skip` could repeat or skip
    # rows between requests.
    query = query.order_by(Transaction.transaction_date.desc(), Transaction.id.desc())

    result = await db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()


async def count_transactions(
    db: AsyncSession,
    user_id: uuid.UUID,
    accountId: uuid.UUID | None = None,
    envelopeId: uuid.UUID | None = None,
    categoryGroupId: uuid.UUID | None = None,
    dateFrom: date | None = None,
    dateTo: date | None = None,
    q: str | None = None,
) -> int:
    """How many transactions match, ignoring `skip`/`limit`.

    Surfaced as the `X-Total-Count` header so a client can page and say how much
    it is not showing. Without it the Transactions screen had no way to tell a
    full page from the end of the data, and reported "100 of 100" while 410
    matched.
    """
    query = _filtered_transactions(
        select(func.count()).select_from(Transaction),
        user_id,
        accountId,
        envelopeId,
        categoryGroupId,
        dateFrom,
        dateTo,
        q,
    )
    return await db.scalar(query) or 0


async def get_spent_by_envelope(
    db: AsyncSession,
    user_id: uuid.UUID,
    dateFrom: date | None = None,
    dateTo: date | None = None,
):
    """Money out per envelope over a period, aggregated in SQL.

    Exists because the screens that show "spent" (Envelopes, Dashboard, the
    sidebar totals) used to fetch the raw transactions and sum them client-side -
    which silently went wrong the moment a period held more rows than
    `get_transactions`'s limit, and got slower the more history there was. An
    aggregate is correct regardless of how the list is paged.

    Only negative amounts count: income is not spending, and letting it net off
    would make an envelope look like it had room it does not have. Unlike
    `get_transactions` above, an empty result is an empty list, not a 404 - a
    month with no spending is a real answer, not a missing resource.
    """
    spent = func.sum(-Transaction.amount).label("spent")
    query = (
        select(Transaction.envelope_id, spent)
        .where(Transaction.user_id == user_id, Transaction.amount < 0, Transaction.envelope_id.is_not(None))
        .group_by(Transaction.envelope_id)
    )

    if dateFrom is not None:
        query = query.where(Transaction.transaction_date >= dateFrom)
    if dateTo is not None:
        query = query.where(Transaction.transaction_date <= dateTo)

    result = await db.execute(query)
    return [{"envelope_id": envelope_id, "spent": total} for envelope_id, total in result.all()]


async def _check_references(db: AsyncSession, user_id: uuid.UUID, values: dict) -> None:
    """404 unless every account/envelope/payee/statement id in `values` is the
    user's.

    The foreign keys only prove a row exists, not whose it is - without this a
    user who learned another's envelope id could file their own spending into it
    and quietly drain someone else's budget.
    """
    if values.get("account_id") is not None:
        await get_owned_account(db, user_id, values["account_id"])
    if values.get("envelope_id") is not None:
        await get_owned_envelope(db, user_id, values["envelope_id"])
    if values.get("payee_id") is not None:
        await get_owned_payee(db, user_id, values["payee_id"])
    if values.get("statement_id") is not None:
        await get_owned_statement(db, user_id, values["statement_id"])


async def get_owned_transaction(db: AsyncSession, user_id: uuid.UUID, transaction_id: uuid.UUID) -> Transaction:
    result = await db.execute(
        select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user_id)
    )
    transaction = result.scalar_one_or_none()
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


async def create_transaction(db: AsyncSession, user_id: uuid.UUID, data: TransactionCreate):
    await _check_references(db, user_id, data.model_dump())
    transaction = Transaction(**data.model_dump(), user_id=user_id)
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


async def update_transaction(db: AsyncSession, user_id: uuid.UUID, transactionId: uuid.UUID, data: TransactionUpdate):
    transaction = await get_owned_transaction(db, user_id, transactionId)

    values = data.model_dump(exclude_unset=True)
    await _check_references(db, user_id, values)
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


async def delete_transaction(db: AsyncSession, user_id: uuid.UUID, transactionId: uuid.UUID):
    transaction = await get_owned_transaction(db, user_id, transactionId)

    await db.execute(delete(Transaction).where(Transaction.id == transactionId))
    await db.commit()

    return transaction
