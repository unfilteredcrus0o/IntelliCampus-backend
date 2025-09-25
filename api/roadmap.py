"""
Roadmap API Routes
=====================================
Provides FastAPI endpoints for roadmap management including creation, retrieval, 
and progress tracking. Supports authenticated users with proper authorization.

Features:
- Create personalized learning roadmaps using LLM
- Retrieve roadmaps with progress tracking  
- Update topic progress and milestone completion
- Dashboard enrollment management with role-based access
- SuperAdmin auto-assignment functionality
- Manager self-created roadmap tracking

Authentication required for all endpoints.
Creator ID implementation allows any user role to create roadmaps.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)
from app.db.database import get_db
from app.models.roadmap import Roadmap, Milestone, Topic, UserProgress, ProgressStatus, Assignment
from app.models.user import User, UserRole
from app.schemas.roadmap import (
    RoadmapCreate, RoadmapResponse, MilestoneResponse, 
    TopicResponse, ProgressUpdate, TopicProgressResponse, 
    MilestoneProgressResponse, RoadmapProgressResponse, 
    DashboardRoadmapResponse, DashboardEnrollmentResponse
)
from app.services.course_validator import validate_course_input, create_custom_course_roadmap_data
from app.services.roadmap_service import (
    create_roadmap_with_llm_fast,
    get_topic_explanation_fast,
    get_topic_explanation_with_metadata,
    update_progress,
    get_roadmap_with_progress,
    generate_topic_sources,
)
from app.core.security import get_current_user
from datetime import datetime, timezone

router = APIRouter(prefix="/api", tags=["Roadmap"])

def _build_roadmap_response(roadmap_data: dict) -> RoadmapResponse:
    """Helper function to build RoadmapResponse from roadmap data"""
    roadmap = roadmap_data['roadmap']
    
    milestones_data = [
        MilestoneResponse(
            id=milestone_data['milestone'].id,
            name=milestone_data['milestone'].name,
            topics=[
                TopicResponse(
                    id=topic_data['topic'].id,
                    name=topic_data['topic'].name,
                    explanation_md=topic_data['topic'].explanation_md,
                    progress=TopicProgressResponse(
                        status=topic_data['progress']['status'],
                        started_at=topic_data['progress'].get('started_at'),
                        completed_at=topic_data['progress'].get('completed_at'),
                        progress_percentage=topic_data['progress'].get('progress_percentage', 0.0)
                    )
                )
                for topic_data in milestone_data['topics']
            ],
            progress=MilestoneProgressResponse(
                status=milestone_data['progress']['status'],
                progress_percentage=milestone_data['progress'].get('progress_percentage', 0.0)
            )
        )
        for milestone_data in roadmap_data['milestones']
    ]

    roadmap_progress = roadmap_data['progress']
    return RoadmapResponse(
        id=roadmap.id,
        title=roadmap.title,
        level=roadmap.level,
        status=roadmap.status.value,
        creator_id=str(roadmap.creator_id),
        milestones=milestones_data,
        progress=RoadmapProgressResponse(
            total_milestones=roadmap_progress['total_milestones'],
            completed_milestones=roadmap_progress['completed_milestones'],
            total_topics=roadmap_progress['total_topics'],
            completed_topics=roadmap_progress['completed_topics'],
            progress_percentage=roadmap_progress['progress_percentage'],
            status=roadmap_progress['status']
        )
    )

def _get_topic_with_access_check(db: Session, topic_id: str, user_id: str) -> Topic:
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    
    roadmap = db.query(Roadmap).filter(Roadmap.id == topic.milestone.roadmap_id).first()
    if not roadmap:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Roadmap not found")
    
    has_access = False
    if roadmap.creator_id == user_id:
        has_access = True
    else:
        assignment = db.query(Assignment).filter(
            Assignment.roadmap_id == roadmap.id,
            Assignment.assigned_to == user_id
        ).first()
        if assignment:
            has_access = True
    
    if not has_access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this topic")
    return topic

def _create_auto_assignments_for_superadmin_roadmap(db: Session, roadmap_id: str, superadmin_id: str, due_date: Optional[datetime] = None) -> int:

    import logging
    logger = logging.getLogger(__name__)
    
    try:

        all_users = db.query(User).filter(
            User.role.in_([UserRole.manager, UserRole.employee])
        ).all()
        
        logger.info(f"Found {len(all_users)} users to auto-assign roadmap {roadmap_id}")
        
        assignments_created = 0
        current_time = datetime.now(timezone.utc)
        
        for user in all_users:
            try:

                existing_assignment = db.query(Assignment).filter(
                    Assignment.roadmap_id == roadmap_id,
                    Assignment.assigned_to == user.id
                ).first()
                
                if existing_assignment:
                    logger.debug(f"Assignment already exists for user {user.id}, skipping")
                    continue
                
                assignment = Assignment(
                    roadmap_id=roadmap_id,
                    assigned_by=superadmin_id,
                    assigned_to=user.id,
                    due_date=due_date,
                    created_at=current_time
                )
                db.add(assignment)
                assignments_created += 1
                
                logger.debug(f"Auto-assigned roadmap {roadmap_id} to user {user.id} ({user.role.value})")
                
            except Exception as e:
                logger.warning(f"Failed to create auto-assignment for user {user.id}: {str(e)}")
                continue
        
        db.commit()
        logger.info(f"Successfully created {assignments_created} auto-assignments for roadmap {roadmap_id}")
        return assignments_created
        
    except Exception as e:
        logger.error(f"Error creating auto-assignments for roadmap {roadmap_id}: {str(e)}")
        db.rollback()
        return 0

@router.post("/roadmap/create")
def create_roadmap(
    roadmap_data: RoadmapCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"User {current_user.id} ({current_user.role.value}) creating roadmap: {roadmap_data.title}")
    logger.info(f"Selected topics for validation: {roadmap_data.selectedTopics}")

    validation_result = validate_course_input(roadmap_data.selectedTopics)

    if validation_result["action"] == "error":
        logger.warning(f"Invalid course input rejected: {roadmap_data.selectedTopics} - {validation_result['reason']}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "We don't recognize this course. Please enter a valid topic.",
                "invalid_topics": validation_result["invalid_topics"],
                "suggested_topics": validation_result.get("suggested_topics", []),
                "reason": validation_result["reason"]
            }
        )
    
    elif validation_result["action"] == "fallback_custom":
        logger.info(f"Falling back to Custom Course for input: {roadmap_data.selectedTopics}")
        roadmap_input = create_custom_course_roadmap_data(
            roadmap_data.selectedTopics, 
            roadmap_data.skillLevel, 
            roadmap_data.duration or "flexible"
        )
        roadmap_input["creator_id"] = current_user.id
        
        if roadmap_data.title and roadmap_data.title.strip():
            roadmap_input["title"] = roadmap_data.title
            
        # Add start_date and end_date if provided
        if roadmap_data.start_date:
            roadmap_input["start_date"] = roadmap_data.start_date
        if roadmap_data.end_date:
            roadmap_input["end_date"] = roadmap_data.end_date
            
    elif validation_result["action"] == "proceed":

        valid_topics = validation_result["valid_topics"]
        if validation_result["invalid_topics"]:
            logger.warning(f"Filtering out invalid topics: {[item['topic'] for item in validation_result['invalid_topics']]}")
        
        logger.info(f"Proceeding with valid topics: {valid_topics}")
        roadmap_input = {
            "creator_id": current_user.id,
            "title": roadmap_data.title,
            "level": roadmap_data.skillLevel,
            "interests": valid_topics,
        }
        
        if roadmap_data.duration:
            roadmap_input["timelines"] = {topic: roadmap_data.duration for topic in valid_topics}
            
        # Add start_date and end_date if provided
        if roadmap_data.start_date:
            roadmap_input["start_date"] = roadmap_data.start_date
        if roadmap_data.end_date:
            roadmap_input["end_date"] = roadmap_data.end_date
    
    roadmap = create_roadmap_with_llm_fast(db, roadmap_input)

    auto_assignments_count = 0
    if current_user.role == UserRole.superadmin:
        logger.info(f"SuperAdmin created roadmap {roadmap.id}, auto-assigning to all users with due_date: {roadmap_data.due_date}")
        auto_assignments_count = _create_auto_assignments_for_superadmin_roadmap(
            db, roadmap.id, current_user.id, roadmap_data.due_date
        )
        logger.info(f"Created {auto_assignments_count} auto-assignments for roadmap {roadmap.id}")
    
    response = {
        "roadmap_id": roadmap.id,
        "auto_assigned_to_users": auto_assignments_count if current_user.role == UserRole.superadmin else 0,
        "validation_result": {
            "action_taken": validation_result["action"],
            "original_topics": roadmap_data.selectedTopics,
            "processed_topics": roadmap_input.get("interests", []),
            "filtered_invalid_topics": [item["topic"] for item in validation_result.get("invalid_topics", [])]
        }
    }
    
    return response

@router.get("/roadmap/{roadmap_id}/progress", response_model=RoadmapResponse)
def get_roadmap_progress(
    roadmap_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    roadmap_data = get_roadmap_with_progress(db, roadmap_id, current_user.id)
    if not roadmap_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Roadmap not found")

    return _build_roadmap_response(roadmap_data)

@router.put("/topic/{topic_id}/progress")
def update_topic_progress(
    topic_id: str,
    progress_update: ProgressUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    
    topic = _get_topic_with_access_check(db, topic_id, current_user.id)
    update_progress(db, current_user.id, topic_id, progress_update.status)
    
    return {"message": "Progress updated successfully"}

@router.get("/topic/{topic_id}/explanation")
def get_topic_explanation_endpoint(
    topic_id: str,
    skill_level: str = "basic",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    topic = _get_topic_with_access_check(db, topic_id, current_user.id)
    
    valid_skill_levels = ["basic", "intermediate", "advanced"]
    if skill_level not in valid_skill_levels:
        skill_level = "basic"
    
    cache_key = f"{topic.name}_{skill_level}_metadata"
    from app.services.roadmap_service import _explanation_cache
    
    if cache_key in _explanation_cache:
        logger.info(f"Returning cached explanation for {topic.name}")
        cached_data = _explanation_cache[cache_key]
        return {
            "explanation": cached_data["explanation"],
            "difficulty_level": cached_data["difficulty_level"],
            "estimated_time": cached_data["estimated_time"],
            "prerequisites": cached_data["prerequisites"],
            "key_concepts": cached_data["key_concepts"],
            "learning_objectives": cached_data["learning_objectives"],
        }
    
    explanation_data = get_topic_explanation_with_metadata(db, topic_id, skill_level)
    
    if not explanation_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic explanation not found")

    try:
        db.refresh(topic)
    except Exception:
        # If refresh fails for any reason, fallback to re-querying
        topic = db.query(Topic).filter(Topic.id == topic_id).first()

    return {
        "explanation": explanation_data["explanation"],
        "difficulty_level": explanation_data["difficulty_level"],
        "estimated_time": explanation_data["estimated_time"],
        "prerequisites": explanation_data["prerequisites"],
        "key_concepts": explanation_data["key_concepts"],
        "learning_objectives": explanation_data["learning_objectives"],
    }

@router.get("/roadmap/user", response_model=List[DashboardRoadmapResponse])
def get_user_roadmaps(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    roadmaps = db.query(Roadmap).filter(Roadmap.creator_id == current_user.id).all()
    
    roadmap_responses = []
    for roadmap in roadmaps:
        roadmap_data = get_roadmap_with_progress(db, roadmap.id, current_user.id)
        if roadmap_data:
            roadmap_responses.append(DashboardRoadmapResponse(
                id=roadmap.id,
                title=roadmap.title,
                status=roadmap.status.value,
                progress_percentage=roadmap_data['progress']['progress_percentage']
            ))
    
    return roadmap_responses

@router.get("/roadmap/{roadmap_id}", response_model=RoadmapResponse)
def get_roadmap_details(
    roadmap_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    roadmap_data = get_roadmap_with_progress(db, roadmap_id, current_user.id)
    if not roadmap_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Roadmap not found")
    return _build_roadmap_response(roadmap_data)

@router.get("/dashboard/enrollments", response_model=List[DashboardEnrollmentResponse])
def list_dashboard_enrollments(
    user_id: Optional[str] = Query(None, description="Filter by specific user ID"),
    manager_id: Optional[str] = Query(None, description="Filter by manager ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get enrollment data based on user role and enrollment status.
    
    Role-based access:
    - Employee: only own enrollments
    - Manager: own enrollments + enrollments of all reportees (or specific user_id if it's self or a reportee)
    - SuperAdmin: enrollments of all users (or specific user_id if provided)
    """
    
    # Get current user's role value
    current_role = current_user.role.value
    
    # Determine which user(s) to get enrollment data for based on role and query params
    target_user_ids = []
    
    if current_role == UserRole.employee.value:
        # Employees can only see their own progress
        if user_id and user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Employees can only view their own enrollment progress"
            )
        target_user_ids = [current_user.id]
        
    elif current_role == UserRole.manager.value:
        # Managers can see their own progress AND their reportees' progress
        if manager_id:
            # If manager_id is specified, ensure it matches current user
            if manager_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Managers can only view progress of their own reportees"
                )
        
        if user_id:
            # Check if the specified user is the manager themselves or a reportee
            if user_id == current_user.id:
                target_user_ids = [user_id]
            else:
                reportee = db.query(User).filter(
                    User.manager_id == current_user.id,
                    User.id == user_id
                ).first()
                if not reportee:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You can only view progress of yourself or your direct reportees"
                    )
                target_user_ids = [user_id]
        else:
            # Get all reportees AND include the manager themselves
            reportees = db.query(User).filter(User.manager_id == current_user.id).all()
            target_user_ids = [current_user.id] + [reportee.id for reportee in reportees]
            
    elif current_role == UserRole.superadmin.value:
        # SuperAdmins can see all users' progress
        if user_id:
            # Verify the user exists
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            target_user_ids = [user_id]
        elif manager_id:
            # Get all reportees of the specified manager
            manager = db.query(User).filter(User.id == manager_id).first()
            if not manager:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Manager not found"
                )
            reportees = db.query(User).filter(User.manager_id == manager_id).all()
            target_user_ids = [reportee.id for reportee in reportees]
        else:
            # Get all users
            all_users = db.query(User).all()
            target_user_ids = [user.id for user in all_users]
    
    if not target_user_ids:
        return []    
    
    from app.models.roadmap import Assignment
    
    roadmap_data = {}
    for target_user_id in target_user_ids:
        enrolled_roadmap_ids = set()
        
        # 1. Roadmaps they created
        created_roadmap_ids = (
            db.query(Roadmap.id)
            .filter(Roadmap.creator_id == target_user_id)
            .all()
        )
        enrolled_roadmap_ids.update([row[0] for row in created_roadmap_ids])
        
        # 2. Roadmaps they were assigned to
        assigned_roadmap_ids = (
            db.query(Assignment.roadmap_id)
            .filter(Assignment.assigned_to == target_user_id)
            .all()
        )
        enrolled_roadmap_ids.update([row[0] for row in assigned_roadmap_ids])
        
        # 3. Roadmaps they have progress in
        progress_roadmap_ids = (
        db.query(Milestone.roadmap_id)
        .join(Topic, Topic.milestone_id == Milestone.id)
        .join(UserProgress, UserProgress.topic_id == Topic.id)
        .filter(UserProgress.user_id == target_user_id)
        .distinct()
        .all()
    )
        enrolled_roadmap_ids.update([row[0] for row in progress_roadmap_ids])
        
        # Add to roadmap_data
        for roadmap_id in enrolled_roadmap_ids:
            if roadmap_id not in roadmap_data:
                roadmap_data[roadmap_id] = []
            roadmap_data[roadmap_id].append(target_user_id)
    
    responses: List[DashboardEnrollmentResponse] = []
    
    for roadmap_id, enrolled_user_ids in roadmap_data.items():
        roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
        if not roadmap:
            continue
            
        total_topics = (
            db.query(Topic)
            .join(Milestone, Milestone.id == Topic.milestone_id)
            .filter(Milestone.roadmap_id == roadmap_id)
            .count()
        )
        
        for enrolled_user_id in enrolled_user_ids:
            # Determine enrolled_at with consistent logic:
            # 1. If assigned, use assignment creation date
            # 2. If creator, use roadmap creation date
            enrolled_at = None
            
            # Check if user was assigned to this roadmap
            assignment = db.query(Assignment).filter(
                Assignment.roadmap_id == roadmap_id,
                Assignment.assigned_to == enrolled_user_id
            ).first()
            
            if assignment:
                enrolled_at = assignment.created_at
            elif roadmap.creator_id == enrolled_user_id:
                enrolled_at = roadmap.created_at
            else:
                # User has progress but no assignment and isn't creator
                # Use earliest progress start time
                progress_rows = (
                    db.query(UserProgress)
                    .join(Topic, Topic.id == UserProgress.topic_id)
                    .join(Milestone, Milestone.id == Topic.milestone_id)
                    .filter(
                        UserProgress.user_id == enrolled_user_id, 
                        Milestone.roadmap_id == roadmap_id
                    )
                    .all()
                )
                
                started_times = [p.started_at for p in progress_rows if p.started_at is not None]
                if started_times:
                    enrolled_at = min(started_times)
                else:
                    enrolled_at = roadmap.created_at

            # Calculate progress information for this user and roadmap
            # Get all topic IDs for this roadmap
            all_topic_ids = (
                db.query(Topic.id)
                .join(Milestone, Milestone.id == Topic.milestone_id)
                .filter(Milestone.roadmap_id == roadmap_id)
                .all()
            )
            topic_ids_list = [topic_id[0] for topic_id in all_topic_ids]
            
            # Get progress data for this user
            user_progress_data = db.query(UserProgress).filter(
                UserProgress.user_id == enrolled_user_id,
                UserProgress.topic_id.in_(topic_ids_list)
            ).all()
            
            # Calculate progress statistics
            completed_topics = sum(1 for p in user_progress_data if p.status.value == ProgressStatus.completed)
            in_progress_topics = sum(1 for p in user_progress_data if p.status.value == "in_progress")
            
            if total_topics > 0:
                progress_percentage = int((completed_topics / total_topics) * 100)
            else:
                progress_percentage = 0
            
            # Determine overall status
            if completed_topics == total_topics and total_topics > 0:
                status = "completed"
            elif completed_topics > 0 or in_progress_topics > 0:
                status = "in_progress"
            else:
                status = "not_started"

            user = db.query(User).filter(User.id == enrolled_user_id).first()
            user_role = user.role.value if user else "unknown"
            
            # Get course title from roadmap
            course_title = roadmap.title if roadmap else "Unknown Course"
            
            # Get start date and due date from roadmap if available, otherwise use assignment/enrollment dates
            # Format dates as strings to return exact format to frontend
            start_date = roadmap.start_date if roadmap.start_date else (enrolled_at.isoformat() if enrolled_at else None)
            due_date = roadmap.end_date if roadmap.end_date else (assignment.due_date.isoformat() if assignment and assignment.due_date else None)
            
            # Determine assignment details and type
            if assignment:
                # User was assigned to this roadmap
                assigned_by = assignment.assigned_by
                assigned_to = assignment.assigned_to
                assignment_type = "assigned"
            elif roadmap.creator_id == enrolled_user_id:
                # User created this roadmap themselves
                assigned_by = None
                assigned_to = None
                assignment_type = "self_created"
            else:
                # User has progress but no assignment and isn't creator (enrolled somehow)
                assigned_by = None
                assigned_to = None
                assignment_type = "creator_enrolled"
            
            responses.append(DashboardEnrollmentResponse(
                roadmap_id=roadmap_id,
                user_id=enrolled_user_id,
                role=user_role,
                enrolled_at=enrolled_at,
                course_title=course_title,
                start_date=start_date,
                due_date=due_date,
                assigned_by=assigned_by,
                assigned_to=assigned_to,
                assignment_type=assignment_type,
                total_topics=total_topics,
                completed_topics=completed_topics,
                progress_percentage=progress_percentage,
                status=status
            ))
    return responses

@router.post("/roadmap/{roadmap_id}/enroll")
def enroll_in_roadmap(
    roadmap_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Imported here to avoid circular imports
    from app.services.roadmap_service import auto_enroll_user_in_roadmap
    
    try:
        roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
        if not roadmap:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Roadmap not found")
        
        from app.models.roadmap import Assignment
        assignment = db.query(Assignment).filter(
            Assignment.roadmap_id == roadmap_id,
            Assignment.assigned_to == current_user.id
        ).first()
        
        is_creator = roadmap.creator_id == current_user.id
        
        if not assignment and not is_creator:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="You must be assigned to this roadmap or be its creator to enroll"
            )
        
        created_count = auto_enroll_user_in_roadmap(db, current_user.id, roadmap_id)
        db.commit()
        
        return {
            "message": f"Successfully enrolled in roadmap: {roadmap.title}",
            "roadmap_id": roadmap_id,
            "roadmap_title": roadmap.title,
            "topics_created": created_count,
            "enrollment_type": "assignment" if assignment else "creator"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enroll in roadmap: {str(e)}"
        )