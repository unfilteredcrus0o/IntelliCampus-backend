"""
Roadmap API Routes
=====================================
Provides FastAPI endpoints for roadmap management including creation, retrieval, 
and progress tracking. Supports authenticated users with proper authorization.

Features:
- Create personalized learning roadmaps using LLM
- Retrieve roadmaps with progress tracking  
- Update topic progress and milestone completion
- Dashboard enrollment management

Authentication required for all endpoints.
Creator ID implementation allows any user role to create roadmaps.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.db.database import get_db
from app.models.roadmap import Roadmap, Milestone, Topic, UserProgress, ProgressStatus
from app.models.user import User, UserRole
from app.schemas.roadmap import (
    RoadmapCreate, RoadmapResponse, MilestoneResponse, 
    TopicResponse, ProgressUpdate, TopicProgressResponse, 
    MilestoneProgressResponse, RoadmapProgressResponse, 
    DashboardRoadmapResponse, DashboardEnrollmentResponse
)
from app.services.roadmap_service import (
    create_roadmap_with_llm,
    get_topic_explanation,
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
                        progress_percentage=topic_data['progress'].get('progress_percentage', 0)
                    )
                )
                for topic_data in milestone_data['topics']
            ],
            progress=MilestoneProgressResponse(
                status=milestone_data['progress']['status'],
                progress_percentage=milestone_data['progress'].get('progress_percentage', 0)
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
    if not roadmap or roadmap.creator_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this topic")
    return topic

@router.post("/roadmap/create")
def create_roadmap(
    roadmap_data: RoadmapCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    
    roadmap_input = {
        "creator_id": current_user.id,
        "title": roadmap_data.title,
        "level": roadmap_data.skillLevel,
        "interests": roadmap_data.selectedTopics,
        "timelines": {topic: roadmap_data.duration for topic in roadmap_data.selectedTopics}
    }
    
    roadmap = create_roadmap_with_llm(db, roadmap_input)
    return {"roadmap_id": roadmap.id}

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    topic = _get_topic_with_access_check(db, topic_id, current_user.id)
    explanation = get_topic_explanation(db, topic_id)
    
    if not explanation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic explanation not found")

    try:
        db.refresh(topic)
    except Exception:
        # If refresh fails for any reason, fallback to re-querying
        topic = db.query(Topic).filter(Topic.id == topic_id).first()

    sources = generate_topic_sources(db, topic_id)

    explanation_with_sources = explanation
    if sources:
        lines = ["\n\n## Recommended Sources"]
        for s in sources:
            title = s.get("title") or s.get("url") or "Resource"
            url = s.get("url") or ""
            desc = s.get("description") or ""
            lines.append(f"- [{title}]({url}) — {desc}")
        explanation_with_sources += "\n" + "\n".join(lines)

    return {
        "explanation": explanation_with_sources,
        "difficulty_level": None,
        "estimated_time": None,
        "prerequisites": None,
        "key_concepts": None,
        "learning_objectives": None,
        "sources": sources,
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
    current_role = getattr(current_user.role, 'value', current_user.role)
    
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
        reportee_query = db.query(User).filter(User.manager_id == current_user.id)
        
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
                reportee = reportee_query.filter(User.id == user_id).first()
                if not reportee:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You can only view progress of yourself or your direct reportees"
                    )
                target_user_ids = [user_id]
        else:
            # Get all reportees AND include the manager themselves
            reportees = reportee_query.all()
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
            enrolled_at = roadmap.created_at
            
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
                # Use earliest progress start time if available
                enrolled_at = min(started_times)
            else:
                assignment = db.query(Assignment).filter(
                    Assignment.roadmap_id == roadmap_id,
                    Assignment.assigned_to == enrolled_user_id
                ).first()
                if assignment:
                    enrolled_at = assignment.created_at
                else:
                    # Check if they're the creator (use roadmap creation date)
                    if roadmap.creator_id == enrolled_user_id:
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
            completed_topics = sum(1 for p in user_progress_data if p.status.value == "completed")
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

        responses.append(DashboardEnrollmentResponse(
            roadmap_id=roadmap_id,
            user_id=enrolled_user_id,
          enrolled_at=enrolled_at,
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