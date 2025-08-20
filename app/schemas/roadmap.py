from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime

class RoadmapCreate(BaseModel):
    selectedTopics: List[str]
    skillLevel: str
    duration: str
    title: Optional[str] = None

class TopicProgressResponse(BaseModel):
    status: str

class TopicResponse(BaseModel):
    id: str
    name: str
    explanation_md: Optional[str]
    progress: Optional[TopicProgressResponse] = None

class MilestoneProgressResponse(BaseModel):
    status: str

class MilestoneResponse(BaseModel):
    id: str
    name: str
    topics: List[TopicResponse]
    progress: Optional[MilestoneProgressResponse] = None

class RoadmapProgressResponse(BaseModel):
    total_milestones: int
    completed_milestones: int
    total_topics: int
    completed_topics: int
    progress_percentage: int
    status: str

class RoadmapResponse(BaseModel):
    id: str
    title: str
    level: str
    status: str
    milestones: List[MilestoneResponse]
    progress: Optional[RoadmapProgressResponse] = None

class ProgressUpdate(BaseModel):
    topic_id: str
    status: str

class DashboardRoadmapResponse(BaseModel):
    id: str
    title: str
    status: str

class DashboardEnrollmentResponse(BaseModel):
    success: bool
    message: str
    data: List[DashboardRoadmapResponse]