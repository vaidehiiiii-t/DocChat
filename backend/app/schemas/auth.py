from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, description="Password must be at least 8 characters long")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class UserResponse(BaseModel):
    id: int
    name: Optional[str]
    email: str
    created_at: Optional[str]
