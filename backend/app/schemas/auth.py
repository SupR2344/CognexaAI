"""Pydantic Schemas for Authentication and User Management."""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Schema for registering a new user."""

    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(..., min_length=6, description="Raw password (will be hashed)")


class UserLogin(BaseModel):
    """Schema for JSON-based user login."""

    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="User password")


class UserResponse(BaseModel):
    """Schema for public user profile responses."""

    id: uuid.UUID
    username: str
    email: EmailStr
    is_active: bool = True
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """OAuth2 access token response."""

    access_token: str
    token_type: str = "bearer"
    user: Optional[UserResponse] = None

    model_config = ConfigDict(from_attributes=True)


class TokenData(BaseModel):
    """Payload data decoded from access token."""

    username: Optional[str] = None
