"""
Quiz Schemas
============

Pydantic models for quiz-related API requests and responses.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.models.quiz import QuizScope, QuizType, QuizGenerator, QuestionKind


class QuizStartRequest(BaseModel):
    """Request model for starting a quiz."""
    quiz_type: Optional[QuizType] = Field(default=QuizType.mixed, description="Type of quiz to generate")
    generator: Optional[QuizGenerator] = Field(default=QuizGenerator.llm, description="Method to generate quiz")


class ChoiceResponse(BaseModel):
    """Response model for multiple choice options."""
    id: int
    label: str
    order_index: int
    
    class Config:
        from_attributes = True


class QuestionResponse(BaseModel):
    """Response model for quiz questions."""
    id: int
    kind: QuestionKind
    prompt: str
    order_index: int
    choices: List[ChoiceResponse] = []
    
    class Config:
        from_attributes = True


class QuizStartResponse(BaseModel):
    """Response model after starting a quiz."""
    quiz_id: int
    attempt_id: int
    questions: List[QuestionResponse]
    
    class Config:
        from_attributes = True