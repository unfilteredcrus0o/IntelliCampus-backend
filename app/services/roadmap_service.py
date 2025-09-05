# --------------------------------------------------
# roadmap_service.py
# Enhanced roadmap service with better error handling and LLM integration
# --------------------------------------------------

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, List

from sqlalchemy.orm import Session, joinedload
from app.models.roadmap import Roadmap, Milestone, Topic, UserProgress, RoadmapStatus, ProgressStatus
from app.schemas.roadmap import RoadmapCreate
from app.services.llm_client import call_llm_with_retry, call_llm_with_json_validation, LLMClientError
from app.services.roadmap_prompts import (
    CREATE_ROADMAP_TITLE_PROMPT,
    CREATE_ROADMAP_PROMPT, 
    TOPIC_EXPLANATION_PROMPT,
    GENERATE_TOPIC_SOURCES_PROMPT,
    ENHANCE_EXPLANATION_PROMPT,
    CONTEXT_AWARE_EXPLANATION_PROMPT
)

logger = logging.getLogger(__name__)

def generate_roadmap_title_with_llm(interests: List[str], skill_level: str, duration: str) -> str:
    """
    Generate a professional, engaging roadmap title using LLM
    
    Args:
        interests: List of topics/subjects for the roadmap
        skill_level: The skill level (beginner, intermediate, advanced)
        duration: Duration of the roadmap (e.g., "4 weeks", "2 months")
    
    Returns:
        Generated title string, or fallback title if LLM fails
    """
    try:

        topics_text = ", ".join(interests) if interests else "General Learning"

        prompt = CREATE_ROADMAP_TITLE_PROMPT.format(
            selectedTopics=topics_text,
            skillLevel=skill_level,
            duration=duration
        )

        logger.info(f"Generating title with LLM for topics: {topics_text}, level: {skill_level}")
        generated_title = call_llm_with_retry(prompt, max_retries=2)

        generated_title = generated_title.strip().strip('"\'')
        
        if len(generated_title) < 5 or len(generated_title) > 100:
            raise ValueError(f"Generated title length out of bounds: {len(generated_title)}")
            
        logger.info(f"LLM generated title: '{generated_title}'")
        return generated_title
        
    except Exception as e:
        logger.warning(f"Failed to generate title with LLM: {str(e)}, using fallback")
        
        if interests:
            if len(interests) == 1:
                return f"{skill_level.title()} {interests[0]} Mastery"
            elif len(interests) == 2:
                return f"{interests[0]} & {interests[1]} {skill_level.title()} Track"
            else:
                return f"Multi-Tech {skill_level.title()} Bootcamp"
        else:
            return f"{skill_level.title()} Learning Track"

