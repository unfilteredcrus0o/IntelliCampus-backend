"""
Quiz Data Models
================

Comprehensive SQLAlchemy ORM models for quiz and assessment system.

Models:
- Quiz: Represents either quick (topic-level) or full (milestone-level) assessments
- Question: Individual questions within a quiz
- Choice: Multiple choice options for MCQ questions
- QuizAttempt: User attempts at taking a quiz
- UserAnswer: Individual answers submitted by users

Features:
- Support for both quick and full scope quizzes
- Multiple question types (MCQ, coding, short answer)
- Flexible answer storage with JSONB
- Comprehensive scoring and feedback system
- Proper foreign key relationships with CASCADE deletes
"""

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, 
    ForeignKey, Enum, DECIMAL, JSON
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from app.db.database import Base


class QuizScope(str, enum.Enum):
    """Quiz scope enumeration."""
    quick = "quick"
    full = "full"


class QuizType(str, enum.Enum):
    """Quiz type enumeration."""
    mcq_only = "mcq_only"
    coding_only = "coding_only"   
    mixed = "mixed"               


class QuizGenerator(str, enum.Enum):
    """Quiz generation method enumeration."""
    llm = "llm"
    template = "template"


class QuestionKind(str, enum.Enum):
    """Question type enumeration."""
    mcq = "mcq"                   
    coding = "coding"             
    short_answer = "short_answer" 


class Quiz(Base):
    """
    Quiz model for both quick and full assessments.
    
    Either topic_id OR milestone_id should be set, not both.
    """
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    topic_id = Column(String, ForeignKey("topics.id", ondelete="CASCADE"), nullable=True, index=True)
    milestone_id = Column(String, ForeignKey("milestones.id", ondelete="CASCADE"), nullable=True, index=True)
    scope = Column(Enum(QuizScope), nullable=False)
    quiz_type = Column(Enum(QuizType), nullable=False)
    generator = Column(Enum(QuizGenerator), nullable=False)
    created_by = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    topic = relationship("Topic", back_populates="quizzes")
    milestone = relationship("Milestone", back_populates="quizzes") 
    creator = relationship("User", back_populates="created_quizzes")
    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan", order_by="Question.order_index")
    attempts = relationship("QuizAttempt", back_populates="quiz", cascade="all, delete-orphan")


class Question(Base):
    """Individual questions within a quiz."""
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(Enum(QuestionKind), nullable=False)
    prompt = Column(Text, nullable=False)
    answer_key = Column(JSON, nullable=True)
    order_index = Column(Integer, nullable=False)

    quiz = relationship("Quiz", back_populates="questions")
    choices = relationship("Choice", back_populates="question", cascade="all, delete-orphan", order_by="Choice.order_index")
    user_answers = relationship("UserAnswer", back_populates="question", cascade="all, delete-orphan")


class Choice(Base):
    """Multiple choice options for MCQ questions."""
    __tablename__ = "choices"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    label = Column(Text, nullable=False)
    order_index = Column(Integer, nullable=False)

    question = relationship("Question", back_populates="choices")


class QuizAttempt(Base):
    """User attempts at taking a quiz."""
    __tablename__ = "quiz_attempts"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    attempt_index = Column(Integer, nullable=False)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    submitted_at = Column(DateTime, nullable=True)
    score = Column(DECIMAL(5, 2), nullable=True)
    passed = Column(Boolean, nullable=True)

    quiz = relationship("Quiz", back_populates="attempts")
    user = relationship("User", back_populates="quiz_attempts")
    user_answers = relationship("UserAnswer", back_populates="attempt", cascade="all, delete-orphan")


class UserAnswer(Base):
    """Individual answers submitted by users."""
    __tablename__ = "user_answers"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    attempt_id = Column(Integer, ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    answer = Column(JSON, nullable=False)
    is_correct = Column(Boolean, nullable=True)
    score = Column(DECIMAL(5, 2), nullable=True)
    feedback = Column(Text, nullable=True)  
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    attempt = relationship("QuizAttempt", back_populates="user_answers")
    question = relationship("Question", back_populates="user_answers")
