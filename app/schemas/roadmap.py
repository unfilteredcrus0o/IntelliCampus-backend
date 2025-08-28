"""
Roadmap & Assignment Schemas
=====================================
Pydantic models for API request/response validation and serialization.

Roadmap Schemas:
- RoadmapCreate: Input for creating new learning roadmaps
- RoadmapResponse: Complete roadmap data with progress tracking
- MilestoneResponse/TopicResponse: Nested roadmap structure
- ProgressUpdate: Topic progress status updates

Assignment Schemas:
- AssignmentCreate: Bulk assignment input with validation
- AssignmentResponse: Individual assignment details  
- BulkAssignmentResponse: Comprehensive assignment operation results

Features:
- Field validation with descriptive error messages
- Flexible date format support
- Nested response structures for complex data
- Comprehensive success/failure reporting
"""

from pydantic import BaseModel, Field
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
    creator_id: str
    milestones: List[MilestoneResponse]
    progress: Optional[RoadmapProgressResponse] = None

class ProgressUpdate(BaseModel):
    topic_id: str
    status: str

class DashboardRoadmapResponse(BaseModel):
    id: str
    title: str
    status: str
    progress_percentage: int

class DashboardEnrollmentResponse(BaseModel):
    success: bool
    message: str
    data: List[DashboardRoadmapResponse]

class AssignmentCreate(BaseModel):
    roadmap_id: str = Field(description="UUID of the roadmap to assign")
    assigned_to: List[str] = Field(min_items=1, description="List of user UUIDs (at least 1 required)")
    due_date: Optional[str] = Field(None, description="Due date in YYYY-MM-DD format")

class AssignmentResponse(BaseModel):
    id: str
    roadmap_id: str
    assigned_by: str
    assigned_to: str
    due_date: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class BulkAssignmentResponse(BaseModel):
    success: bool
    message: str
    created_assignments: List[AssignmentResponse]
    failed_assignments: List[Dict[str, str]] = []