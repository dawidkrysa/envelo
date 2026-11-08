import aiofiles
from app.db.models import Account, Payee, Statement, Transaction
from app.db.models.enums import CategorizationSource, FileTransferStatus
from app.db.repositories.categorization_rule import match_envelope_for_transaction
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
    """Parse a stored statement file into transactions for the statement's owner.

    Everything is done as `statement.user_id`: the payees it finds or creates, the
    rules and payee history that file its rows, and the transactions themselves.
    No request is involved by the time this runs, so the owner comes from the
    statement row rather than from a token.
    """
    user_id = statement.user_id

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

    result = await db.execute(select(Account).where(Account.id == statement.account_id, Account.user_id == user_id))
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    transactions = []

    if file_data is not None:
        for row in file_data:
            payee: Payee | None = None
            if row.payee:
                payee = await get_or_create_payee(db, user_id, row.payee)

            payee_id = payee.id if payee is not None else None
            # The payee's name, not the description: rules match on who was paid
            # (see `match_envelope_for_transaction`). A row whose CSV carried no
            # payee therefore matches no rule and stays uncategorized.
            envelope_id = await match_envelope_for_transaction(
                db, user_id, payee_id, payee.name if payee is not None else None
            )

            try:
                data = TransactionCreate(
                    account_id=statement.account_id,
                    envelope_id=envelope_id,
                    payee_id=payee_id,
                    statement_id=statement.id,
                    amount=row.amount,
                    currency=account.currency,
                    description=row.description,
                    transaction_date=row.transaction_date,
                    cleared=False,
                    categorization_source=(
                        CategorizationSource.RULE if envelope_id is not None else None
                    ),
                )
            except ValidationError as e:
                statement.status = FileTransferStatus.FAILED
                statement.error_message = str(e)
                await db.commit()
                return statement

            transactions.append(Transaction(**data.model_dump(), user_id=user_id))

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
