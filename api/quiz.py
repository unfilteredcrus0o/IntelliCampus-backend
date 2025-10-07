"""
Quiz API Routes
================

FastAPI endpoints for quiz management following the quick quiz pattern:
1. If quiz exists → fetch latest quiz
2. If not → call LLM, generate quiz, insert into DB  
3. Create new quiz_attempts row
4. Return quiz with quiz_id, attempt_id, questions

Endpoints:
- POST /topics/{topic_id}/quiz/start - Start quick quiz (scope=quick)
- POST /milestones/{milestone_id}/quiz/start - Start milestone quiz (scope=full)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body, Request
from sqlalchemy.orm import Session
from typing import List
import logging

from app.db.database import get_db
from app.models.quiz import Quiz, QuizAttempt, Question, Choice, QuizScope
from app.models.roadmap import Milestone, Topic
from app.models.user import User
from app.schemas.quiz import (
    QuizStartRequest, QuizStartResponse, QuestionResponse, ChoiceResponse
)
from app.services.quiz_service import start_milestone_quiz, start_topic_quiz
from app.core.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Quiz"])


def _build_question_response(question: Question) -> QuestionResponse:
    """Helper to build QuestionResponse from Question model."""
    choices = [
        ChoiceResponse(
            id=choice.id,
            label=choice.label,
            order_index=choice.order_index
        )
        for choice in question.choices
    ]
    
    return QuestionResponse(
        id=question.id,
        kind=question.kind,
        prompt=question.prompt,
        order_index=question.order_index,
        choices=choices
    )


def _build_quiz_start_response(quiz_data: dict) -> QuizStartResponse:
    """Helper to build QuizStartResponse from quiz service data."""
    quiz_id = quiz_data["quiz_id"]
    attempt_id = quiz_data["attempt_id"]
    questions = quiz_data["questions"]
    
    question_responses = [
        _build_question_response(question) 
        for question in questions
    ]
    
    return QuizStartResponse(
        quiz_id=quiz_id,
        attempt_id=attempt_id,
        questions=question_responses
    )


@router.post("/milestones/{milestone_id}/quiz/startFullQuiz", response_model=QuizStartResponse)
def start_milestone_quiz_endpoint(
    milestone_id: str,
    request: QuizStartRequest = QuizStartRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Start a full scope quiz for a milestone.
    
    Logic: scope=full, linked to milestone
    1. If quiz exists → fetch latest quiz
    2. If not → call LLM, generate quiz, insert into DB
    3. Create new quiz_attempts row
    4. Return quiz with quiz_id, attempt_id, questions
    
    Args:
        milestone_id: UUID of the milestone to start quiz for
        request: Quiz configuration options
        db: Database session
        current_user: Authenticated user
        
    Returns:
        QuizStartResponse with quiz_id, attempt_id, questions
        
    Raises:
        404: Milestone not found
        500: Error starting quiz
    """
    logger.info(f"User {current_user.id} starting milestone quiz for milestone {milestone_id}")
    
    logger.error(f" QUIZ TYPE DEBUG - Received request: {request}")
    logger.error(f" QUIZ TYPE DEBUG - Quiz type: {request.quiz_type}")
    logger.error(f" QUIZ TYPE DEBUG - Quiz type value: {request.quiz_type.value if hasattr(request.quiz_type, 'value') else str(request.quiz_type)}")
    
    milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()
    if not milestone:
        logger.warning(f"Milestone {milestone_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Milestone not found"
        )
    
    quiz_data = start_milestone_quiz(
        db=db,
        milestone_id=milestone_id,
        user_id=current_user.id,
        quiz_type=request.quiz_type,
        generator=request.generator
    )
    
    if not quiz_data:
        logger.error(f"Failed to start milestone quiz for milestone {milestone_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start quiz. Please try again."
        )
    
    logger.info(f"Successfully started milestone quiz {quiz_data['quiz_id']} attempt {quiz_data['attempt_id']} for user {current_user.id}")
    
    return _build_quiz_start_response(quiz_data)


