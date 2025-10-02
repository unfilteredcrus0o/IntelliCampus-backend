"""
Quiz API Schemas  
=====================================
Pydantic models for quiz-related API requests and responses.

Schemas:
- QuizStartResponse: Response when starting a quiz with questions and attempt info
- QuestionResponse: Individual question data with choices (for MCQ) or metadata (for coding)
- ChoiceResponse: Answer choice for MCQ questions
- QuizSubmitRequest: User's answers when submitting a completed quiz
- QuizResultResponse: Results and scoring after quiz submission

Features:
- Supports both MCQ and coding question types
- Flexible metadata field for coding question test cases
- Progress tracking with attempt management
- Comprehensive scoring and feedback system
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

class ChoiceResponse(BaseModel):
    id: int
    label: str
    
    class Config:
        from_attributes = True

class QuestionResponse(BaseModel):
    id: int
    kind: str = Field(..., description="Question type: 'mcq' or 'coding'")
    prompt: str
    choices: Optional[List[ChoiceResponse]] = Field(None, description="Answer choices for MCQ questions")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional data for coding questions (tests, etc.)")
    
    class Config:
        from_attributes = True

class QuizStartResponse(BaseModel):
    quiz_id: int
    attempt_id: int
    questions: List[QuestionResponse]
    quiz_type: str = Field(..., description="Quiz type: 'mcq_only', 'coding_only', or 'mixed'")
    topic_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class AnswerSubmission(BaseModel):
    question_id: int
    answer: Union[str, int, List[int]] = Field(..., description="Answer: choice_id for MCQ, code string for coding")

class QuizSubmitRequest(BaseModel):
    attempt_id: int
    answers: List[AnswerSubmission]

class QuestionResultResponse(BaseModel):
    question_id: int
    user_answer: Union[str, int, List[int]]
    correct_answer: Optional[Union[str, int, List[int]]] = None
    is_correct: Optional[bool] = None
    feedback: Optional[str] = None
    
class QuizResultResponse(BaseModel):
    attempt_id: int
    quiz_id: int
    score: float = Field(..., description="Score as percentage (0.0 - 100.0)")
    passed: bool
    total_questions: int
    correct_answers: int
    submitted_at: datetime
    question_results: List[QuestionResultResponse]
    
    class Config:
        from_attributes = True

class QuizAttemptResponse(BaseModel):
    id: int
    quiz_id: int
    attempt_index: int
    started_at: datetime
    submitted_at: Optional[datetime] = None
    score: Optional[float] = None
    passed: Optional[bool] = None
    
    class Config:
        from_attributes = True
