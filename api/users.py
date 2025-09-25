from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.database import get_db
from app.models.user import User, UserRole as ModelUserRole
from app.schemas.user import UserResponse
from app.core.security import require_manager_or_superadmin, get_current_user

router = APIRouter(prefix="/api/users", tags=["Users"])

@router.get("/managers", response_model=List[dict])
def get_available_managers(db: Session = Depends(get_db)):

    managers = db.query(User).filter(User.role == ModelUserRole.manager).all()
    
    return [
        {
            "id": manager.id,
            "name": manager.name,
            "email": manager.email,
            "image_url": manager.image_url,
            "employee_count": db.query(User).filter(User.manager_id == manager.id).count()
        }
        for manager in managers
    ]

@router.get("/", response_model=List[UserResponse])
def get_employees_for_assignment(
    role: Optional[str] = Query(None, description="Filter by role"),
    manager_id: Optional[str] = Query(None, description="Filter by manager ID (string)"),
    include_all: Optional[bool] = Query(False, description="Include all users (superadmin only)")
    ,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_superadmin)
):


    role_filter: Optional[ModelUserRole] = None
    if role:
        try:
            role_filter = ModelUserRole(role)
        except ValueError:
            role_filter = None
    
    if current_user.role == ModelUserRole.superadmin:
        query = db.query(User)
        if role_filter is not None:
            query = query.filter(User.role == role_filter)
        elif not include_all:
            query = query.filter(User.role == ModelUserRole.employee)
        if manager_id is not None:
            query = query.filter(User.manager_id == manager_id)
    elif current_user.role == ModelUserRole.manager:
        if include_all:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only superadmins can access all users"
            )
        query = db.query(User).filter(
            User.role == ModelUserRole.employee,
            User.manager_id == current_user.id
        )
        if role_filter is not None:
            query = query.filter(User.role == role_filter)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges"
        )
    
    employees = query.all()
    return employees

@router.get("/all-for-assignment")
def get_all_users_for_assignment(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != ModelUserRole.superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superadmins can access all users for assignment"
        )
    
    users = db.query(User).filter(User.role != ModelUserRole.superadmin).all()
    
    return {
        "total_users": len(users),
        "users": [
            {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role.value,
                "image_url": user.image_url
            }
            for user in users
        ]
    }