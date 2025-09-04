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
from app.db.database import get_db
from app.models.roadmap import Roadmap, Milestone, Topic, UserProgress, ProgressStatus, Assignment
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
    
    roadmap_input = {
        "creator_id": current_user.id,
        "title": roadmap_data.title,
        "level": roadmap_data.skillLevel,
        "interests": roadmap_data.selectedTopics,
        "timelines": {topic: roadmap_data.duration for topic in roadmap_data.selectedTopics}
    }
    
    roadmap = create_roadmap_with_llm(db, roadmap_input)

    auto_assignments_count = 0
    if current_user.role == UserRole.superadmin:
        logger.info(f"SuperAdmin created roadmap {roadmap.id}, auto-assigning to all users with due_date: {roadmap_data.due_date}")
        auto_assignments_count = _create_auto_assignments_for_superadmin_roadmap(
            db, roadmap.id, current_user.id, roadmap_data.due_date
        )
        logger.info(f"Created {auto_assignments_count} auto-assignments for roadmap {roadmap.id}")
    
    return {
        "roadmap_id": roadmap.id,
        "auto_assigned_to_users": auto_assignments_count if current_user.role == UserRole.superadmin else 0
    }

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
    roadmap_id: Optional[str] = Query(None, description="Filter by specific roadmap"),
    status_filter: Optional[str] = Query(None, description="Filter by status: not_started, in_progress, completed"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Comprehensive enrollment dashboard with role-based functionality:
    - Employee: Only own progress and assignments
    - Manager: All assigned courses progress + own progress with detailed assignment tracking + self-created roadmaps
    - SuperAdmin: System-wide progress with comprehensive filtering and assignment details
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"User {current_user.id} ({current_user.role.value}) requesting dashboard with filters: user_id={user_id}, manager_id={manager_id}, roadmap_id={roadmap_id}")
    # Determine target users and get assignments based on role
    target_user_ids = []
    assignments_data = {}
    
    if current_user.role == UserRole.employee:
        # Employees see their own assignments and progress
        if user_id and user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Employees can only view their own progress"
            )
        target_user_ids = [current_user.id]
        
        assignments = db.query(Assignment).filter(Assignment.assigned_to == current_user.id)
        if roadmap_id:
            assignments = assignments.filter(Assignment.roadmap_id == roadmap_id)
        assignments = assignments.all()
        
    elif current_user.role == UserRole.manager:
        if user_id:
            requested_user = db.query(User).filter(User.id == user_id).first()
            if not requested_user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            
            if requested_user.manager_id == current_user.id or user_id == current_user.id:
                target_user_ids = [user_id]
                assignments = db.query(Assignment).filter(Assignment.assigned_to == user_id)
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Managers can only view progress of their reportees or themselves"
                )
        else:
            reportees = db.query(User).filter(User.manager_id == current_user.id).all()
            target_user_ids = [user.id for user in reportees]
            
            target_user_ids.append(current_user.id)
            
            assignments = db.query(Assignment).filter(
                Assignment.assigned_to.in_(target_user_ids)
            )
        
        if roadmap_id:
            assignments = assignments.filter(Assignment.roadmap_id == roadmap_id)
        assignments = assignments.all()
                
    elif current_user.role == UserRole.superadmin:

        assignments_query = db.query(Assignment)
        
        if user_id:
            requested_user = db.query(User).filter(User.id == user_id).first()
            if not requested_user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            target_user_ids = [user_id]
            assignments_query = assignments_query.filter(Assignment.assigned_to == user_id)
        elif manager_id:
            reportees = db.query(User).filter(User.manager_id == manager_id).all()
            target_user_ids = [user.id for user in reportees]
            assignments_query = assignments_query.filter(Assignment.assigned_to.in_(target_user_ids))
        else:

            assignments = assignments_query.all()
            target_user_ids = list(set([a.assigned_to for a in assignments]))
        
        if roadmap_id:
            assignments_query = assignments_query.filter(Assignment.roadmap_id == roadmap_id)
        
        assignments = assignments_query.all()
    

    for assignment in assignments:
        key = (assignment.assigned_to, assignment.roadmap_id)
        assignments_data[key] = assignment
    
    if not target_user_ids:
        return []
    

    assignment_roadmap_ids = list(set([a.roadmap_id for a in assignments]))
    if current_user.role == UserRole.manager:
        manager_created_roadmaps = db.query(Roadmap.id).filter(Roadmap.creator_id == current_user.id).all()
        manager_roadmap_ids = [r.id for r in manager_created_roadmaps]
        all_roadmap_ids = list(set(assignment_roadmap_ids + manager_roadmap_ids))
    else:
        all_roadmap_ids = assignment_roadmap_ids

    enrollment_data = (
        db.query(
            Milestone.roadmap_id,
            UserProgress.user_id,
            UserProgress.started_at,
            UserProgress.last_accessed,
            UserProgress.status
        )
        .join(Topic, Topic.milestone_id == Milestone.id)
        .join(UserProgress, UserProgress.topic_id == Topic.id)
        .filter(
            UserProgress.user_id.in_(target_user_ids),
            Milestone.roadmap_id.in_(all_roadmap_ids) if all_roadmap_ids else True
        )
        .all()
    )

    user_roadmap_progress = {}
    for roadmap_id, user_id, started_at, last_accessed, status in enrollment_data:
        key = (user_id, roadmap_id)
        if key not in user_roadmap_progress:
            user_roadmap_progress[key] = {
                'started_times': [],
                'last_accessed_times': [],
                'statuses': []
            }
        user_roadmap_progress[key]['started_times'].append(started_at)
        user_roadmap_progress[key]['last_accessed_times'].append(last_accessed)
        user_roadmap_progress[key]['statuses'].append(status)

    unique_roadmap_ids = all_roadmap_ids
    roadmaps = db.query(Roadmap).filter(Roadmap.id.in_(unique_roadmap_ids)).all() if unique_roadmap_ids else []
    roadmap_lookup = {r.id: r for r in roadmaps}
    
    users = db.query(User).filter(User.id.in_(target_user_ids)).all()
    user_lookup = {u.id: u for u in users}

    responses: List[DashboardEnrollmentResponse] = []
    
    processed_roadmap_user_pairs = set()
    
    for assignment in assignments:
        roadmap = roadmap_lookup.get(assignment.roadmap_id)
        user = user_lookup.get(assignment.assigned_to)
        assigner = db.query(User).filter(User.id == assignment.assigned_by).first()
        
        if not roadmap or not user:
            continue
        processed_roadmap_user_pairs.add((user.id, roadmap.id))
            
        total_topics = (
            db.query(Topic)
            .join(Milestone, Milestone.id == Topic.milestone_id)
            .filter(Milestone.roadmap_id == roadmap.id)
            .count()
        )
        
        progress_key = (user.id, roadmap.id)
        progress_data = user_roadmap_progress.get(progress_key)
        
        if progress_data:

            completed_topics = len([s for s in progress_data['statuses'] if s == ProgressStatus.completed])
            progress_percentage = int((completed_topics / total_topics * 100)) if total_topics > 0 else 0
            
            valid_start_times = [t for t in progress_data['started_times'] if t is not None]
            valid_access_times = [t for t in progress_data['last_accessed_times'] if t is not None]
            
            enrolled_at = min(valid_start_times) if valid_start_times else None
            last_accessed = max(valid_access_times) if valid_access_times else None
            
            if progress_percentage == 100:
                status = "completed"
            elif valid_start_times or valid_access_times:
                status = "in_progress"
            else:
                status = "not_started"
        else:
            completed_topics = 0
            progress_percentage = 0
            enrolled_at = None
            last_accessed = None
            status = "not_started"
        
        if assignment.due_date and status != "completed" and datetime.now(timezone.utc) > assignment.due_date.replace(tzinfo=timezone.utc):
            # Note: keeping status as is but could add overdue logic here in future (just a note ^^)
            pass
        
        if status_filter and status != status_filter:
            continue

        responses.append(DashboardEnrollmentResponse(
            roadmap_id=roadmap.id,
            roadmap_title=roadmap.title,
            user_id=user.id,
            user_name=user.name,
            role=user.role.value,
            enrolled_at=enrolled_at,
            total_topics=total_topics,
            completed_topics=completed_topics,
            progress_percentage=progress_percentage,
            last_accessed=last_accessed,
            assignment_id=assignment.id,
            assigned_by=assignment.assigned_by,
            assigner_name=assigner.name if assigner else "Unknown",
            due_date=assignment.due_date,
            assigned_at=assignment.created_at,
            status=status
        ))

    if current_user.role == UserRole.manager:

        manager_created_roadmaps = db.query(Roadmap).filter(Roadmap.creator_id == current_user.id)
        if roadmap_id:
            manager_created_roadmaps = manager_created_roadmaps.filter(Roadmap.id == roadmap_id)
        manager_created_roadmaps = manager_created_roadmaps.all()
        
        for roadmap in manager_created_roadmaps:

            if (current_user.id, roadmap.id) in processed_roadmap_user_pairs:
                continue

            roadmap_assignments = db.query(Assignment).filter(Assignment.roadmap_id == roadmap.id).all()
            if roadmap_assignments:
                continue

            total_topics = (
                db.query(Topic)
            .join(Milestone, Milestone.id == Topic.milestone_id)
                .filter(Milestone.roadmap_id == roadmap.id)
                .count()
            )
            
            progress_key = (current_user.id, roadmap.id)
            progress_data = user_roadmap_progress.get(progress_key)
            
            if progress_data:
                completed_topics = len([s for s in progress_data['statuses'] if s == ProgressStatus.completed])
                progress_percentage = int((completed_topics / total_topics * 100)) if total_topics > 0 else 0
                
                valid_start_times = [t for t in progress_data['started_times'] if t is not None]
                valid_access_times = [t for t in progress_data['last_accessed_times'] if t is not None]
                
                enrolled_at = min(valid_start_times) if valid_start_times else None
                last_accessed = max(valid_access_times) if valid_access_times else None
                
                if progress_percentage == 100:
                    status = "completed"
                elif valid_start_times or valid_access_times:
                    status = "in_progress"
                else:
                    status = "not_started"
            else:
                completed_topics = 0
                progress_percentage = 0
                enrolled_at = None
                last_accessed = None
                status = "not_started"

            # Apply status filter if provided
            if status_filter and status != status_filter:
                continue

            responses.append(DashboardEnrollmentResponse(
                roadmap_id=roadmap.id,
                roadmap_title=roadmap.title,
                user_id=current_user.id,
                user_name=current_user.name,
                role=current_user.role.value,
                enrolled_at=enrolled_at,
                total_topics=total_topics,
                completed_topics=completed_topics,
                progress_percentage=progress_percentage,
                last_accessed=last_accessed,
                assignment_id=None,
                assigned_by=None,
                assigner_name=None,
                due_date=None,
                assigned_at=None,
                status=status
            ))
    
    
    responses.sort(key=lambda x: (
        0 if x.status == "completed" else 1 if x.status == "in_progress" else 2,
        x.user_name,
        x.roadmap_title
    ))
    
    logger.info(f"Dashboard retrieved: {len(responses)} assignments/enrollments shown")
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