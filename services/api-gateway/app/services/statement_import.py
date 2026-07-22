import aiofiles
from app.db.models import Account, Payee, Statement, Transaction
from app.db.models.enums import FileTransferStatus
from app.db.repositories.constants import SEED_USER_ID
from app.db.repositories.payee import get_or_create_payee
from app.schemas.transaction import TransactionCreate
from app.services.csv_column_mappings import get_column_mapping
from app.services.csv_parser import StatementParseError, parse_csv
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


async def import_statement(db: AsyncSession, statement: Statement) -> Statement:

    file_data = None

    if statement.storage_path is not None:
        async with aiofiles.open(statement.storage_path, "rb") as f:
            try:
                file_data = parse_csv(
                    content=await f.read(), mapping=get_column_mapping()
                )
            except StatementParseError as e:
                statement.status = FileTransferStatus.FAILED
                statement.error_message = str(e)
                await db.commit()
                return statement
    else:
        statement.status = FileTransferStatus.FAILED
        statement.error_message = "Storage path is empty"

    result = await db.execute(select(Account).where(Account.id == statement.account_id))
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    transactions = []

    if file_data is not None:
        for row in file_data:
            payee: Payee | None = None
            if row.payee:
                payee = await get_or_create_payee(db, row.payee)

            try:
                data = TransactionCreate(
                    account_id=statement.account_id,
                    envelope_id=None,
                    payee_id=payee.id if payee is not None else None,
                    statement_id=statement.id,
                    amount=row.amount,
                    currency=account.currency,
                    description=row.description,
                    transaction_date=row.transaction_date,
                    cleared=False,
                    categorization_source=None,
                )
            except ValidationError as e:
                statement.status = FileTransferStatus.FAILED
                statement.error_message = str(e)
                await db.commit()
                return statement

            transactions.append(Transaction(**data.model_dump(), user_id=SEED_USER_ID))

        db.add_all(transactions)
        statement.status = FileTransferStatus.PARSED

    try:
        await db.commit()
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Error while importing statement",
        )

    return statement
