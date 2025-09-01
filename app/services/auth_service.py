# ------------------------------------------
# Authentication service functions
# - register_user() : Creates a new user with hashed password
# - authenticate_user() : Verifies credentials and returns both access & refresh tokens
# - refresh_user_token() : Generates new access token using refresh token
# Works with SQLAlchemy DB session and security utilities
# ------------------------------------------

from sqlalchemy.orm import Session
from datetime import timedelta
from app.models.user import User, UserRole
from app.core.security import (get_password_hash, verify_password, create_access_token, create_refresh_token, verify_refresh_token)
from app.core.config import ACCESS_TOKEN_EXPIRE_MINUTES

def register_user(db: Session, user_id: str, name: str, email: str, password: str, role: UserRole = UserRole.employee, manager_id: str = None):
    existing_user_by_id = db.query(User).filter(User.id == user_id).first()
    if existing_user_by_id:
        raise Exception("User ID already exists")
    
    existing_user_by_email = db.query(User).filter(User.email == email).first()
    if existing_user_by_email:
        raise Exception("Email already registered")
    
    if manager_id:
        manager = db.query(User).filter(User.id == manager_id).first()
        if not manager:
            raise Exception("Manager ID does not exist")
        if manager.role != UserRole.manager:
            raise Exception("Specified ID is not a manager")
    
    hashed_password = get_password_hash(password)
    new_user = User(id=user_id, name=name, email=email, password_hash=hashed_password, role=role, manager_id=manager_id)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

def authenticate_user(db: Session, email: str, password: str):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    refresh_token = create_refresh_token(db, user.id)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

def refresh_user_token(db: Session, refresh_token: str):

    user = verify_refresh_token(db, refresh_token)
    if not user:
        return None
    
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role.value
        }
    }
