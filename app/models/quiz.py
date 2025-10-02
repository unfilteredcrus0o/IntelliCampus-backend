"""
Quiz Data Models  
=====================================
SQLAlchemy ORM models for the quiz system supporting topic-level quick quizzes.

Models:
- Quiz: Topic-level quizzes with LLM-generated content
- Question: Individual quiz questions (MCQ, coding, or mixed)  
- Choice: Answer choices for MCQ questions
- QuizAttempt: User attempts at quizzes with scoring and completion tracking

Features:
- Support for multiple question types (mcq_only, coding_only, mixed)
- LLM-generated quiz content with caching
- Progress tracking with attempt history
- Proper foreign key relationships with CASCADE deletes
- UUID primary keys for quizzes and questions
"""

from sqlalchemy import Column, String, Enum, ForeignKey, Integer, Text, DateTime, JSON, Boolean, Float
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
import uuid
from app.db.database import Base

class QuizType(str, enum.Enum):
    mcq_only = "mcq_only"
    coding_only = "coding_only"  
    mixed = "mixed"

class QuizScope(str, enum.Enum):
    quick = "quick"
    comprehensive = "comprehensive"

class QuestionKind(str, enum.Enum):
    mcq = "mcq"
    coding = "coding"

class Generator(str, enum.Enum):
    llm = "llm"
    manual = "manual"

class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    topic_id = Column(String, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    milestone_id = Column(String, ForeignKey("milestones.id", ondelete="CASCADE"), nullable=True, index=True)
    quiz_type = Column(Enum(QuizType), nullable=False)
    scope = Column(Enum(QuizScope), default=QuizScope.quick, nullable=False)
    generator = Column(Enum(Generator), default=Generator.llm, nullable=False)
    created_by = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan", order_by="Question.id")
    attempts = relationship("QuizAttempt", back_populates="quiz", cascade="all, delete-orphan")

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(Enum(QuestionKind), nullable=False)
    prompt = Column(Text, nullable=False)
    question_metadata = Column(JSON, nullable=True)  # For coding questions: tests, expected output, etc.
    order_index = Column(Integer, nullable=False, default=0)
    
    # Relationships
    quiz = relationship("Quiz", back_populates="questions")
    choices = relationship("Choice", back_populates="question", cascade="all, delete-orphan", order_by="Choice.id")

class Choice(Base):
    __tablename__ = "choices"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    label = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False, nullable=False)
    order_index = Column(Integer, nullable=False, default=0)
    
    # Relationships
    question = relationship("Question", back_populates="choices")

class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    attempt_index = Column(Integer, nullable=False, default=1)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    submitted_at = Column(DateTime, nullable=True)
    score = Column(Float, nullable=True)  # Percentage score (0.0 - 100.0)
    passed = Column(Boolean, nullable=True)  # True if passed, False if failed, None if not graded
    answers = Column(JSON, nullable=True)  # Store user answers for review
    
    # Relationships
    quiz = relationship("Quiz", back_populates="attempts")
