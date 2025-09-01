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

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List
from app.db.database import get_db
from app.models.roadmap import Roadmap, Milestone, Topic, UserProgress, ProgressStatus
from app.models.user import User
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    roadmap_ids = (
        db.query(Milestone.roadmap_id)
        .join(Topic, Topic.milestone_id == Milestone.id)
        .join(UserProgress, UserProgress.topic_id == Topic.id)
        .filter(UserProgress.user_id == current_user.id)
        .distinct()
        .all()
    )

    roadmap_id_list = [row[0] for row in roadmap_ids]
    
    roadmaps = db.query(Roadmap).filter(Roadmap.id.in_(roadmap_id_list)).all()

    responses: List[DashboardEnrollmentResponse] = []
    for roadmap in roadmaps:
        total_topics = (
            db.query(Topic)
            .join(Milestone, Milestone.id == Topic.milestone_id)
            .filter(Milestone.roadmap_id == roadmap.id)
            .count()
        )
        progress_rows = (
            db.query(UserProgress)
            .join(Topic, Topic.id == UserProgress.topic_id)
            .join(Milestone, Milestone.id == Topic.milestone_id)
            .filter(UserProgress.user_id == current_user.id, Milestone.roadmap_id == roadmap.id)
            .all()
        )
        started_times = [p.started_at for p in progress_rows if p.started_at is not None]
        enrolled_at = min(started_times) if started_times else roadmap.created_at

        responses.append(DashboardEnrollmentResponse(
            roadmap_id=roadmap.id,
            user_id=current_user.id,
          enrolled_at=enrolled_at,
            total_topics=total_topics
        ))
    return responses
