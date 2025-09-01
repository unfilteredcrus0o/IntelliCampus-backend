"""
Assignment Management API
========================
Provides endpoints for bulk roadmap assignment functionality.

Features:
- Bulk assignment of roadmaps to multiple users
- Assignment validation and duplicate prevention  
- Comprehensive error handling with detailed feedback
- Audit logging for assignment tracking

"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict
from app.db.database import get_db
from app.models.user import User
from app.models.roadmap import Assignment, Roadmap
from app.services.roadmap_service import auto_enroll_user_in_roadmap
from app.schemas.roadmap import AssignmentCreate, BulkAssignmentResponse, AssignmentResponse
from app.core.security import get_current_user
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Assignments"])

def _parse_due_date(date_string: str) -> datetime:

    if not date_string:
        logger.debug("No due date provided, returning None")
        return None
    
    for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"]:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    
    try:
        parsed_date = datetime.fromisoformat(date_string)
        logger.debug(f"Successfully parsed due date: {parsed_date}")
        return parsed_date
    except ValueError as e:
        logger.warning(f"Failed to parse due date '{date_string}': {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid due_date format. Use YYYY-MM-DD or ISO format"
        )

def _create_single_assignment(db: Session, roadmap_id: int, assigned_by: str, assigned_to: str, due_date: datetime) -> Assignment:
    logger.info(f"Creating assignment: roadmap_id={roadmap_id}, assigned_by={assigned_by}, assigned_to={assigned_to}, due_date={due_date}")
    
    assignment = Assignment(
        roadmap_id=roadmap_id,
        assigned_by=assigned_by,
        assigned_to=assigned_to,
        due_date=due_date,
        created_at=datetime.now(timezone.utc)
    )
    db.add(assignment)
    db.flush()
    
    logger.info(f"Assignment created successfully with ID: {assignment.id}")
    return assignment

def _build_assignment_response(assignments_created: List[Assignment], assignments_failed: List[Dict]) -> BulkAssignmentResponse:
    success_count = len(assignments_created)
    failed_count = len(assignments_failed)
    
    logger.debug(f"Building assignment response: {success_count} successful, {failed_count} failed")
    
    if success_count == 0:
        logger.warning(f"All assignments failed: {failed_count} failures")
        return BulkAssignmentResponse(
            success=False,
            message=f"No assignments created. {failed_count} failed.",
            created_assignments=[],
            failed_assignments=assignments_failed
        )
    
    success_status = failed_count == 0
    message = (f"Successfully created {success_count} assignments" if success_status 
               else f"Created {success_count} assignments, {failed_count} failed")
    
    if success_status:
        logger.info(f"All assignments successful: {success_count} created")
    else:
        logger.warning(f"Partial success: {success_count} created, {failed_count} failed")
    
    return BulkAssignmentResponse(
        success=success_status,
        message=message,
        created_assignments=[AssignmentResponse(
            id=a.id, roadmap_id=a.roadmap_id, assigned_by=a.assigned_by,
            assigned_to=a.assigned_to, due_date=a.due_date, created_at=a.created_at
        ) for a in assignments_created],
        failed_assignments=assignments_failed
    )

@router.post("/assignments", response_model=BulkAssignmentResponse)
def create_assignments(
    assignment_data: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    logger.info(f"Bulk assignment request initiated by user {current_user.id} for roadmap {assignment_data.roadmap_id}")
    logger.info(f"Target users: {assignment_data.assigned_to}, Due date: {assignment_data.due_date}")
    
    roadmap = db.query(Roadmap).filter(Roadmap.id == assignment_data.roadmap_id).first()
    if not roadmap:
        logger.warning(f"Assignment failed: Roadmap {assignment_data.roadmap_id} not found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Roadmap not found")
    
    logger.info(f"Roadmap validated: {roadmap.title}")
    
    due_date = _parse_due_date(assignment_data.due_date)
    created_assignments = []
    failed_assignments = []
    logger.info(f"Processing {len(assignment_data.assigned_to)} user assignments")
    
    try:
        for user_id in assignment_data.assigned_to:
            try:
                logger.debug(f"Processing assignment for user: {user_id}")
                
                user = db.query(User).filter(User.id == user_id).first()
                if not user:
                    logger.warning(f"User {user_id} not found, skipping assignment")
                    failed_assignments.append({"user_id": user_id, "error": "User not found"})
                    continue
                
                existing_assignment = db.query(Assignment).filter(
                    Assignment.roadmap_id == assignment_data.roadmap_id,
                    Assignment.assigned_to == user_id
                ).first()
                if existing_assignment:
                    logger.warning(f"Duplicate assignment detected for user {user_id} and roadmap {assignment_data.roadmap_id}")
                    failed_assignments.append({"user_id": user_id, "error": "Assignment already exists"})
                    continue
                
                assignment = _create_single_assignment(
                    db, assignment_data.roadmap_id, current_user.id, user_id, due_date
                )
                created_assignments.append(assignment)
                
                logger.debug(f"Auto-enrolling user {user_id} in roadmap {assignment_data.roadmap_id}")
                auto_enroll_user_in_roadmap(db, user_id, assignment_data.roadmap_id)
                
                logger.info(f"Successfully assigned roadmap {assignment_data.roadmap_id} to user {user_id}")
                
            except Exception as e:
                logger.error(f"Failed to create assignment for user {user_id}: {str(e)}")
                failed_assignments.append({"user_id": user_id, "error": str(e)})
        
        db.commit()
        
        success_count = len(created_assignments)
        failure_count = len(failed_assignments)
        logger.info(f"Bulk assignment completed: {success_count} successful, {failure_count} failed")
        
        if success_count > 0:
            logger.info(f"Successfully created assignments: {[a.id for a in created_assignments]}")
        if failure_count > 0:
            logger.warning(f"Failed assignments: {failed_assignments}")
            
        return _build_assignment_response(created_assignments, failed_assignments)
        
    except HTTPException:
        logger.error("HTTPException occurred during bulk assignment, rolling back")
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Unexpected error during bulk assignment: {str(e)}, rolling back")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create assignments: {str(e)}"
        )

@router.get("/assignments/count")
def get_assignments_count(db: Session = Depends(get_db)):
    logger.info("Fetching assignment count statistics")
    from sqlalchemy import func
    
    try:
        total_count = db.query(Assignment).count()
        logger.debug(f"Total assignments count: {total_count}")
        
        assignments_by_user = db.query(
            Assignment.assigned_to,
            func.count(Assignment.id).label('count')
        ).group_by(Assignment.assigned_to).all()
        
        assignments_by_assigner = db.query(
            Assignment.assigned_by,
            func.count(Assignment.id).label('count')
        ).group_by(Assignment.assigned_by).all()
        
        assignments_by_roadmap = db.query(
            Assignment.roadmap_id,
            func.count(Assignment.id).label('count')
        ).group_by(Assignment.roadmap_id).all()
        
        with_due_date = db.query(Assignment).filter(Assignment.due_date.isnot(None)).count()
        without_due_date = total_count - with_due_date
    
        response_data = {
            "total_assignments": total_count,
            "assignments_by_user": [
                {"user_id": user_id, "assignment_count": count} 
                for user_id, count in assignments_by_user
            ],
            "assignments_by_assigner": [
                {"assigner_id": assigner_id, "assignments_created": count}
                for assigner_id, count in assignments_by_assigner  
            ],
            "assignments_by_roadmap": [
                {"roadmap_id": roadmap_id, "assignment_count": count}
                for roadmap_id, count in assignments_by_roadmap
            ],
            "due_date_statistics": {
                "with_due_date": with_due_date,
                "without_due_date": without_due_date
            }
        }
        
        logger.info(f"Assignment statistics retrieved successfully: {total_count} total assignments")
        return response_data
        
    except Exception as e:
        logger.error(f"Error retrieving assignment statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve assignment statistics"
        )

@router.get("/assignments/roadmap/{roadmap_id}/count")
def get_roadmap_assignment_count(
    roadmap_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    logger.info(f"User {current_user.id} requesting assignment count for roadmap {roadmap_id}")
    
    try:
        roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
        if not roadmap:
            logger.warning(f"Roadmap {roadmap_id} not found for assignment count request")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Roadmap not found"
            )
        
        logger.debug(f"Found roadmap: {roadmap.title}")
    
        assignment_count = db.query(Assignment).filter(Assignment.roadmap_id == roadmap_id).count()
        logger.debug(f"Assignment count for roadmap {roadmap_id}: {assignment_count}")
        
        assigners = db.query(Assignment.assigned_by).filter(Assignment.roadmap_id == roadmap_id).distinct().all()
        assignees = db.query(Assignment.assigned_to).filter(Assignment.roadmap_id == roadmap_id).distinct().all()
        
        response_data = {
            "roadmap_id": roadmap_id,
            "roadmap_title": roadmap.title,
            "total_assignments": assignment_count,
            "unique_assigners": len(assigners),
            "unique_assignees": len(assignees),
            "assigners": [assigner[0] for assigner in assigners],
            "assignees": [assignee[0] for assignee in assignees]
        }
        
        logger.info(f"Roadmap assignment statistics retrieved: roadmap={roadmap_id}, assignments={assignment_count}, assigners={len(assigners)}, assignees={len(assignees)}")
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving roadmap assignment count for {roadmap_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve roadmap assignment statistics"
        )