@router.post("/milestones/{milestone_id}/quiz/submitFullQuiz")
async def submit_milestone_quiz_endpoint(
    milestone_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit answers for the latest quiz attempt on a milestone.
    This is a convenience endpoint that finds the latest active attempt.
    
    Args:
        milestone_id: UUID of the milestone
        answers: Dictionary mapping question_id to chosen answer index (request body)
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Dictionary with score, percentage, results per question
    """
    try:
        latest_attempt = db.query(QuizAttempt).join(Quiz).filter(
            Quiz.milestone_id == milestone_id,
            Quiz.scope == QuizScope.full,
            QuizAttempt.user_id == current_user.id,
            QuizAttempt.submitted_at.is_(None)
        ).order_by(QuizAttempt.id.desc()).first()
        
        if not latest_attempt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active quiz attempt found for this milestone. Start a quiz first."
            )
        
        logger.info(f"Found active attempt {latest_attempt.id} for milestone {milestone_id}")
        logger.error(f" ATTEMPT DEBUG - Attempt ID: {latest_attempt.id}")
        logger.error(f" ATTEMPT DEBUG - User ID: {latest_attempt.user_id}")
        logger.error(f" ATTEMPT DEBUG - Quiz ID: {latest_attempt.quiz_id}")
        logger.error(f" ATTEMPT DEBUG - Submitted at: {latest_attempt.submitted_at}")
        logger.error(f" ATTEMPT DEBUG - Score: {latest_attempt.score}")
        
        if latest_attempt.submitted_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Quiz attempt {latest_attempt.id} already submitted at {latest_attempt.submitted_at}. Start a new quiz."
            )
        
        answers = {}
        try:
            import json
            body = await request.body()
            
            if body:
                body_str = body.decode('utf-8')
                parsed_data = json.loads(body_str)
                
                answers = {}
                
                if 'answers' in parsed_data and isinstance(parsed_data['answers'], list):
                    
                    for answer_obj in parsed_data['answers']:
                        question_id = answer_obj.get('question_id')
                        choice_index = answer_obj.get('choice_index')
                        
                        if question_id is not None and choice_index is not None:
                            str_key = str(question_id)
                            answers[str_key] = choice_index
                            answers[question_id] = choice_index
                        
                            
                else:
                    for key, value in parsed_data.items():
                        if str(key).isdigit():
                            str_key = str(key)
                            answers[str_key] = value
                            answers[int(key)] = value
                
                
        except Exception as e:
            import traceback
            try:
                content_type = request.headers.get('content-type', '')
                
                form = await request.form()
                answers = dict(form)
            except:
                answers = {}
        
        from datetime import datetime
        
        questions = db.query(Question).filter(
            Question.quiz_id == latest_attempt.quiz_id
        ).order_by(Question.order_index).all()
        
        total_questions = len(questions)
        correct_answers = 0
        detailed_results = []
        
        for question in questions:
            str_key = str(question.id)
            int_key = question.id
            
            user_answer = answers.get(str_key)
            if user_answer is None:
                user_answer = answers.get(int_key)
            
            if user_answer is not None:
                correct_choice = question.answer_key.get('correct_choice')
                is_correct = (int(user_answer) == correct_choice)
                
                if is_correct:
                    correct_answers += 1
                
                detailed_results.append({
                    "question_id": question.id,
                    "question": question.prompt,
                    "user_answer": int(user_answer),
                    "correct_answer": correct_choice,
                    "is_correct": is_correct,
                    "choices": [choice.label for choice in question.choices] if question.choices else []
                })
            else:
                detailed_results.append({
                    "question_id": question.id,
                    "question": question.prompt,
                    "user_answer": None,
                    "correct_answer": question.answer_key.get('correct_choice'),
                    "is_correct": False,
                    "choices": [choice.label for choice in question.choices] if question.choices else []
                })
        
        score = (correct_answers / total_questions) if total_questions > 0 else 0
        passed = score >= 0.7 
        
        latest_attempt.submitted_at = datetime.utcnow()
        latest_attempt.score = score
        db.commit()
        
        return {
            "attempt_id": latest_attempt.id,
            "score": score,
            "correct_answers": correct_answers,
            "total_questions": total_questions,
            "passed": passed,
            "submitted_at": latest_attempt.submitted_at.isoformat(),
            "detailed_results": detailed_results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting milestone quiz for {milestone_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit quiz: {str(e)}"
        )

@router.post("/quiz/attempts/{attempt_id}/submit")
def submit_quiz_attempt_endpoint(
    attempt_id: int,
    answers: dict = Body(...), 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit answers for a quiz attempt and get scored results.
    
    Args:
        attempt_id: ID of the quiz attempt
        answers: Dictionary mapping question_id to chosen answer index
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Dictionary with score, percentage, results per question
    """
    try:
        from app.models.quiz import QuizAttempt
        attempt = db.query(QuizAttempt).filter(
            QuizAttempt.id == attempt_id,
            QuizAttempt.user_id == current_user.id
        ).first()
        
        if not attempt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz attempt not found"
            )
        
        if attempt.submitted_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quiz already submitted"
            )
        
        questions = db.query(Question).filter(
            Question.quiz_id == attempt.quiz_id
        ).order_by(Question.order_index).all()
        
        total_questions = len(questions)
        correct_answers = 0
        detailed_results = []
        
        for question in questions:
            question_id = str(question.id)
            user_answer = answers.get(question_id)
            
            logger.error(f"🔍 Q{question.id} - Looking for key '{question_id}', found: {user_answer}")
            
            if user_answer is not None:
                correct_choice = question.answer_key.get('correct_choice')
                is_correct = (int(user_answer) == correct_choice)
                
                if is_correct:
                    correct_answers += 1
                
                detailed_results.append({
                    "question_id": question.id,
                    "question": question.prompt,
                    "user_answer": int(user_answer),
                    "correct_answer": correct_choice,
                    "is_correct": is_correct,
                    "choices": [choice.label for choice in question.choices] if question.choices else []
                })
            else:
                detailed_results.append({
                    "question_id": question.id,
                    "question": question.prompt,
                    "user_answer": None,
                    "correct_answer": question.answer_key.get('correct_choice'),
                    "is_correct": False,
                    "choices": [choice.label for choice in question.choices] if question.choices else []
                })
        
        percentage = (correct_answers / total_questions * 100) if total_questions > 0 else 0
        passed = percentage >= 70
        
        from datetime import datetime, timezone
        attempt.submitted_at = datetime.now(timezone.utc)
        attempt.score = round(percentage, 2)
        attempt.passed = passed
        
        db.commit()
        
        logger.info(f"Quiz attempt {attempt_id} submitted. Score: {percentage:.1f}% ({correct_answers}/{total_questions})")
        
        return {
            "attempt_id": attempt.id,
            "score": round(percentage, 2),
            "correct_answers": correct_answers,
            "total_questions": total_questions,
            "passed": passed,
            "submitted_at": attempt.submitted_at.isoformat(),
            "detailed_results": detailed_results
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error submitting quiz attempt {attempt_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit quiz: {str(e)}"
        )