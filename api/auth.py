# ------------------------------------------
# Authentication API routes (FastAPI)
# - /auth/register : Registers a new user
# - /auth/login    : Authenticates user and returns JWT tokens (access + refresh)
# - /auth/refresh  : Refreshes access token using refresh token
# - /auth/logout   : Revokes refresh token (optional)
# Uses dependency-injected DB session via get_db()
# ------------------------------------------

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.schemas.user import UserCreate, UserLogin, LoginResponse, RefreshTokenRequest, RefreshTokenResponse
from app.services.auth_service import register_user, authenticate_user, refresh_user_token
from app.core.security import revoke_refresh_token, get_current_user
from app.db.database import get_db
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    try:
        register_user(db, user.name, user.email, user.password)
        return {"message": "User registered successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login", response_model=LoginResponse)
def login(user: UserLogin, db: Session = Depends(get_db)):
    tokens = authenticate_user(db, user.email, user.password)
    if not tokens:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return tokens

@router.post("/refresh", response_model=RefreshTokenResponse)
def refresh_token(
    request: RefreshTokenRequest, 
    db: Session = Depends(get_db)
):
    tokens = refresh_user_token(db, request.refresh_token)
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    return tokens

@router.post("/logout")
def logout(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    success = revoke_refresh_token(db, request.refresh_token)
    if success:
        return {"message": "Successfully logged out"}
    else:
        return {"message": "Logout completed"}
