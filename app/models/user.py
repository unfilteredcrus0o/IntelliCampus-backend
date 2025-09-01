# ------------------------------------------
# SQLAlchemy User model definition
# Represents registered application users
# - Stores auto-incrementing integer ID as primary key
# - Tracks name, email, hashed password, and creation timestamp
# ------------------------------------------

from sqlalchemy import Column, String, TIMESTAMP, Text, Boolean, ForeignKey, Enum, Integer
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from app.db.database import Base

class UserRole(enum.Enum):
    employee = "employee"
    manager = "manager"
    superadmin = "superadmin"

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.employee)
    manager_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))
    
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    
    manager = relationship("User", remote_side=[id], back_populates="employees")
    employees = relationship("User", back_populates="manager")

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(Text, nullable=False)
    expires_at = Column(TIMESTAMP, nullable=False)
    is_revoked = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="refresh_tokens")
