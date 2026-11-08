import os
import uuid

import aiofiles
from app.core.config import get_settings
from app.db.models import FileFormat, FileTransferStatus, Statement
from app.db.repositories.account import get_owned_account
from app.schemas.statement import StatementCreate, StatementUpdate
from app.services.statement_import import import_statement
from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


async def get_statements(db: AsyncSession, user_id: uuid.UUID, accountId: uuid.UUID | None = None):
    query = select(Statement).where(Statement.user_id == user_id)
    if accountId is not None:
        query = query.where(Statement.account_id == accountId)

    statements = (await db.execute(query)).scalars().all()
    if not statements:
        raise HTTPException(status_code=404, detail="Statements not found")
    return statements


async def get_owned_statement(db: AsyncSession, user_id: uuid.UUID, statement_id: uuid.UUID) -> Statement:
    """The user's statement, or 404 - also when it exists but is someone else's."""
    result = await db.execute(select(Statement).where(Statement.id == statement_id, Statement.user_id == user_id))
    statement = result.scalar_one_or_none()
    if statement is None:
        raise HTTPException(status_code=404, detail="Statement not found")
    return statement


async def delete_statement(db: AsyncSession, user_id: uuid.UUID, statementId: uuid.UUID):
    statement = await get_owned_statement(db, user_id, statementId)

    try:
        await db.execute(delete(Statement).where(Statement.id == statementId))
        await db.commit()
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete statement: it still has associated transactions. Remove or reassign those transactions first.",
        )

    return statement


async def update_statement(db: AsyncSession, user_id: uuid.UUID, statementId: uuid.UUID, data: StatementUpdate):
    statement = await get_owned_statement(db, user_id, statementId)

    values = data.model_dump(exclude_unset=True)
    if values.get("account_id") is not None:
        await get_owned_account(db, user_id, values["account_id"])
    if values:
        await db.execute(
            update(Statement).where(Statement.id == statementId).values(**values)
        )
        await db.commit()
        await db.refresh(statement)
    return statement


async def create_statement(db: AsyncSession, user_id: uuid.UUID, data: StatementCreate):
    await get_owned_account(db, user_id, data.account_id)

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
        user_id=user_id,
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
