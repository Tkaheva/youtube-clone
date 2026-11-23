from uuid import UUID

from pydantic import BaseModel

from app.models.reaction import ReactionTarget, ReactionType


class ReactionBase(BaseModel):
    target_type: ReactionTarget
    target_id: UUID
    type: ReactionType


class ReactionCreate(ReactionBase):
    pass


class ReactionResponse(BaseModel):
    id: UUID
    user_id: UUID
    target_type: ReactionTarget
    target_id: UUID
    type: ReactionType

    model_config = {"from_attributes": True}