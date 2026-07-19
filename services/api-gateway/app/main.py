import logging
import uuid
from contextlib import asynccontextmanager

from app.core.logging import setup_logging
from app.db.repositories import (
    create_account,
    delete_account,
    get_accounts,
    update_account,
)
from app.db.session import engine, get_db
from app.schemas import AccountCreate, AccountDelete, AccountRead, AccountUpdate
from fastapi import APIRouter, Depends, FastAPI, status
from sqlalchemy.ext.asyncio import AsyncSession

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Starting Envelo API Gateway")
    yield
    logger.info("Shutting down Envelo API Gateway")
    await engine.dispose()


app = FastAPI(title="Envelo API Gateway", lifespan=lifespan)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


budget_router = APIRouter(prefix="/budget", tags=["Budget"])


@budget_router.get(
    "/accounts",
    summary="List of all accounts",
    status_code=status.HTTP_200_OK,
    response_model=list[AccountRead],
)
async def get_accounts_v1(db: AsyncSession = Depends(get_db)):
    return await get_accounts(db)


@budget_router.delete(
    "/accounts/{accountId}",
    summary="Delete account",
    status_code=status.HTTP_200_OK,
    response_model=AccountDelete,
)
async def delete_account_v1(accountId: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await delete_account(db, accountId)


@budget_router.put(
    "/accounts/{accountId}",
    summary="Update account",
    status_code=status.HTTP_200_OK,
    response_model=AccountUpdate,
)
async def update_account_v1(
    data: AccountUpdate, accountId: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    return await update_account(db, accountId, data)


@budget_router.post(
    "/accounts",
    summary="Create account",
    status_code=status.HTTP_201_CREATED,
    response_model=AccountRead,
)
async def create_account_v1(data: AccountCreate, db: AsyncSession = Depends(get_db)):
    return await create_account(db, data)


app.include_router(budget_router)
