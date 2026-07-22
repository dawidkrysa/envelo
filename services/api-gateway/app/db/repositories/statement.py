import os
import uuid

import aiofiles
from app.core.config import get_settings
from app.db.models import Account, FileFormat, FileTransferStatus, Statement
from app.db.repositories.constants import SEED_USER_ID
from app.schemas.statement import StatementCreate, StatementUpdate
from app.services.statement_import import import_statement
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
    result = await db.execute(select(Account).where(Account.id == data.account_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Account not found")

    filename = data.file.filename or ""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    settings = get_settings()
    allowed_formats = {
        fmt.strip().lower() for fmt in settings.allowed_statement_formats.split(",")
    }
    if extension not in allowed_formats:
        raise HTTPException(
            status_code=400, detail=f"Unsupported file format: '{extension}'"
        )

    try:
        file_format = FileFormat(extension)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Unsupported file format: '{extension}'"
        )

    content = await data.file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum allowed size of {settings.max_upload_size_bytes} bytes",
        )

    statement_id = uuid.uuid4()
    os.makedirs(settings.statement_upload_dir, exist_ok=True)
    storage_path = os.path.join(
        settings.statement_upload_dir, f"{statement_id}.{extension}"
    )
    async with aiofiles.open(storage_path, "wb") as f:
        await f.write(content)

    statement = Statement(
        id=statement_id,
        user_id=SEED_USER_ID,
        account_id=data.account_id,
        filename=filename,
        format=file_format,
        status=FileTransferStatus.PENDING,
        storage_path=storage_path,
        size_bytes=len(content),
    )
    db.add(statement)
    await db.commit()
    await db.refresh(statement)
    statement = await import_statement(db, statement)
    return statement
