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
from app.schemas.roadmap import RoadmapCreate, RoadmapResponse, MilestoneResponse, TopicResponse, ProgressUpdate, TopicProgressResponse, MilestoneProgressResponse, RoadmapProgressResponse, DashboardRoadmapResponse, DashboardEnrollmentResponse
from app.services.roadmap_service import create_roadmap_with_llm, get_topic_explanation, update_progress, get_roadmap_with_progress
from app.core.security import get_current_user

router = APIRouter(prefix="/api", tags=["Roadmap"])

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
        "user_id": current_user.id
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

    roadmap = roadmap_data['roadmap']
    
    milestones_data = []
    for milestone_data in roadmap_data['milestones']:
        milestone = milestone_data['milestone']
        milestone_progress = milestone_data['progress']
        
        topics_data = []
        for topic_data in milestone_data['topics']:
            topic = topic_data['topic']
            topic_progress = topic_data['progress']
            
            topics_data.append(TopicResponse(
                id=topic.id,
                name=topic.name,
                explanation_md=topic.explanation_md,
                progress=TopicProgressResponse(
                    status=topic_progress['status']
                )
            ))
        
        milestones_data.append(MilestoneResponse(
            id=milestone.id,
            name=milestone.name,
            topics=topics_data,
            progress=MilestoneProgressResponse(
                status=milestone_progress['status']
            )
        ))

    roadmap_progress = roadmap_data['progress']
    return RoadmapResponse(
        id=roadmap.id,
        title=roadmap.title,
        level=roadmap.level,
        status=roadmap.status.value,
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

@router.get("/topic/{topic_id}/explanation")
def get_explanation(
    topic_id: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):


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
    roadmaps = (
        db.query(Roadmap)
        .filter(Roadmap.user_id == current_user.id)
        .all()
    )
    
    roadmaps_data = []
    for roadmap in roadmaps:
        roadmap_data = get_roadmap_with_progress(db, roadmap.id, current_user.id)
        
        if roadmap_data:
            roadmap_obj = roadmap_data['roadmap']
            
            milestones_data = []
            for milestone_data in roadmap_data['milestones']:
                milestone = milestone_data['milestone']
                milestone_progress = milestone_data['progress']
                
                topics_data = []
                for topic_data in milestone_data['topics']:
                    topic = topic_data['topic']
                    topic_progress = topic_data['progress']
                    
                    topics_data.append(TopicResponse(
                        id=topic.id,
                        name=topic.name,
                        explanation_md=topic.explanation_md,
                        progress=TopicProgressResponse(
                            status=topic_progress['status']
                        )
                    ))
                
                milestones_data.append(MilestoneResponse(
                    id=milestone.id,
                    name=milestone.name,
                    topics=topics_data,
                    progress=MilestoneProgressResponse(
                        status=milestone_progress['status']
                    )
                ))

            roadmap_progress = roadmap_data['progress']
            roadmaps_data.append(RoadmapResponse(
                id=roadmap_obj.id,
                title=roadmap_obj.title,
                level=roadmap_obj.level,
                status=roadmap_obj.status.value,
                milestones=milestones_data,
                progress=RoadmapProgressResponse(
                    total_milestones=roadmap_progress['total_milestones'],
                    completed_milestones=roadmap_progress['completed_milestones'],
                    total_topics=roadmap_progress['total_topics'],
                    completed_topics=roadmap_progress['completed_topics'],
                    progress_percentage=roadmap_progress['progress_percentage'],
                    status=roadmap_progress['status']
                )
            ))
    
    return roadmaps_data

@router.get("/dashboard/enrollments", response_model=DashboardEnrollmentResponse)
def get_dashboard_enrollments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    roadmaps = (
        db.query(Roadmap)
        .filter(Roadmap.user_id == current_user.id)
        .all()
    )
    
    if not roadmaps:
        return DashboardEnrollmentResponse(
            success=False,
            message="You haven't enrolled in any course.",
            data=[]
        )

    roadmaps_data = []
    for roadmap in roadmaps:
        roadmap_progress_data = get_roadmap_with_progress(db, roadmap.id, current_user.id)
        progress_percentage = roadmap_progress_data['progress']['progress_percentage']
        
        roadmaps_data.append(DashboardRoadmapResponse(
            id=roadmap.id,
            title=roadmap.title,
            status=roadmap.status.value,
            progress_percentage=progress_percentage
        ))
    
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
