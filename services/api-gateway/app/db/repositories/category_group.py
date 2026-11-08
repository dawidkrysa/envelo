import uuid

from app.db.models import CategoryGroup
from app.schemas.category_group import CategoryGroupCreate, CategoryGroupUpdate
from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


async def get_category_groups(db: AsyncSession, user_id: uuid.UUID, skip: int = 0, limit: int = 100):
    result = await db.execute(
        select(CategoryGroup).where(CategoryGroup.user_id == user_id).offset(skip).limit(limit)
    )
    category_groups = result.scalars().all()
    if not category_groups:
        raise HTTPException(status_code=404, detail="Category group not found")
    return category_groups


async def get_owned_category_group(
    db: AsyncSession, user_id: uuid.UUID, category_group_id: uuid.UUID
) -> CategoryGroup:
    """The user's category group, or 404 - also when it exists but is someone
    else's, so that a guessed id cannot be confirmed."""
    result = await db.execute(
        select(CategoryGroup).where(CategoryGroup.id == category_group_id, CategoryGroup.user_id == user_id)
    )
    category_group = result.scalar_one_or_none()
    if category_group is None:
        raise HTTPException(status_code=404, detail="Category group not found")
    return category_group


async def delete_category_group(db: AsyncSession, user_id: uuid.UUID, categoryGroupId: uuid.UUID):
    category_group = await get_owned_category_group(db, user_id, categoryGroupId)

    try:
        await db.execute(delete(CategoryGroup).where(CategoryGroup.id == categoryGroupId))
        await db.commit()
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete category group: it still has associated envelopes. Move or delete those envelopes first.",
        )

    return category_group


async def update_category_group(
    db: AsyncSession, user_id: uuid.UUID, categoryGroupId: uuid.UUID, data: CategoryGroupUpdate
):
    category_group = await get_owned_category_group(db, user_id, categoryGroupId)

    values = data.model_dump(exclude_unset=True)
    if values:
        await db.execute(update(CategoryGroup).where(CategoryGroup.id == categoryGroupId).values(**values))
        await db.commit()
        await db.refresh(category_group)
    return category_group


async def create_category_group(db: AsyncSession, user_id: uuid.UUID, data: CategoryGroupCreate):
    category_group = CategoryGroup(**data.model_dump(), user_id=user_id)
    db.add(category_group)
    await db.commit()
    await db.refresh(category_group)
    return category_group
