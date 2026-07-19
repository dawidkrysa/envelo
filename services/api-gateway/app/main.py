import logging
import uuid
from contextlib import asynccontextmanager
from datetime import date

from app import schemas
from app.core.logging import setup_logging
from app.db import repositories as repo
from app.db.session import engine, get_db
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


accounts_router = APIRouter(prefix="/budget/accounts", tags=["Accounts"])
payees_router = APIRouter(prefix="/budget/payees", tags=["Payees"])
category_groups_router = APIRouter(
    prefix="/budget/category-groups", tags=["Category Groups"]
)
envelopes_router = APIRouter(prefix="/budget/envelopes", tags=["Envelopes"])
envelope_allocations_router = APIRouter(
    prefix="/budget/envelope-allocations", tags=["Envelope Allocations"]
)
statements_router = APIRouter(prefix="/budget/statements", tags=["Statements"])
transactions_router = APIRouter(prefix="/budget/transactions", tags=["Transactions"])


# ==============================================================================
# Accounts
# ==============================================================================


# Create
@accounts_router.post(
    "",
    summary="Create account",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.AccountRead,
)
async def create_account_v1(
    data: schemas.AccountCreate, db: AsyncSession = Depends(get_db)
):
    return await repo.create_account(db, data)


# Read
@accounts_router.get(
    "",
    summary="List of all accounts",
    status_code=status.HTTP_200_OK,
    response_model=list[schemas.AccountRead],
)
async def get_accounts_v1(
    skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)
):
    return await repo.get_accounts(db, skip, limit)


