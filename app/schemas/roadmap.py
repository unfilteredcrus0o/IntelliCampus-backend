from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime

class RoadmapCreate(BaseModel):
    selectedTopics: List[str]
    skillLevel: str
    duration: str
    title: Optional[str] = None

class TopicResponse(BaseModel):
    id: str
    name: str
    explanation_md: Optional[str]

class MilestoneResponse(BaseModel):
    id: str
    name: str
    topics: List[TopicResponse]

class RoadmapResponse(BaseModel):
    id: str
    title: str
    level: str
    status: str
    milestones: List[MilestoneResponse]

class ProgressUpdate(BaseModel):
    topic_id: str
    status: str
