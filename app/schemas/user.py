from pydantic import BaseModel, EmailStr
from datetime import datetime
from enum import Enum
from typing import Optional

class UserRole(str, Enum):
    employee = "employee"
    manager = "manager"
    superadmin = "superadmin"

class UserCreate(BaseModel):
    user_id: str
    name: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.employee
    manager_id: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class UserInfo(BaseModel):
    id: str
    email: str
    name: str
    role: UserRole

class RefreshTokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: UserInfo

class UserProfile(BaseModel):
    id: str
    name: str
    email: str
    role: UserRole
    
    class Config:
        from_attributes = True

class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    manager_id: Optional[str] = None

    class Config:
        from_attributes = True