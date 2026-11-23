from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000, example="Отличное видео!")
    parent_id: Optional[UUID] = Field(None, example=None)


class CommentResponse(BaseModel):
    id: UUID
    video_id: UUID
    author_id: UUID
    author_username: str
    parent_id: Optional[UUID]
    content: str
    is_deleted: bool
    is_blocked: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CommentListResponse(BaseModel):
    comments: List[CommentResponse]
    total: int