# --------------------------------------------------
# Clean Roadmap Service - LLM-Only Content Generation
# Single Groq model approach with batch processing
# 
# Features:
# - Optional duration parameter for roadmap creation
# - Enhanced JSON parsing with multiple error recovery strategies
# - Control character cleaning and escape sequence fixing
# - Robust error handling with fallback content generation
# - Regex-based field extraction for malformed JSON responses
# - Comprehensive content sanitization and character filtering
# - Intelligent caching system for topic explanations
# - Multiple fallback strategies for reliable content delivery
# --------------------------------------------------

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, List
from sqlalchemy.orm import Session
from app.models.roadmap import Roadmap, Milestone, Topic, UserProgress, RoadmapStatus, ProgressStatus
from app.schemas.roadmap import RoadmapCreate
from app.services.llm_client import call_groq_enhanced, LLMClientError
from app.services.roadmap_prompts import (
    create_batch_roadmap_prompt, 
    create_topic_explanation_prompt,
    create_topic_sources_prompt
)

logger = logging.getLogger(__name__)

_explanation_cache = {}



async def create_roadmap_with_pipeline(db: Session, roadmap_data: dict) -> Roadmap:
    """Create roadmap using single Groq model with batch processing"""
    start_time = datetime.now()
    
    title = roadmap_data.get("title")
    if not title or title.strip() == "":
        interests = roadmap_data.get("interests", [])
        skill_level = roadmap_data.get("level", "basic")
        
        if len(interests) == 1:
            title = f"{skill_level.title()} {interests[0]} Mastery Track"
        else:
            title = f"{skill_level.title()} Multi-Tech Learning Path"

    roadmap = Roadmap(
        creator_id=roadmap_data["creator_id"],
        title=title,
        level=roadmap_data["level"],
        interests=roadmap_data["interests"],
        timelines=roadmap_data["timelines"],
        start_date=roadmap_data.get("start_date"),
        end_date=roadmap_data.get("end_date"),
        status=RoadmapStatus.pending
    )

    db.add(roadmap)
    db.commit()
    db.refresh(roadmap)

    interests = roadmap_data["interests"]
    skill_level = roadmap_data["level"]
    
    try:
        logger.info(f"Batch processing roadmap for {len(interests)} interests using Groq only")
        
        all_topics = []
        milestone_order_counter = 1
        
        for interest in interests:
            try:
                timeline = roadmap_data.get("timelines", {}).get(interest) if roadmap_data.get("timelines") else None
                
                logger.info(f"Generating roadmap structure for {interest}" + (f" with duration: {timeline}" if timeline else " with LLM-suggested duration"))
                prompt = create_batch_roadmap_prompt(interest, timeline, skill_level)
                response = call_groq_enhanced(prompt, max_tokens=2500, temperature=0.7)
                
                cleaned_response = response.strip()
                if cleaned_response.startswith('```json'):
                    cleaned_response = cleaned_response[7:]
                if cleaned_response.endswith('```'):
                    cleaned_response = cleaned_response[:-3]
                cleaned_response = cleaned_response.strip()
                
                try:
                    roadmap_structure = json.loads(cleaned_response)
                except json.JSONDecodeError as parse_error:
                    logger.error(f"JSON parse error for {interest}: {parse_error}")
                    logger.error(f"Raw response: {response[:200]}...")
                    roadmap_structure = {
                        "milestones": [
                            {
                                "name": f"Learn {interest}",
                                "description": f"Master the fundamentals of {interest}",
                                "estimated_duration": timeline,
                                "topics": [
                                    f"Introduction to {interest}",
                                    f"Basic {interest} Concepts",
                                    f"Practical {interest} Applications",
                                    f"Advanced {interest} Topics",
                                    f"{interest} Best Practices",
                                    f"{interest} Project Work"
                                ]
                            }
                        ]
                    }
                milestones_data = roadmap_structure.get("milestones", [])
                
                for milestone_data in milestones_data:
                    clean_name = milestone_data.get("name", f"Learning {interest}").strip()
                    
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
                    topics_list = milestone_data.get("topics", [])
                    
                    for topic_name in topics_list:
                        topic = Topic(
                            milestone_id=milestone.id,
                            name=topic_name if isinstance(topic_name, str) else topic_name.get("name", "Unknown Topic"),
                            order_index=topic_order_counter
                        )
                        topic_order_counter += 1
                        db.add(topic)
                        db.flush()
                        all_topics.append(topic)
                        
            except Exception as e:
                logger.error(f"Failed to generate roadmap for '{interest}': {e}")
                milestone = Milestone(
                    roadmap_id=roadmap.id,
                    name=f"Milestone {milestone_order_counter}: Learn {interest}",
                    description=f"Master the fundamentals of {interest}",
                    estimated_duration=timeline or "2-3 weeks",
                    order_index=milestone_order_counter
                )
                milestone_order_counter += 1
                db.add(milestone)
                db.flush()
                
                topic = Topic(
                    milestone_id=milestone.id,
                    name=f"Introduction to {interest}",
                    order_index=1
                )
                db.add(topic)
                db.flush()
                all_topics.append(topic)

    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        raise e

    progress_records = []
    for topic in all_topics:
        progress = UserProgress(
            user_id=roadmap_data["creator_id"],
            topic_id=topic.id,
            status=ProgressStatus.not_started
        )
        progress_records.append(progress)

    db.add_all(progress_records)

    roadmap.status = RoadmapStatus.ready
    db.commit()
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    logger.info(f"Groq-only roadmap creation completed in {duration:.2f} seconds")
    
    return roadmap

