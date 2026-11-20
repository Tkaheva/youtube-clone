import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class UserCreate(BaseModel):
    email: EmailStr = Field(..., max_length=255, example="user@example.com")
    username: str = Field(..., min_length=3, max_length=50, example="john_doe")
    password: str = Field(..., min_length=8, max_length=128, example="secret123")


class UserLogin(BaseModel):
    email: EmailStr = Field(..., example="user@example.com")
    password: str = Field(..., example="secret123")


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    avatar_url: Optional[str] = None
    bio: Optional[str] = None