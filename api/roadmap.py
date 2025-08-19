# ==========================================
# Roadmap API Routes
# ------------------------------------------
# Provides endpoints to:
# - Create a new roadmap using LLM service (authenticated).
# - Retrieve a roadmap with milestones and topics (authenticated & authorized).
# - Get markdown explanation for a topic (authenticated).
# - Get all roadmaps for authenticated user.
# - Update progress on topics (authenticated).
#
# Dependencies:
# - SQLAlchemy models: Roadmap, Milestone, Topic, UserProgress, User
# - Schemas: RoadmapCreate, RoadmapResponse, MilestoneResponse, TopicResponse, ProgressUpdate
# - Services: create_roadmap_with_llm, get_topic_explanation, update_progress
# - Security: get_current_user dependency for authentication
# ==========================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List
from app.db.database import get_db
from app.models.roadmap import Roadmap, Milestone, Topic, UserProgress
from app.models.user import User
from app.schemas.roadmap import RoadmapCreate, RoadmapResponse, MilestoneResponse, TopicResponse, ProgressUpdate
from app.services.roadmap_service import create_roadmap_with_llm, get_topic_explanation, update_progress
from app.core.security import get_current_user

router = APIRouter(prefix="/api", tags=["Roadmap"])

@router.post("/roadmap/create")
def create_roadmap(
    payload: RoadmapCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new roadmap for the authenticated user"""
    title = (
        payload.title.strip()
        if getattr(payload, "title", None) and payload.title.strip()
        else f"{payload.skillLevel.capitalize()} Roadmap for {', '.join(payload.selectedTopics)}"
    )

    roadmap_data = {
        "title": title,
        "interests": payload.selectedTopics,
        "level": payload.skillLevel,
        "timelines": {topic: payload.duration for topic in payload.selectedTopics},
        "user_id": current_user.id  # Use authenticated user's ID
    }
    roadmap = create_roadmap_with_llm(db, roadmap_data)
    return {"roadmap_id": roadmap.id, "status": roadmap.status.value}

@router.get("/roadmap/{roadmap_id}", response_model=RoadmapResponse)
def get_roadmap(
    roadmap_id: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific roadmap (only if it belongs to the authenticated user)"""
    roadmap = (
        db.query(Roadmap)
          .options(
              joinedload(Roadmap.milestones)
                .joinedload(Milestone.topics)
          )
          .filter(Roadmap.id == roadmap_id, Roadmap.user_id == current_user.id)
          .first()
    )
    if not roadmap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Roadmap not found or access denied"
        )

    milestones_data = []
    for m in roadmap.milestones:
        topics_data = [
            TopicResponse(id=t.id, name=t.name, explanation_md=t.explanation_md)
            for t in m.topics
        ]
        milestones_data.append(
            MilestoneResponse(id=m.id, name=m.name, topics=topics_data)
        )

    return RoadmapResponse(
        id=roadmap.id,
        title=roadmap.title,
        level=roadmap.level,
        status=roadmap.status.value,
        milestones=milestones_data
    )

@router.get("/topic/{topic_id}/explanation")
def get_explanation(
    topic_id: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get explanation for a topic (only if it belongs to user's roadmap)"""
    # First verify the topic belongs to a roadmap owned by the current user
    topic = (
        db.query(Topic)
        .join(Milestone)
        .join(Roadmap)
        .filter(Topic.id == topic_id, Roadmap.user_id == current_user.id)
        .first()
    )
    
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found or access denied"
        )
    
    try:
        explanation_md = get_topic_explanation(db, topic_id)
        return {"explanation": explanation_md}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve explanation: {str(e)}")

@router.get("/roadmaps", response_model=List[RoadmapResponse])
def get_user_roadmaps(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all roadmaps for the authenticated user"""
    roadmaps = (
        db.query(Roadmap)
        .options(
            joinedload(Roadmap.milestones)
            .joinedload(Milestone.topics)
        )
        .filter(Roadmap.user_id == current_user.id)
        .all()
    )
    
    roadmaps_data = []
    for roadmap in roadmaps:
        milestones_data = []
        for m in roadmap.milestones:
            topics_data = [
                TopicResponse(id=t.id, name=t.name, explanation_md=t.explanation_md)
                for t in m.topics
            ]
            milestones_data.append(
                MilestoneResponse(id=m.id, name=m.name, topics=topics_data)
            )
        
        roadmaps_data.append(RoadmapResponse(
            id=roadmap.id,
            title=roadmap.title,
            level=roadmap.level,
            status=roadmap.status.value,
            milestones=milestones_data
        ))
    
    return roadmaps_data

@router.post("/progress/update")
def update_topic_progress(
    progress_data: ProgressUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update progress for a topic (only if it belongs to user's roadmap)"""
    # Verify the topic belongs to a roadmap owned by the current user
    topic = (
        db.query(Topic)
        .join(Milestone)
        .join(Roadmap)
        .filter(Topic.id == progress_data.topic_id, Roadmap.user_id == current_user.id)
        .first()
    )
    
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found or access denied"
        )
    
    try:
        progress = update_progress(db, current_user.id, progress_data.topic_id, progress_data.status)
        return {
            "message": "Progress updated successfully",
            "progress": {
                "topic_id": progress.topic_id,
                "status": progress.status.value,
                "started_at": progress.started_at,
                "completed_at": progress.completed_at
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update progress: {str(e)}"
        )
