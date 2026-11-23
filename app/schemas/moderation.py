from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.complaint import ComplaintReason, ComplaintStatus, ComplaintTargetType


class ComplaintCreate(BaseModel):
    target_type: ComplaintTargetType
    target_id: UUID
    reason: ComplaintReason
    description: Optional[str] = Field(None, max_length=2000)


class ComplaintResponse(BaseModel):
    id: UUID
    reporter_id: UUID
    target_type: ComplaintTargetType
    target_id: UUID
    reason: ComplaintReason
    description: Optional[str]
    status: ComplaintStatus
    moderator_id: Optional[UUID]
    reviewed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VideoHideRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=1000)