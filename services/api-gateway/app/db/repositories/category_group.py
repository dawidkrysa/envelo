import uuid

from app.db.models import CategoryGroup
from app.db.repositories.constants import SEED_USER_ID
from app.schemas.category_group import CategoryGroupCreate, CategoryGroupUpdate
from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


async def get_category_groups(db: AsyncSession, skip: int = 0, limit: int = 100):
    result = await db.execute(select(CategoryGroup).offset(skip).limit(limit))
    category_groups = result.scalars().all()
    if not category_groups:
        raise HTTPException(status_code=404, detail="Category group not found")
    return category_groups


async def delete_category_group(db: AsyncSession, categoryGroupId: uuid.UUID):
    result = await db.execute(
        select(CategoryGroup).where(CategoryGroup.id == categoryGroupId)
    )
    category_group = result.scalar_one_or_none()
    if category_group is None:
        raise HTTPException(status_code=404, detail="Category group not found")

    try:
        await db.execute(
            delete(CategoryGroup).where(CategoryGroup.id == categoryGroupId)
        )
        await db.commit()
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete category group: it still has associated envelopes. Move or delete those envelopes first.",
        )

    return category_group


async def update_category_group(
    db: AsyncSession, categoryGroupId: uuid.UUID, data: CategoryGroupUpdate
):
    result = await db.execute(
        select(CategoryGroup).where(CategoryGroup.id == categoryGroupId)
    )
    category_group = result.scalar_one_or_none()
    if category_group is None:
        raise HTTPException(status_code=404, detail="Category group not found")

    values = data.model_dump(exclude_unset=True)
    if values:
        await db.execute(
            update(CategoryGroup)
            .where(CategoryGroup.id == categoryGroupId)
            .values(**values)
        )
        await db.commit()
        await db.refresh(category_group)
    return category_group


async def create_category_group(db: AsyncSession, data: CategoryGroupCreate):
    category_group = CategoryGroup(**data.model_dump(), user_id=SEED_USER_ID)
    db.add(category_group)
    await db.commit()
    await db.refresh(category_group)
    return category_group
