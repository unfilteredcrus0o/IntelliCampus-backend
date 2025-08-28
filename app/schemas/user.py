from pydantic import BaseModel, EmailStr
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    employee = "employee"
    manager = "manager"
    superadmin = "superadmin"

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.employee

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