# ==========================================
# Roadmap API Routes
# ------------------------------------------
# Provides endpoints to:
# - Create a new roadmap using LLM service.
# - Retrieve a roadmap with milestones and topics (404 if not found).
# - Get markdown explanation for a topic (404 if not found).
#
# Dependencies:
# - SQLAlchemy models: Roadmap, Milestone, Topic
# - Schemas: RoadmapCreate, RoadmapResponse, MilestoneResponse, TopicResponse
# - Services: create_roadmap_with_llm, get_topic_explanation
# ==========================================

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from app.db.database import get_db
from app.models.roadmap import Roadmap, Milestone, Topic
from app.schemas.roadmap import RoadmapCreate, RoadmapResponse, MilestoneResponse, TopicResponse
from app.services.roadmap_service import create_roadmap_with_llm, get_topic_explanation

router = APIRouter(prefix="/api", tags=["Roadmap"])

@router.post("/roadmap/create")
def create_roadmap(payload: RoadmapCreate, db: Session = Depends(get_db)):

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
        "user_id": payload.user_id
    }
    roadmap = create_roadmap_with_llm(db, roadmap_data)
    return {"roadmap_id": roadmap.id, "status": roadmap.status.value}

@router.get("/roadmap/{roadmap_id}", response_model=RoadmapResponse)
def get_roadmap(roadmap_id: str, db: Session = Depends(get_db)):
    roadmap = (
        db.query(Roadmap)
          .options(
              joinedload(Roadmap.milestones)
                .joinedload(Milestone.topics)
          )
          .filter(Roadmap.id == roadmap_id)
          .first()
    )
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")

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
def get_explanation(topic_id: str, db: Session = Depends(get_db)):
    try:
        explanation_md = get_topic_explanation(db, topic_id)
        return {"explanation": explanation_md}
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Topic not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve explanation: {str(e)}")
