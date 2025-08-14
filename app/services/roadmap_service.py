# --------------------------------------------------
# roadmap_service.py
# Handles roadmap creation, topic explanations, and progress tracking.
#
# - create_roadmap_with_llm:
#     Creates a roadmap, generating milestones/topics via LLM.
#     Falls back to a basic structure if JSON parsing fails.
#
# - get_topic_explanation:
#     Returns or generates (via LLM) a Markdown explanation for a topic.
#
# - update_progress:
#     Creates/updates a user's topic progress, tracking start/completion times.
#
# Uses:
# - SQLAlchemy models: Roadmap, Milestone, Topic, UserProgress
# - Enums: RoadmapStatus, ProgressStatus
# - call_llm for AI-generated content
# --------------------------------------------------

from sqlalchemy.orm import Session
from app.models.roadmap import Roadmap, Milestone, Topic, UserProgress, RoadmapStatus, ProgressStatus
from app.schemas.roadmap import RoadmapCreate
from app.services.llm_client import call_llm
from app.services.roadmap_prompts import CREATE_ROADMAP_PROMPT, TOPIC_EXPLANATION_PROMPT
import json
from datetime import datetime

def create_roadmap_with_llm(db: Session, roadmap_data: dict):

    roadmap = Roadmap(
    user_id=roadmap_data["user_id"],
    title=roadmap_data.get("title", "Custom Roadmap"),
    level=roadmap_data["level"],
    interests=roadmap_data["interests"],
    timelines=roadmap_data["timelines"],
    status=RoadmapStatus.pending
    )

    db.add(roadmap)
    db.commit()
    db.refresh(roadmap)
    milestone_order_counter = 1

    for interest in roadmap_data["interests"]:
        timeline = roadmap_data["timelines"].get(interest, "7 days")

        prompt = CREATE_ROADMAP_PROMPT.format(
            selectedTopics=interest,
            duration=timeline,
            skillLevel=roadmap_data["level"]
        )

        llm_response = call_llm(prompt)

        try:
            roadmap_structure = json.loads(llm_response)

            for milestone_data in roadmap_structure["milestones"]:
                clean_name = milestone_data["name"].strip()
                if clean_name.lower().startswith("milestone "):
                    parts = clean_name.split(":", 1)
                    if len(parts) > 1:
                        clean_name = parts[1].strip()

                milestone = Milestone(
                    roadmap_id=roadmap.id,
                    name=f"Milestone {milestone_order_counter}: {clean_name}",
                    order=milestone_order_counter
                )
                milestone_order_counter += 1
                db.add(milestone)
                db.flush()

                for topic_name in milestone_data["topics"]:
                    topic = Topic(
                        milestone_id=milestone.id,
                        name=topic_name
                    )
                    db.add(topic)

            db.commit()

        except json.JSONDecodeError:

            milestone = Milestone(
                roadmap_id=roadmap.id,
                name=f"Milestone {milestone_order_counter}: {interest} Fundamentals",
                order=milestone_order_counter
            )
            milestone_order_counter += 1
            db.add(milestone)
            db.flush()

            topic = Topic(
                milestone_id=milestone.id,
                name=f"Basic {interest}"
            )
            db.add(topic)
            db.commit()

    roadmap.status = RoadmapStatus.ready
    db.commit()

    return roadmap

def get_topic_explanation(db: Session, topic_id: str) -> str:
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise ValueError("Topic not found")

    if topic.explanation_md:
        return topic.explanation_md

    prompt = TOPIC_EXPLANATION_PROMPT.format(topic_name=topic.name)

    explanation = call_llm(prompt)

    topic.explanation_md = explanation
    db.commit()

    return explanation

def update_progress(db: Session, user_id: str, topic_id: str, status: str):
    progress = db.query(UserProgress).filter(
        UserProgress.user_id == user_id,
        UserProgress.topic_id == topic_id
    ).first()

    if not progress:
        progress = UserProgress(
            user_id=user_id,
            topic_id=topic_id,
            status=ProgressStatus(status)
        )
        db.add(progress)
    else:
        progress.status = ProgressStatus(status)

    if status == "completed":
        progress.completed_at = datetime.utcnow()
    elif status == "in_progress" and not progress.started_at:
        progress.started_at = datetime.utcnow()

    db.commit()
    return progress