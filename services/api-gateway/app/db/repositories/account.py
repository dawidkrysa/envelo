import uuid
from decimal import Decimal

from app.db.models import Account, Statement, Transaction
from app.schemas.account import AccountCreate, AccountUpdate
from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


async def get_accounts(db: AsyncSession, user_id: uuid.UUID, skip: int = 0, limit: int = 100):
    result = await db.execute(select(Account).where(Account.user_id == user_id).offset(skip).limit(limit))
    accounts = result.scalars().all()
    if not accounts:
        raise HTTPException(status_code=404, detail="Accounts not found")
    return accounts


async def get_account_balances(db: AsyncSession, user_id: uuid.UUID):
    """Where each account actually stands: its cash balance, how many
    transactions are behind it, and when it was last imported into.

    An aggregate rather than three fields on `AccountRead`, for the same reason
    `spent-by-envelope` exists: the alternative is fetching every transaction and
    summing client-side, which is silently wrong the moment an account holds more
    rows than one page - and `GET /budget/transactions` caps at 100.

    Every account is listed, including ones nothing has ever touched: a new
    account with a balance of 0,00 is a real answer, and leaving it out would
    make the screen's account list disagree with `GET /budget/accounts`.

    `last_imported_at` comes from the account's newest statement and is `None`
    for an account whose transactions were all entered by hand.
    """
    accounts = (
        (await db.execute(select(Account).where(Account.user_id == user_id).order_by(Account.name))).scalars().all()
    )

    totals = {
        account_id: (balance, count)
        for account_id, balance, count in (
            await db.execute(
                select(
                    Transaction.account_id,
                    func.sum(Transaction.amount),
                    func.count(Transaction.id),
                )
                .where(Transaction.user_id == user_id)
                .group_by(Transaction.account_id)
            )
        ).all()
    }

    last_imports = {
        account_id: imported_at
        for account_id, imported_at in (
            await db.execute(
                select(Statement.account_id, func.max(Statement.imported_at))
                .where(Statement.user_id == user_id)
                .group_by(Statement.account_id)
            )
        ).all()
    }

    return [
        {
            "account_id": account.id,
            "balance": totals.get(account.id, (Decimal("0"), 0))[0],
            "transaction_count": totals.get(account.id, (Decimal("0"), 0))[1],
            "last_imported_at": last_imports.get(account.id),
        }
        for account in accounts
    ]


async def get_owned_account(db: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID) -> Account:
    result = await db.execute(select(Account).where(Account.id == account_id, Account.user_id == user_id))
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


async def delete_account(db: AsyncSession, user_id: uuid.UUID, accountId: uuid.UUID):
    account = await get_owned_account(db, user_id, accountId)

    try:
        await db.execute(delete(Account).where(Account.id == accountId))
        await db.commit()
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete account: it still has associated statements or transactions. Archive the account instead, or remove its transaction history first.",
        )

    return account


async def update_account(db: AsyncSession, user_id: uuid.UUID, accountId: uuid.UUID, data: AccountUpdate):
    account = await get_owned_account(db, user_id, accountId)

    values = data.model_dump(exclude_unset=True)
    if values:
        await db.execute(update(Account).where(Account.id == accountId).values(**values))
        await db.commit()
        await db.refresh(account)
    return account


async def create_account(db: AsyncSession, user_id: uuid.UUID, data: AccountCreate):
    account = Account(**data.model_dump(), user_id=user_id)
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account
