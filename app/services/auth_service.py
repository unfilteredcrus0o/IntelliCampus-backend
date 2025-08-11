# ------------------------------------------
# Authentication service functions
# - register_user() : Creates a new user with hashed password
# - authenticate_user() : Verifies credentials and returns JWT token
# Works with SQLAlchemy DB session and security utilities
# ------------------------------------------

from sqlalchemy.orm import Session
from datetime import timedelta
from app.models.user import User
from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.config import ACCESS_TOKEN_EXPIRE_MINUTES

def register_user(db: Session, name: str, email: str, password: str):
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise Exception("Email already registered")
    hashed_password = get_password_hash(password)
    new_user = User(name=name, email=email, password_hash=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

def authenticate_user(db: Session, email: str, password: str):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return token
