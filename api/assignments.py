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
# Removed auto_enroll_user_in_roadmap import - assignments should not force enrollment
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
                
                logger.info(f"Successfully assigned roadmap {assignment_data.roadmap_id} to user {user_id}")
                logger.debug(f"Assignment created - user can enroll separately if they choose")
                
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

@router.get("/assignments/my")
def get_my_assignments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    logger.info(f"User {current_user.id} requesting their assignments")
    
    try:
        assignment_list = []
        
        # 1. Get assignments TO the user (existing logic)
        assignments = db.query(Assignment).filter(
            Assignment.assigned_to == current_user.id
        ).join(Roadmap, Assignment.roadmap_id == Roadmap.id).all()
        
        logger.debug(f"Found {len(assignments)} assignments TO user {current_user.id}")
        
        for assignment in assignments:
            roadmap = db.query(Roadmap).filter(Roadmap.id == assignment.roadmap_id).first()
            assigner = db.query(User).filter(User.id == assignment.assigned_by).first()
            
            assignment_list.append({
                "assignment_id": assignment.id,
                "roadmap_id": assignment.roadmap_id,
                "roadmap_title": roadmap.title if roadmap else "Unknown Roadmap (Deleted)",
                "assigned_by": assignment.assigned_by,
                "assigner_name": assigner.name if assigner else "Unknown Assigner",
                "due_date": assignment.due_date,
                "assigned_at": assignment.created_at,
                "status": "assigned"
            })
        
        # 2. Get roadmaps CREATED BY the user (new logic for self-created roadmaps)
        created_roadmaps = db.query(Roadmap).filter(
            Roadmap.creator_id == current_user.id
        ).all()
        
        logger.debug(f"Found {len(created_roadmaps)} roadmaps CREATED BY user {current_user.id}")
        
        for roadmap in created_roadmaps:
            # Check if this roadmap is already in the assignment list (to avoid duplicates)
            already_assigned = any(item["roadmap_id"] == roadmap.id for item in assignment_list)
            
            if not already_assigned:
                assignment_list.append({
                    "assignment_id": None,  # No assignment record for self-created
                    "roadmap_id": roadmap.id,
                    "roadmap_title": roadmap.title,
                    "assigned_by": current_user.id,
                    "assigner_name": current_user.name,
                    "due_date": roadmap.end_date,  # Use roadmap's end_date as due_date
                    "assigned_at": roadmap.created_at,
                    "status": "self_created"
                })
        
        response = {
            "user_id": current_user.id,
            "total_assignments": len(assignment_list),
            "assignments": assignment_list
        }
        
        logger.info(f"Successfully retrieved {len(assignment_list)} assignments for user {current_user.id}")
        return response
        
    except Exception as e:
        logger.error(f"Error retrieving assignments for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user assignments"
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

@router.get("/assignments/{assignment_id}")
def get_assignment_details(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    logger.info(f"User {current_user.id} requesting assignment details for {assignment_id}")
    
    try:
        assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if not assignment:
            logger.warning(f"Assignment {assignment_id} not found")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
        
        if (assignment.assigned_by != current_user.id and 
            assignment.assigned_to != current_user.id and 
            current_user.role.value not in ['manager', 'superadmin']):
            logger.warning(f"User {current_user.id} unauthorized to view assignment {assignment_id}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
        
        roadmap = db.query(Roadmap).filter(Roadmap.id == assignment.roadmap_id).first()
        assigner = db.query(User).filter(User.id == assignment.assigned_by).first()
        assignee = db.query(User).filter(User.id == assignment.assigned_to).first()
        
        response = {
            "assignment_id": assignment.id,
            "roadmap": {
                "id": assignment.roadmap_id,
                "title": roadmap.title if roadmap else "Unknown Roadmap (Deleted)"
            },
            "assigned_by": {
                "id": assignment.assigned_by,
                "name": assigner.name if assigner else "Unknown User"
            },
            "assigned_to": {
                "id": assignment.assigned_to,
                "name": assignee.name if assignee else "Unknown User"
            },
            "due_date": assignment.due_date,
            "created_at": assignment.created_at,
            "status": "assigned"
        }
        
        logger.info(f"Assignment details retrieved for {assignment_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving assignment {assignment_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve assignment details"
        )

@router.delete("/assignments/{assignment_id}")
def delete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete/cancel an assignment (managers/superadmins only)"""
    logger.info(f"User {current_user.id} attempting to delete assignment {assignment_id}")
    
    if current_user.role.value not in ['manager', 'superadmin']:
        logger.warning(f"User {current_user.id} unauthorized to delete assignments")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, 
                          detail="Only managers and superadmins can delete assignments")
    
    try:
        assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if not assignment:
            logger.warning(f"Assignment {assignment_id} not found for deletion")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
        
        if (current_user.role.value == 'manager' and 
            assignment.assigned_by != current_user.id):
            logger.warning(f"Manager {current_user.id} cannot delete assignment created by {assignment.assigned_by}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, 
                              detail="Managers can only delete assignments they created")
        
        roadmap_id = assignment.roadmap_id
        assigned_to = assignment.assigned_to
        
        db.delete(assignment)
        db.commit()
        
        logger.info(f"Assignment {assignment_id} deleted successfully by {current_user.id}")
        logger.info(f"Cancelled assignment: roadmap {roadmap_id} to user {assigned_to}")
        
        return {
            "message": f"Assignment {assignment_id} deleted successfully",
            "assignment_id": assignment_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting assignment {assignment_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete assignment"
        )