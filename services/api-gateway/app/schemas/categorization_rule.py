import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CategorizationRuleRead(BaseModel):
    id: uuid.UUID
    envelope_id: uuid.UUID
    phrase: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CategorizationRuleCreate(BaseModel):
    envelope_id: uuid.UUID
    phrase: str

    model_config = ConfigDict(from_attributes=True)


class CategorizationRuleUpdate(BaseModel):
    envelope_id: uuid.UUID | None = None
    phrase: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CategorizationRuleDelete(BaseModel):
    id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)