def create_roadmap_with_llm(db: Session, roadmap_data: dict) -> Roadmap:
    title = roadmap_data.get("title")
    if not title or title.strip() == "":
        interests = roadmap_data.get("interests", [])
        skill_level = roadmap_data.get("level", "beginner")
        duration = roadmap_data.get("timelines", {})
        
        if isinstance(duration, dict) and duration:
            duration_str = next(iter(duration.values()))
        else:
            duration_str = "4 weeks"
            
        title = generate_roadmap_title_with_llm(interests, skill_level, duration_str)

    roadmap = Roadmap(
        creator_id=roadmap_data["creator_id"],
        title=title,
        level=roadmap_data["level"],
        interests=roadmap_data["interests"],
        timelines=roadmap_data["timelines"],
        status=RoadmapStatus.pending
    )

    db.add(roadmap)
    db.commit()
    db.refresh(roadmap)
    milestone_order_counter = 1
    all_topics = []

    for interest in roadmap_data["interests"]:
        timeline = roadmap_data["timelines"].get(interest, "7 days")

        prompt = CREATE_ROADMAP_PROMPT.format(
            selectedTopics=interest,
            duration=timeline,
            skillLevel=roadmap_data["level"]
        )

        try:
            llm_response = call_llm_with_json_validation(prompt, max_retries=3)
            roadmap_structure = json.loads(llm_response)

            milestones_data = roadmap_structure.get("milestones", [])         
            for milestone_data in milestones_data:
                clean_name = milestone_data.get("name", f"Learning {interest}").strip()
                if clean_name.lower().startswith("milestone "):
                    parts = clean_name.split(":", 1)
                    if len(parts) > 1:
                        clean_name = parts[1].strip()

                milestone = Milestone(
                    roadmap_id=roadmap.id,
                    name=f"Milestone {milestone_order_counter}: {clean_name}",
                    description=milestone_data.get("description", ""),
                    estimated_duration=milestone_data.get("estimated_duration", timeline),
                    order_index=milestone_order_counter
                )
                milestone_order_counter += 1
                db.add(milestone)
                db.flush()

                topic_order_counter = 1
                topics_list = milestone_data.get("topics", [f"Learn {interest}"])
                
                for topic_name in topics_list:
                    topic = Topic(
                        milestone_id=milestone.id,
                        name=topic_name,
                        order_index=topic_order_counter
                    )
                    topic_order_counter += 1
                    db.add(topic)
                    db.flush()
                    all_topics.append(topic)        


        except (json.JSONDecodeError, LLMClientError) as e:
            logger.warning(f"LLM failed for '{interest}', using fallback: {type(e).__name__}")
            milestone = Milestone(
                roadmap_id=roadmap.id,
                name=f"Milestone {milestone_order_counter}: Learn {interest}",
                description=f"Comprehensive learning path for {interest}",
                estimated_duration=timeline,
                order_index=milestone_order_counter
            )
            milestone_order_counter += 1
            db.add(milestone)
            db.flush()

            topic = Topic(
                milestone_id=milestone.id,
                name=f"Master {interest} Fundamentals",
                order_index=1
            )
            db.add(topic)
            db.flush()
            all_topics.append(topic)

    for topic in all_topics:
        progress = UserProgress(
            user_id=roadmap_data["creator_id"],
            topic_id=topic.id,
            status=ProgressStatus.not_started
        )
        db.add(progress)

    roadmap.status = RoadmapStatus.ready
    db.commit()
    return roadmap

def get_topic_explanation(db: Session, topic_id: str, user_context: Optional[Dict] = None) -> Optional[str]:
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        return None

    if topic.explanation_md and not user_context:
        return topic.explanation_md
    
    try:
        if user_context:

            prompt = CONTEXT_AWARE_EXPLANATION_PROMPT.format(
                topic_name=topic.name,
                skill_level=user_context.get("skill_level", "beginner"),
                learning_goals=user_context.get("learning_goals", "general understanding"),
                time_available=user_context.get("time_available", "flexible"),
                completed_topics=", ".join(user_context.get("completed_topics", []))
            )
        else:
            prompt = TOPIC_EXPLANATION_PROMPT.format(topic_name=topic.name)

        response = call_llm_with_json_validation(prompt, max_retries=2)
        explanation_data = json.loads(response)
        
        explanation_content = explanation_data.get("content", f"# {topic.name}\n\nContent generation failed.")
        
        if not user_context:
            topic.explanation_md = explanation_content
            db.commit()
        
        return explanation_content
        
    except (LLMClientError, json.JSONDecodeError) as e:
        
        fallback = f"""# {topic.name}

## Overview
This topic covers the fundamentals of {topic.name}.

## What You'll Learn
- Core concepts and principles
- Practical applications
- Best practices

## Getting Started
Begin by understanding the basic concepts and gradually work through practical examples.

*Note: Detailed explanation generation is temporarily unavailable. Please check back later for enhanced content.*
"""
        return fallback

def enhance_topic_explanation(db: Session, topic_id: str) -> Optional[str]:
    """Enhance existing topic explanation with better content"""
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic or not topic.explanation_md:
        logger.warning(f"Topic or explanation not found for enhancement: {topic_id}")
        return None
    
    try:
        prompt = ENHANCE_EXPLANATION_PROMPT.format(
            current_explanation=topic.explanation_md,
            topic_name=topic.name
        )
        
        response = call_llm_with_json_validation(prompt)
        enhancement_data = json.loads(response)
        
        enhanced_content = enhancement_data.get("enhanced_content", topic.explanation_md)
        
        topic.explanation_md = enhanced_content
        db.commit()
        return enhanced_content
        
    except (LLMClientError, json.JSONDecodeError) as e:
        logger.error(f"Failed to enhance explanation for topic {topic.name}: {e}")
        return topic.explanation_md