# Update
@accounts_router.put(
    "/{accountId}",
    summary="Update account",
    status_code=status.HTTP_200_OK,
    response_model=schemas.AccountUpdate,
)
async def update_account_v1(
    data: schemas.AccountUpdate, accountId: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    return await repo.update_account(db, accountId, data)


# Delete
@accounts_router.delete(
    "/{accountId}",
    summary="Delete account",
    status_code=status.HTTP_200_OK,
    response_model=schemas.AccountDelete,
)
async def delete_account_v1(accountId: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await repo.delete_account(db, accountId)


# ==============================================================================
# Payees
# ==============================================================================


# Create
@payees_router.post(
    "",
    summary="Create payee",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.PayeeRead,
)
async def create_payee_v1(
    data: schemas.PayeeCreate, db: AsyncSession = Depends(get_db)
):
    return await repo.create_payee(db, data)


# Read
@payees_router.get(
    "",
    summary="List of all payees",
    status_code=status.HTTP_200_OK,
    response_model=list[schemas.PayeeRead],
)
async def get_payee_v1(
    skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)
):
    return await repo.get_payees(db, skip, limit)


# Update
@payees_router.put(
    "/{payeeId}",
    summary="Update payee",
    status_code=status.HTTP_200_OK,
    response_model=schemas.PayeeRead,
)
async def update_payee_v1(
    data: schemas.PayeeUpdate, payeeId: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    return await repo.update_payee(db, payeeId, data)


# Delete
@payees_router.delete(
    "/{payeeId}",
    summary="Delete payee",
    status_code=status.HTTP_200_OK,
    response_model=schemas.PayeeDelete,
)
async def delete_payee_v1(payeeId: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await repo.delete_payee(db, payeeId)


# ==============================================================================
# Category Groups
# ==============================================================================


# Create
@category_groups_router.post(
    "",
    summary="Create category group",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.CategoryGroupRead,
)
async def create_category_group_v1(
    data: schemas.CategoryGroupCreate, db: AsyncSession = Depends(get_db)
):
    return await repo.create_category_group(db, data)


# Read
@category_groups_router.get(
    "",
    summary="List of all category groups",
    status_code=status.HTTP_200_OK,
    response_model=list[schemas.CategoryGroupRead],
)
async def get_category_groups_v1(
    skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)
):
    return await repo.get_category_groups(db, skip, limit)


# Update
@category_groups_router.put(
    "/{categoryGroupId}",
    summary="Update category group",
    status_code=status.HTTP_200_OK,
    response_model=schemas.CategoryGroupRead,
)
async def update_category_group_v1(
    data: schemas.CategoryGroupUpdate,
    categoryGroupId: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    return await repo.update_category_group(db, categoryGroupId, data)


# Delete
@category_groups_router.delete(
    "/{categoryGroupId}",
    summary="Delete category group",
    status_code=status.HTTP_200_OK,
    response_model=schemas.CategoryGroupDelete,
)
async def delete_category_group_v1(
    categoryGroupId: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    return await repo.delete_category_group(db, categoryGroupId)


# ==============================================================================
# Envelopes
# ==============================================================================


# Create
@envelopes_router.post(
    "",
    summary="Create envelope",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.EnvelopeRead,
)
async def create_envelope_v1(
    data: schemas.EnvelopeCreate, db: AsyncSession = Depends(get_db)
):
    return await repo.create_envelope(db, data)


# Read
@envelopes_router.get(
    "",
    summary="List of all envelopes",
    status_code=status.HTTP_200_OK,
    response_model=list[schemas.EnvelopeRead],
)
async def get_envelopes_v1(
    categoryGroupId: uuid.UUID | None = None, db: AsyncSession = Depends(get_db)
):
    return await repo.get_envelopes(db, categoryGroupId)


# Update
@envelopes_router.put(
    "/{envelopeId}",
    summary="Update envelope",
    status_code=status.HTTP_200_OK,
    response_model=schemas.EnvelopeRead,
)
async def update_envelope_v1(
    data: schemas.EnvelopeUpdate,
    envelopeId: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    return await repo.update_envelope(db, envelopeId, data)


# Delete
@envelopes_router.delete(
    "/{envelopeId}",
    summary="Delete envelope",
    status_code=status.HTTP_200_OK,
    response_model=schemas.EnvelopeDelete,
)
async def delete_envelope_v1(envelopeId: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await repo.delete_envelope(db, envelopeId)


# ==============================================================================
# Envelope Allocations
# ==============================================================================


# Create
@envelope_allocations_router.post(
    "",
    summary="Create envelope allocation",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.EnvelopeAllocationRead,
)
async def create_envelope_allocation_v1(
    data: schemas.EnvelopeAllocationCreate, db: AsyncSession = Depends(get_db)
):
    return await repo.create_envelope_allocation(db, data)


# Read
@envelope_allocations_router.get(
    "",
    summary="List of all envelope allocations",
    status_code=status.HTTP_200_OK,
    response_model=list[schemas.EnvelopeAllocationRead],
)
async def get_envelope_allocations_v1(
    envelopeId: uuid.UUID | None = None, db: AsyncSession = Depends(get_db)
):
    return await repo.get_envelope_allocations(db, envelopeId)


# Update
@envelope_allocations_router.put(
    "/{envelopeAllocationId}",
    summary="Update envelope allocation",
    status_code=status.HTTP_200_OK,
    response_model=schemas.EnvelopeAllocationRead,
)
async def update_envelope_allocation_v1(
    data: schemas.EnvelopeAllocationUpdate,
    envelopeAllocationId: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    return await repo.update_envelope_allocation(db, envelopeAllocationId, data)


# Move money between two envelope allocations (same month) in one atomic operation
@envelope_allocations_router.post(
    "/transfer",
    summary="Transfer money between two envelope allocations",
    status_code=status.HTTP_200_OK,
    response_model=list[schemas.EnvelopeAllocationRead],
)
async def transfer_envelope_allocation_v1(
    data: schemas.EnvelopeAllocationTransfer, db: AsyncSession = Depends(get_db)
):
    return await repo.transfer_envelope_allocation(db, data)


# ==============================================================================
# Statements
# ==============================================================================


# Create
@statements_router.post(
    "",
    summary="Create statement",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.StatementRead,
)
async def create_statement_v1(
    data: schemas.StatementCreate, db: AsyncSession = Depends(get_db)
):
    return await repo.create_statement(db, data)


# Read
@statements_router.get(
    "",
    summary="List of all statements",
    status_code=status.HTTP_200_OK,
    response_model=list[schemas.StatementRead],
)
async def get_statements_v1(
    accountId: uuid.UUID | None = None, db: AsyncSession = Depends(get_db)
):
    return await repo.get_statements(db, accountId)


# Update
@statements_router.put(
    "/{statementId}",
    summary="Update statement",
    status_code=status.HTTP_200_OK,
    response_model=schemas.StatementRead,
)
async def update_statement_v1(
    data: schemas.StatementUpdate,
    statementId: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    return await repo.update_statement(db, statementId, data)


# Delete
@statements_router.delete(
    "/{statementId}",
    summary="Delete statement",
    status_code=status.HTTP_200_OK,
    response_model=schemas.StatementDelete,
)
async def delete_statement_v1(
    statementId: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    return await repo.delete_statement(db, statementId)


# ==============================================================================
# Transactions
# ==============================================================================


# Create
@transactions_router.post(
    "",
    summary="Create transaction",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.TransactionRead,
)
async def create_transaction_v1(
    data: schemas.TransactionCreate, db: AsyncSession = Depends(get_db)
):
    return await repo.create_transaction(db, data)


# Read
@transactions_router.get(
    "",
    summary="List of all transactions",
    status_code=status.HTTP_200_OK,
    response_model=list[schemas.TransactionRead],
)
async def get_transactions_v1(
    accountId: uuid.UUID | None = None,
    envelopeId: uuid.UUID | None = None,
    categoryGroupId: uuid.UUID | None = None,
    dateFrom: date | None = None,
    dateTo: date | None = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    return await repo.get_transactions(
        db, accountId, envelopeId, categoryGroupId, dateFrom, dateTo, skip, limit
    )


# Update
@transactions_router.put(
    "/{transactionId}",
    summary="Update transaction",
    status_code=status.HTTP_200_OK,
    response_model=schemas.TransactionRead,
)
async def update_transaction_v1(
    data: schemas.TransactionUpdate,
    transactionId: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    return await repo.update_transaction(db, transactionId, data)


# Delete
@transactions_router.delete(
    "/{transactionId}",
    summary="Delete transaction",
    status_code=status.HTTP_200_OK,
    response_model=schemas.TransactionDelete,
)
async def delete_transaction_v1(
    transactionId: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    return await repo.delete_transaction(db, transactionId)


app.include_router(accounts_router)
app.include_router(payees_router)
app.include_router(category_groups_router)
app.include_router(envelopes_router)
app.include_router(envelope_allocations_router)
app.include_router(statements_router)
app.include_router(transactions_router)