def create_roadmap_with_llm_fast(db: Session, roadmap_data: dict) -> Roadmap:
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(create_roadmap_with_pipeline(db, roadmap_data))

def get_topic_explanation_with_metadata(db: Session, topic_id: str, skill_level: str = "basic") -> Optional[Dict]:
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        return None

    cache_key = f"{topic.name}_{skill_level}_metadata"
    
    if cache_key in _explanation_cache:
        logger.info(f"Using cached explanation with metadata for {topic.name}")
        return _explanation_cache[cache_key]
    
    try:
        logger.info(f"Generating Groq explanation for {topic.name}")
        prompt = create_topic_explanation_prompt(topic.name, skill_level)
        
        response = call_groq_enhanced(prompt, max_tokens=2000, temperature=0.7)
        
        cleaned_response = response.strip()
        if cleaned_response.startswith('```json'):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.endswith('```'):
            cleaned_response = cleaned_response[:-3]
        cleaned_response = cleaned_response.strip()
        
        import re
        cleaned_response = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', cleaned_response)
        cleaned_response = re.sub(r'\\(?!["\\/bfnrt])', r'\\\\', cleaned_response)
        
        try:
            explanation_data = json.loads(cleaned_response)
            logger.info(f"Successfully parsed JSON response for {topic.name}")
        except json.JSONDecodeError as e:
            logger.warning(f"Initial JSON parse failed, attempting to fix: {e}")
            
            explanation_data = None
            
            import re
            try:
                content_match = re.search(r'"content"\s*:\s*"(.*?)"(?=\s*,\s*"[^"]+"\s*:|$)', cleaned_response, re.DOTALL)
                difficulty_match = re.search(r'"difficulty_level"\s*:\s*"([^"]*)"', cleaned_response)
                time_match = re.search(r'"estimated_time"\s*:\s*"([^"]*)"', cleaned_response)
                concepts_match = re.search(r'"key_concepts"\s*:\s*\[(.*?)\]', cleaned_response, re.DOTALL)
                objectives_match = re.search(r'"learning_objectives"\s*:\s*\[(.*?)\]', cleaned_response, re.DOTALL)
                
                if content_match:
                    content = content_match.group(1)
                    content = content.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')
                    content = content.replace('\\r', '\r').replace('\\\\', '\\')
                    import string
                    content = ''.join(char for char in content if char in string.printable or char in '\n\r\t')
                    key_concepts = []
                    if concepts_match:
                        concepts_str = concepts_match.group(1)
                        key_concepts = [c.strip().strip('"') for c in concepts_str.split(',') if c.strip()]
                    
                    learning_objectives = []
                    if objectives_match:
                        objectives_str = objectives_match.group(1)
                        learning_objectives = [o.strip().strip('"') for o in objectives_str.split(',') if o.strip()]
                    
                    explanation_data = {
                        "content": content,
                        "difficulty_level": difficulty_match.group(1) if difficulty_match else skill_level,
                        "estimated_time": time_match.group(1) if time_match else "15-20 minutes",
                        "key_concepts": key_concepts,
                        "prerequisites": None,
                        "learning_objectives": learning_objectives
                    }
                    logger.info("Successfully extracted data using regex patterns")
                    
            except Exception as regex_error:
                logger.warning(f"Regex extraction failed: {regex_error}")
            
            if not explanation_data:
                try:
                    fixed_response = cleaned_response
                    fixed_response = re.sub(r'\\(?!["\\/bfnrt])', r'\\\\', fixed_response)
                    fixed_response = re.sub(r'(?<!\\)"(?=.*"content")', '\\"', fixed_response)
                    
                    explanation_data = json.loads(fixed_response)
                    logger.info("Successfully fixed JSON using escape sequence cleanup")
                    
                except Exception as cleanup_error:
                    logger.warning(f"JSON cleanup failed: {cleanup_error}")
            
            if not explanation_data:
                logger.warning("All JSON fix attempts failed, creating structured response from raw content")
                
                content_lines = response.split('\n')
                readable_content = []
                
                for line in content_lines:
                    if not any(marker in line for marker in ['{', '}', '"content":', '"difficulty_level":', '"estimated_time":']):
                        clean_line = line.strip().strip('"').strip(',')
                        if clean_line and not clean_line.startswith('\\'):
                            readable_content.append(clean_line)
                
                if readable_content:
                    content = f"# {topic.name}\n\n" + '\n\n'.join(readable_content[:10])
                else:
                    content = f"# {topic.name}\n\n## Introduction\nThis topic covers important concepts in {topic.name}.\n\n### Key Points\nDetailed information about {topic.name} and its practical applications."
                
                explanation_data = {
                    "content": content,
                    "difficulty_level": skill_level,
                    "estimated_time": "15-20 minutes",
                    "key_concepts": [topic.name.split()[-1] if topic.name else "concept"],
                    "prerequisites": None,
                    "learning_objectives": [f"Understand {topic.name}", f"Apply {topic.name} concepts"]
                }
        
        result = {
            "explanation": explanation_data.get("content", f"# {topic.name}\n\nLLM generation failed."),
            "difficulty_level": explanation_data.get("difficulty_level", skill_level),
            "estimated_time": explanation_data.get("estimated_time", "15-20 minutes"),
            "key_concepts": explanation_data.get("key_concepts", []),
            "prerequisites": explanation_data.get("prerequisites"),
            "learning_objectives": explanation_data.get("learning_objectives", [])
        }
        
        _explanation_cache[cache_key] = result
        
    except Exception as e:
        logger.error(f"Groq explanation generation failed for {topic.name}: {e}")
        raise Exception(f"Could not generate explanation for {topic.name}: {str(e)}")
    
    try:
        topic.explanation_md = result["explanation"]
        topic.difficulty_level = result["difficulty_level"]
        topic.estimated_time = result["estimated_time"]
        db.commit()
    except Exception as db_error:
        logger.warning(f"Failed to save explanation to database: {db_error}")
        db.rollback()
    
    return result