def generate_topic_sources(db: Session, topic_id: str) -> List[Dict]:
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        return []
    
    try:
        prompt = GENERATE_TOPIC_SOURCES_PROMPT.format(topic_name=topic.name)
        response = call_llm_with_json_validation(prompt)
        sources_data = json.loads(response)
        
        return sources_data
        
    except (LLMClientError, json.JSONDecodeError) as e:
        logger.error(f"Failed to generate sources for topic {topic.name}: {e}")
        return []

def update_progress(db: Session, user_id: str, topic_id: str, status: str) -> UserProgress:
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
    
    old_status = progress.status.value if progress.status else "not_started"
    new_status = ProgressStatus(status)
    
    if status == "not_started":
        progress.status = ProgressStatus.not_started
        progress.started_at = None
        progress.completed_at = None
    elif status == "in_progress":
        progress.status = ProgressStatus.in_progress
        if not progress.started_at:
            progress.started_at = datetime.now(timezone.utc)
        progress.completed_at = None
    elif status == "completed":
        progress.status = ProgressStatus.completed
        if not progress.started_at:
            progress.started_at = datetime.now(timezone.utc)
        progress.completed_at = datetime.now(timezone.utc)
    progress.last_accessed = datetime.now(timezone.utc)
    db.commit()
    return progress

def get_roadmap_with_progress(db: Session, roadmap_id: str, user_id: str) -> Optional[Dict]:
    from app.models.roadmap import Assignment
    
    roadmap = (
        db.query(Roadmap)
        .options(
            joinedload(Roadmap.milestones)
            .joinedload(Milestone.topics)
            .joinedload(Topic.progress)
        )
        .filter(Roadmap.id == roadmap_id)
        .first()
    )
    
    if not roadmap:
        return None
    
    has_access = False
    if roadmap.creator_id == user_id:
        has_access = True
    else:
        assignment = db.query(Assignment).filter(
            Assignment.roadmap_id == roadmap_id,
            Assignment.assigned_to == user_id
        ).first()
        if assignment:
            has_access = True
    
    if not has_access:
        return None
    
    all_topic_ids = []
    for milestone in roadmap.milestones:
        for topic in milestone.topics:
            all_topic_ids.append(topic.id)
    
    progress_data = db.query(UserProgress).filter(
        UserProgress.user_id == user_id,
        UserProgress.topic_id.in_(all_topic_ids)
    ).all()
    
    progress_lookup = {p.topic_id: p for p in progress_data}
    
    roadmap_data = {
        'roadmap': roadmap,
        'milestones': [],
        'metadata': roadmap.metadata or {}
    }
    
    total_topics = 0
    completed_topics = 0
    in_progress_topics = 0
    total_milestones = len(roadmap.milestones)
    completed_milestones = 0
    
    for milestone in roadmap.milestones:
        milestone_topics = []
        milestone_completed = 0
        milestone_in_progress = 0
        milestone_total = len(milestone.topics)
        
        for topic in milestone.topics:
            total_topics += 1
            progress = progress_lookup.get(topic.id)
            
            if progress:
                topic_status = progress.status.value
                topic_progress_percentage = (
                    100 if topic_status == "completed" 
                    else 50 if topic_status == "in_progress" 
                    else 0
                )
                
                if topic_status == "completed":
                    completed_topics += 1
                    milestone_completed += 1
                elif topic_status == "in_progress":
                    in_progress_topics += 1
                    milestone_in_progress += 1
            else:
                topic_status = "not_started"
                topic_progress_percentage = 0
                progress = None
            
            topic_data = {
                'topic': topic,
                'progress': {
                    'status': topic_status,
                    'started_at': progress.started_at if progress else None,
                    'completed_at': progress.completed_at if progress else None,
                    'last_accessed': progress.last_accessed if progress else None,
                    'progress_percentage': topic_progress_percentage,
                    'metadata': progress.metadata if progress else {}
                }
            }
            milestone_topics.append(topic_data)
        
        milestone_progress_percentage = int((milestone_completed / milestone_total * 100)) if milestone_total > 0 else 0
        
        if milestone_completed == milestone_total:
            milestone_status = "completed"
            completed_milestones += 1
        elif milestone_completed > 0 or milestone_in_progress > 0:
            milestone_status = "in_progress"
        else:
            milestone_status = "not_started"
        
        milestone_data = {
            'milestone': milestone,
            'topics': milestone_topics,
            'progress': {
                'status': milestone_status,
                'progress_percentage': milestone_progress_percentage,
                'completed_topics': milestone_completed,
                'total_topics': milestone_total
            }
        }
        roadmap_data['milestones'].append(milestone_data)
    
    roadmap_progress_percentage = int((completed_topics / total_topics * 100)) if total_topics > 0 else 0
    
    if completed_topics == total_topics:
        roadmap_status = "completed"
    elif completed_topics > 0 or in_progress_topics > 0:
        roadmap_status = "in_progress"
    else:
        roadmap_status = "not_started"
    
    roadmap_data['progress'] = {
        'total_milestones': total_milestones,
        'completed_milestones': completed_milestones,
        'total_topics': total_topics,
        'completed_topics': completed_topics,
        'in_progress_topics': in_progress_topics,
        'progress_percentage': roadmap_progress_percentage,
        'status': roadmap_status
    }
    
    return roadmap_data

