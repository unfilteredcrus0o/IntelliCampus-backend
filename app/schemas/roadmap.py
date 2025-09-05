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
from typing import List, Dict, Optional, Literal
from datetime import datetime

class RoadmapCreate(BaseModel):
    selectedTopics: List[str]
    skillLevel: str
    duration: str
    title: Optional[str] = None
    due_date: Optional[datetime] = Field(None, description="Due date for auto-assigned courses (SuperAdmin only)")

class TopicProgressResponse(BaseModel):
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress_percentage: int

class TopicResponse(BaseModel):
    id: str
    name: str
    explanation_md: Optional[str] = None
    progress: TopicProgressResponse

class MilestoneProgressResponse(BaseModel):
    status: str
    progress_percentage: int

class MilestoneResponse(BaseModel):
    id: str
    name: str
    topics: List[TopicResponse]
    progress: MilestoneProgressResponse

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
    progress: RoadmapProgressResponse

class ProgressUpdate(BaseModel):
    status: str = Field(..., description="Topic status: not_started, in_progress, completed")

class DashboardRoadmapResponse(BaseModel):
    id: str
    title: str
    status: str
    progress_percentage: int

class DashboardEnrollmentResponse(BaseModel):
    roadmap_id: str
    roadmap_title: str
    user_id: str
    user_name: str
    role: str
    enrolled_at: Optional[datetime] = None
    total_topics: int
    completed_topics: int = 0
    progress_percentage: int = 0
    last_accessed: Optional[datetime] = None
    assignment_id: Optional[int] = None
    assigned_by: Optional[str] = None
    assigner_name: Optional[str] = None
    due_date: Optional[datetime] = None
    assigned_at: Optional[datetime] = None
    status: Literal["not_started", "in_progress", "completed", "enrolled"] = "enrolled"

class AssignmentCreate(BaseModel):
    roadmap_id: str
    assigned_to: List[str]
    due_date: Optional[str] = None

class AssignmentResponse(BaseModel):
    id: int
    roadmap_id: str
    assigned_by: str
    assigned_to: str
    due_date: Optional[datetime] = None
    created_at: datetime

class BulkAssignmentResponse(BaseModel):
    success: bool
    message: str
    created_assignments: List[AssignmentResponse]
    failed_assignments: List[Dict]