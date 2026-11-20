from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.video import VideoStatus, VideoVisibility


class VideoUpload(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, example="My First Video")
    description: Optional[str] = Field(None, example="A short description")
    visibility: VideoVisibility = Field(default=VideoVisibility.public)


class VideoResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    s3_key: str
    thumbnail_s3_key: Optional[str]
    duration_seconds: Optional[int]
    views_count: int
    status: VideoStatus
    visibility: VideoVisibility
    author_id: UUID
    author_username: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VideoListResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    s3_key: str
    thumbnail_s3_key: Optional[str]
    status: VideoStatus
    visibility: VideoVisibility
    author_id: UUID
    author_username: str
    created_at: datetime

    model_config = {"from_attributes": True}