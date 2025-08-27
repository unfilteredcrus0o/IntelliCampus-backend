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
from app.models.roadmap import Roadmap, Milestone, Topic, UserProgress
from app.models.user import User
from app.schemas.roadmap import (
    RoadmapCreate, RoadmapResponse, MilestoneResponse, 
    TopicResponse, ProgressUpdate, TopicProgressResponse, 
    MilestoneProgressResponse, RoadmapProgressResponse, 
    DashboardRoadmapResponse, DashboardEnrollmentResponse
)
from app.services.roadmap_service import (create_roadmap_with_llm, get_topic_explanation, update_progress, get_roadmap_with_progress)
from app.core.security import get_current_user

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
                        status=topic_data['progress']['status']
                    )
                )
                for topic_data in milestone_data['topics']
            ],
            progress=MilestoneProgressResponse(
                status=milestone_data['progress']['status']
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
        creator_id=roadmap.creator_id,
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
    """Helper function to get topic with access check"""
    topic = (
        db.query(Topic)
        .join(Milestone)
        .join(Roadmap)
        .filter(Topic.id == topic_id, Roadmap.creator_id == user_id)
        .first()
    )
    
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found or access denied"
        )
    return topic

@router.post("/roadmap/create")
def create_roadmap(
    payload: RoadmapCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

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
        "creator_id": current_user.id
    }
    roadmap = create_roadmap_with_llm(db, roadmap_data)
    return {"roadmap_id": roadmap.id, "status": roadmap.status.value}

@router.get("/roadmap/{roadmap_id}", response_model=RoadmapResponse)
def get_roadmap(
    roadmap_id: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    roadmap_data = get_roadmap_with_progress(db, roadmap_id, current_user.id)
    
    if not roadmap_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Roadmap not found or access denied"
        )

    return _build_roadmap_response(roadmap_data)

@router.get("/topic/{topic_id}/explanation")
def get_explanation(
    topic_id: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    topic = _get_topic_with_access_check(db, topic_id, current_user.id)
    
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
    roadmaps = (
        db.query(Roadmap)
        .filter(Roadmap.creator_id == current_user.id)
        .all()
    )
    
    return [
        _build_roadmap_response(get_roadmap_with_progress(db, roadmap.id, current_user.id))
        for roadmap in roadmaps
        if get_roadmap_with_progress(db, roadmap.id, current_user.id)
    ]

@router.get("/dashboard/enrollments", response_model=DashboardEnrollmentResponse)
def get_dashboard_enrollments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    roadmaps = (
        db.query(Roadmap)
        .filter(Roadmap.creator_id == current_user.id)
        .all()
    )
    
    if not roadmaps:
        return DashboardEnrollmentResponse(
            success=False,
            message="You haven't enrolled in any course.",
            data=[]
        )

    roadmaps_data = [
        DashboardRoadmapResponse(
            id=roadmap.id,
            title=roadmap.title,
            status=roadmap.status.value,
            progress_percentage=get_roadmap_with_progress(
                db, roadmap.id, current_user.id
            )['progress']['progress_percentage']
        )
        for roadmap in roadmaps
    ]
    
    return DashboardEnrollmentResponse(
        success=True,
        message=f"Found {len(roadmaps_data)} enrolled course(s).",
        data=roadmaps_data
    )

@router.post("/progress/update")
def update_topic_progress(
    progress_data: ProgressUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    topic = _get_topic_with_access_check(db, progress_data.topic_id, current_user.id)
    try:
        progress = update_progress(
            db, current_user.id, progress_data.topic_id, progress_data.status
        )
        
        roadmap = (
            db.query(Roadmap)
            .join(Milestone)
            .join(Topic)
            .filter(Topic.id == progress_data.topic_id)
            .first()
        )
        
        roadmap_data = get_roadmap_with_progress(db, roadmap.id, current_user.id)
        roadmap_progress = roadmap_data['progress']
        
        return {
            "message": "Progress updated successfully",
            "roadmap_progress": {
                "total_milestones": roadmap_progress['total_milestones'],
                "completed_milestones": roadmap_progress['completed_milestones'],
                "total_topics": roadmap_progress['total_topics'],
                "completed_topics": roadmap_progress['completed_topics'],
                "status": roadmap_progress['status']
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update progress: {str(e)}"
        )