def get_topic_explanation_fast(db: Session, topic_id: str, user_context: Optional[Dict] = None) -> Optional[str]:
    skill_level = user_context.get("skill_level", "basic") if user_context else "basic"
    result = get_topic_explanation_with_metadata(db, topic_id, skill_level)
    
    if result:
        return result.get("explanation")
    return None

# Additional functions required by the API
def update_progress(db: Session, user_id: str, topic_id: str, status: str) -> bool:
    """Update progress for a topic"""
    try:
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
                progress.completed_at = datetime.now(timezone.utc)
            elif status == "in_progress" and not progress.started_at:
                progress.started_at = datetime.now(timezone.utc)
        
        db.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to update progress: {e}")
        db.rollback()
        return False

def get_roadmap_with_progress(db: Session, roadmap_id: str, user_id: str) -> Optional[Dict]:
    """Get roadmap with progress information - compatible with existing API structure"""
    roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
    if not roadmap:
        return None
    
    # Get milestones with topics and progress
    milestones = db.query(Milestone).filter(
        Milestone.roadmap_id == roadmap_id
    ).order_by(Milestone.order_index).all()
    
    milestones_data = []
    
    for milestone in milestones:
        topics = db.query(Topic).filter(
            Topic.milestone_id == milestone.id
        ).order_by(Topic.order_index).all()
        
        topics_data = []
        
        for topic in topics:
            progress = db.query(UserProgress).filter(
                UserProgress.user_id == user_id,
                UserProgress.topic_id == topic.id
            ).first()
            
            topic_data = {
                "topic": topic,
                "progress": {
                    "status": progress.status.value if progress else "not_started",
                    "started_at": progress.started_at.isoformat() if progress and progress.started_at else None,
                    "completed_at": progress.completed_at.isoformat() if progress and progress.completed_at else None,
                    "progress_percentage": 100.0 if progress and progress.status.value == "completed" else 0.0
                }
            }
            topics_data.append(topic_data)
        
        milestone_data = {
            "milestone": milestone,
            "topics": topics_data,
            "progress": {
                "status": "completed" if all(t["progress"]["status"] == "completed" for t in topics_data) else "in_progress" if any(t["progress"]["status"] != "not_started" for t in topics_data) else "not_started",
                "progress_percentage": round(sum(t["progress"]["progress_percentage"] for t in topics_data) / len(topics_data), 1) if topics_data else 0.0
            }
        }
        milestones_data.append(milestone_data)
    
    # Return structure compatible with _build_roadmap_response
    return {
        "roadmap": roadmap,
        "milestones": milestones_data,
        "progress": {
            "total_milestones": len(milestones_data),
            "completed_milestones": sum(1 for m in milestones_data if m["progress"]["status"] == "completed"),
            "total_topics": sum(len(m["topics"]) for m in milestones_data),
            "completed_topics": sum(sum(1 for t in m["topics"] if t["progress"]["status"] == "completed") for m in milestones_data),
            "progress_percentage": round(sum(m["progress"]["progress_percentage"] for m in milestones_data) / len(milestones_data), 1) if milestones_data else 0.0,
            "status": "completed" if all(m["progress"]["status"] == "completed" for m in milestones_data) else "in_progress" if any(m["progress"]["status"] != "not_started" for m in milestones_data) else "not_started"
        }
    }

def generate_topic_sources(db: Session, topic_id: str) -> List[Dict]:
    """Generate learning sources for a topic using Groq"""
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        return []
    
    try:
        prompt = create_topic_sources_prompt(topic.name)
        
        response = call_groq_enhanced(prompt, max_tokens=1000, temperature=0.7)
        
        # Clean JSON response
        cleaned_response = response.strip()
        if cleaned_response.startswith('```json'):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.endswith('```'):
            cleaned_response = cleaned_response[:-3]
        cleaned_response = cleaned_response.strip()
        
        sources_data = json.loads(cleaned_response)
        return sources_data.get("sources", [])
        
    except Exception as e:
        logger.error(f"Failed to generate sources for {topic.name}: {e}")
        # Return basic fallback sources
        return [
            {
                "title": f"Learn {topic.name} - Official Documentation",
                "url": "#",
                "type": "documentation",
                "description": f"Official documentation and guides for {topic.name}"
            }
        ]
