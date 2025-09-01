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
            "employee_count": db.query(User).filter(User.manager_id == manager.id).count()
        }
        for manager in managers
    ]

@router.get("/", response_model=List[UserResponse])
def get_employees_for_assignment(
    role: Optional[str] = Query(None, description="Filter by role"),
    manager_id: Optional[str] = Query(None, description="Filter by manager ID (string)")
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
        else:
            query = query.filter(User.role == ModelUserRole.employee)
        if manager_id is not None:
            query = query.filter(User.manager_id == manager_id)
    elif current_user.role == ModelUserRole.manager:
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