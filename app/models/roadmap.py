"""
Roadmap Data Models  
=====================================
Comprehensive SQLAlchemy ORM models for learning management system.

Models:
- Roadmap: Learning path with creator tracking and status management
- Milestone: Ordered stages within roadmaps containing multiple topics  
- Topic: Individual learning units with AI-generated explanations
- UserProgress: Tracks user completion status per topic with timestamps
- Assignment: Manager-to-user roadmap assignments with due dates

Features:
- UUID primary keys for roadmap, milestone, topic
- Proper foreign key relationships with CASCADE deletes
- Enum types for status consistency  
- Creator-based ownership separate from assignment system
- Comprehensive indexing for query performance
"""

from sqlalchemy import Column, String, Enum, ForeignKey, Integer, Text, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
import uuid
from app.db.database import Base

class RoadmapStatus(str, enum.Enum):
    pending = "pending"
    ready = "ready" 
    completed = "completed"

class ProgressStatus(str, enum.Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"

class Roadmap(Base):
    __tablename__ = "roadmaps"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    creator_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, default="Custom Roadmap")
    level = Column(String, nullable=False)
    interests = Column(JSON)
    timelines = Column(JSON)
    status = Column(Enum(RoadmapStatus), default=RoadmapStatus.pending)
    start_date = Column(String, nullable=True)
    end_date = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    milestones = relationship("Milestone", back_populates="roadmap", cascade="all, delete", order_by="Milestone.order_index")

class Milestone(Base):
    __tablename__ = "milestones"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)  # UUID string PK
    roadmap_id = Column(String, ForeignKey("roadmaps.id", ondelete="CASCADE"))
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    estimated_duration = Column(String, nullable=True)
    order_index = Column(Integer, nullable=False)

    roadmap = relationship("Roadmap", back_populates="milestones")
    topics = relationship("Topic", back_populates="milestone", cascade="all, delete")
    quizzes = relationship("Quiz", back_populates="milestone", cascade="all, delete")

class Topic(Base):
    __tablename__ = "topics"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)  # UUID string PK
    milestone_id = Column(String, ForeignKey("milestones.id", ondelete="CASCADE"))
    name = Column(String, nullable=False)
    explanation_md = Column(Text, nullable=True)
    order_index = Column(Integer, nullable=False)
    
    milestone = relationship("Milestone", back_populates="topics")
    progress = relationship("UserProgress", back_populates="topic", cascade="all, delete")
    quizzes = relationship("Quiz", back_populates="topic", cascade="all, delete")

class UserProgress(Base):
    __tablename__ = "user_progress"
    
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    topic_id = Column(String, ForeignKey("topics.id", ondelete="CASCADE"))
    status = Column(Enum(ProgressStatus), default=ProgressStatus.not_started)
    last_accessed = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    topic = relationship("Topic", back_populates="progress")

class Assignment(Base):
    __tablename__ = "assignments"
    
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    roadmap_id = Column(String, ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_by = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    assigned_to = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    due_date = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)