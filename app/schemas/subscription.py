from uuid import UUID

from pydantic import BaseModel


class SubscriptionResponse(BaseModel):
    id: UUID
    subscriber_id: UUID
    channel_id: UUID
    is_active: bool

    model_config = {"from_attributes": True}


class SubscriptionStatus(BaseModel):
    subscribed: bool
    is_active: bool