def get_user_learning_context(db: Session, user_id: str, topic_id: str) -> Dict:
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        return {}
    
    milestone = db.query(Milestone).filter(Milestone.id == topic.milestone_id).first()
    if not milestone:
        return {}
    
    roadmap_data = get_roadmap_with_progress(db, milestone.roadmap_id, user_id)
    if not roadmap_data:
        return {}
    
    completed_topics = []
    skill_indicators = []
    
    for milestone_data in roadmap_data['milestones']:
        for topic_data in milestone_data['topics']:
            if topic_data['progress']['status'] == 'completed':
                completed_topics.append(topic_data['topic'].name)
            if topic_data['progress']['status'] in ['completed', 'in_progress']:
                skill_indicators.append(topic_data['topic'].name)
    
    total_topics = roadmap_data['progress']['total_topics']
    completed_count = len(completed_topics)
    
    if completed_count == 0:
        skill_level = "beginner"
    elif completed_count < total_topics * 0.3:
        skill_level = "beginner"
    elif completed_count < total_topics * 0.7:
        skill_level = "intermediate"
    else:
        skill_level = "advanced"
    
    return {
        "skill_level": skill_level,
        "completed_topics": completed_topics,
        "learning_goals": roadmap_data['roadmap'].interests,
        "time_available": "flexible" 
    }

def auto_enroll_user_in_roadmap(db: Session, user_id: str, roadmap_id: str) -> int:

    topic_rows = (
        db.query(Topic.id)
        .join(Milestone, Milestone.id == Topic.milestone_id)
        .filter(Milestone.roadmap_id == roadmap_id)
        .all()
    )

    topic_ids = {row[0] for row in topic_rows}
    if not topic_ids:
        logger.warning(f"No topics in roadmap {roadmap_id}")
        return 0

    existing_rows = (
        db.query(UserProgress.topic_id)
        .filter(UserProgress.user_id == user_id, UserProgress.topic_id.in_(topic_ids))
        .all()
    )
    existing_topic_ids = {row[0] for row in existing_rows}

    created_count = 0
    for topic_id in (topic_ids - existing_topic_ids):
        db.add(
            UserProgress(
                user_id=user_id,
                topic_id=topic_id,
                status=ProgressStatus.not_started,
            )
        )
        created_count += 1
    return created_count