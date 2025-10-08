"""
Quiz Service
=====================================
Service layer for quiz management including LLM-powered quiz generation,
quiz logic, attempt tracking, and scoring.

Features:
- LLM-powered quiz generation based on topic content
- Intelligent quiz type classification (MCQ only, coding only, or mixed)
- Quiz caching and retrieval for topics
- Attempt management and progress tracking  
- Automatic scoring and feedback generation
- Support for both multiple choice and coding questions

Dependencies:
- LLM client for content generation
- Database models for persistence
- Topic context for relevant quiz generation
"""

import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.models.quiz import Quiz, Question, Choice, QuizAttempt, QuizType, QuizScope, QuestionKind, Generator
from app.models.roadmap import Topic
from app.models.user import User
from app.services.llm_client import call_llm, LLMClientError

logger = logging.getLogger(__name__)

def get_fallback_quiz_type(topic_name: str) -> str:
    """Determine quiz type based on topic name patterns when LLM is unavailable."""
    topic_lower = topic_name.lower()
    
    # Programming/coding related topics
    coding_keywords = ['programming', 'coding', 'python', 'javascript', 'java', 'code', 'function', 'algorithm', 'development']
    if any(keyword in topic_lower for keyword in coding_keywords):
        return "mixed"
    
    # Theory/concept heavy topics  
    theory_keywords = ['theory', 'concept', 'introduction', 'overview', 'principles', 'fundamentals']
    if any(keyword in topic_lower for keyword in theory_keywords):
        return "mcq_only"
    
    # Default to mixed for balanced assessment
    return "mixed"

def create_fallback_quiz(topic_name: str, quiz_type: str) -> Dict[str, Any]:
    """Create a simple fallback quiz when LLM generation fails."""
    logger.info(f"Creating fallback quiz for topic: {topic_name}")
    
    questions = []
    
    if quiz_type in ["mcq_only", "mixed"]:
        # Add MCQ questions
        questions.append({
            "kind": "mcq",
            "prompt": f"What is the main concept you should understand about {topic_name}?",
            "choices": [
                {"label": "It's a fundamental topic that requires practice", "is_correct": True},
                {"label": "It's only theoretical knowledge", "is_correct": False},
                {"label": "It's not important for learning", "is_correct": False},
                {"label": "It should be memorized only", "is_correct": False}
            ],
            "metadata": None,
            "order_index": 0
        })
        
        questions.append({
            "kind": "mcq", 
            "prompt": f"When learning {topic_name}, what is the best approach?",
            "choices": [
                {"label": "Combine theory with practical examples", "is_correct": True},
                {"label": "Only read about it", "is_correct": False},
                {"label": "Skip the basics", "is_correct": False},
                {"label": "Learn it all at once", "is_correct": False}
            ],
            "metadata": None,
            "order_index": 1
        })
    
    if quiz_type in ["coding_only", "mixed"]:
        # Add coding question
        questions.append({
            "kind": "coding",
            "prompt": f"Write a simple example or pseudocode that demonstrates your understanding of {topic_name}. Comment your code to explain the key concepts.",
            "choices": None,
            "metadata": {
                "tests": [
                    {"input": "example_input", "output": "expected_output"},
                ]
            },
            "order_index": len(questions)
        })
    
    # Add more questions to reach desired count
    while len(questions) < 3:
        questions.append({
            "kind": "mcq",
            "prompt": f"Which statement best describes {topic_name}?",
            "choices": [
                {"label": "It's an important learning topic", "is_correct": True},
                {"label": "It's not relevant", "is_correct": False},
                {"label": "It's too complex", "is_correct": False},
                {"label": "It's outdated", "is_correct": False}
            ],
            "metadata": None,
            "order_index": len(questions)
        })
    
    return {"questions": questions}

# Quiz generation prompts
QUIZ_CLASSIFICATION_PROMPT = """
Analyze this learning topic and determine the best quiz type for assessing understanding.

Topic: {topic_name}
Topic Content: {topic_content}

Consider these factors:
- Is this topic more theoretical/conceptual or practical/hands-on?
- Would multiple choice questions effectively test understanding?
- Would coding exercises be more appropriate for assessment?
- Could a combination of both provide comprehensive assessment?

Return ONLY a JSON object with this format:
{{
    "quiz_type": "mcq_only" | "coding_only" | "mixed",
    "reasoning": "Brief explanation of why this quiz type was chosen"
}}
"""

QUIZ_GENERATION_PROMPT = """
Generate a comprehensive quiz for this learning topic with {num_questions} questions.

Topic: {topic_name}
Topic Content: {topic_content}
Quiz Type: {quiz_type}
Target Audience: Beginner to Intermediate learners

Requirements:
- Create {num_questions} questions that test key concepts and practical understanding
- For MCQ questions: Include 4 answer choices with exactly 1 correct answer
- For coding questions: Include test cases and expected outputs in metadata
- Questions should progress from basic concepts to practical applications
- Ensure questions are clear, unambiguous, and educational

{type_specific_instructions}

Return ONLY a JSON object with this exact format:
{{
    "questions": [
        {{
            "kind": "mcq" | "coding",
            "prompt": "Question text",
            "choices": [
                {{"label": "Choice text", "is_correct": true|false}},
                ...
            ],
            "metadata": {{"tests": [{{"input": "test input", "output": "expected output"}}], ...}}
        }},
        ...
    ]
}}
"""

def get_type_specific_instructions(quiz_type: str) -> str:
    """Get specific instructions based on quiz type."""
    if quiz_type == "mcq_only":
        return """
- ALL questions must be multiple choice format
- Each question must have exactly 4 answer choices
- Only 1 choice should be correct per question
- Do not include 'choices' field for coding questions (there won't be any)
"""
    elif quiz_type == "coding_only":
        return """
- ALL questions must be coding/programming format
- Include practical coding challenges that test the topic concepts
- Each coding question must include test cases in metadata with input/output pairs
- Do not include 'metadata' field for MCQ questions (there won't be any)
"""
    else:  # mixed
        return """
- Include BOTH multiple choice AND coding questions
- Mix question types to provide comprehensive assessment
- MCQ questions must have exactly 4 choices with 1 correct answer
- Coding questions must include test cases in metadata
- Balance theoretical understanding (MCQ) with practical skills (coding)
"""

def classify_quiz_type(topic_name: str, topic_content: Optional[str] = None) -> str:
    """Use LLM to determine the best quiz type for a topic."""
    try:
        content = topic_content or f"Learning topic about {topic_name}"
        prompt = QUIZ_CLASSIFICATION_PROMPT.format(
            topic_name=topic_name,
            topic_content=content[:1000]  # Limit content length
        )
        
        response = call_llm(prompt, temperature=0.3)
        
        # Extract JSON from response
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()
        
        result = json.loads(response)
        
        quiz_type = result.get("quiz_type", "mixed")
        if quiz_type not in ["mcq_only", "coding_only", "mixed"]:
            logger.warning(f"Invalid quiz type '{quiz_type}' from LLM, defaulting to 'mixed'")
            quiz_type = "mixed"
            
        logger.info(f"Classified quiz type for '{topic_name}': {quiz_type}")
        return quiz_type
        
    except Exception as e:
        logger.error(f"Failed to classify quiz type for topic '{topic_name}': {e}")
        logger.info(f"Using fallback classification for topic: {topic_name}")
        return get_fallback_quiz_type(topic_name)

def generate_quiz_content(topic_name: str, quiz_type: str, topic_content: Optional[str] = None, num_questions: int = 5) -> Dict[str, Any]:
    """Generate quiz questions using LLM."""
    try:
        content = topic_content or f"Learning topic about {topic_name}"
        type_instructions = get_type_specific_instructions(quiz_type)
        
        prompt = QUIZ_GENERATION_PROMPT.format(
            topic_name=topic_name,
            topic_content=content[:1500],  # Limit content length
            quiz_type=quiz_type,
            num_questions=num_questions,
            type_specific_instructions=type_instructions
        )
        
        response = call_llm(prompt, temperature=0.3)
        
        # Extract JSON from response
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()
        
        result = json.loads(response)
        
        # Validate the response structure
        if "questions" not in result or not isinstance(result["questions"], list):
            raise ValueError("Invalid response structure: missing or invalid 'questions' field")
        
        # Validate each question
        validated_questions = []
        for i, question in enumerate(result["questions"]):
            try:
                validated_question = validate_question_data(question, quiz_type)
                validated_question["order_index"] = i
                validated_questions.append(validated_question)
            except Exception as e:
                logger.warning(f"Skipping invalid question {i}: {e}")
                
        if not validated_questions:
            raise ValueError("No valid questions generated")
            
        logger.info(f"Generated {len(validated_questions)} questions for topic '{topic_name}'")
        return {"questions": validated_questions}
        
    except Exception as e:
        logger.error(f"Failed to generate quiz content for topic '{topic_name}': {e}")
        logger.info(f"Using fallback quiz generation for topic: {topic_name}")
        return create_fallback_quiz(topic_name, quiz_type)

def validate_question_data(question: Dict[str, Any], expected_quiz_type: str) -> Dict[str, Any]:
    """Validate and clean question data from LLM."""
    if "kind" not in question or "prompt" not in question:
        raise ValueError("Missing required fields: kind, prompt")
    
    kind = question["kind"]
    if kind not in ["mcq", "coding"]:
        raise ValueError(f"Invalid question kind: {kind}")
    
    # Validate MCQ questions
    if kind == "mcq":
        if "choices" not in question or not isinstance(question["choices"], list):
            raise ValueError("MCQ questions must have choices")
        
        choices = question["choices"]
        if len(choices) < 2:
            raise ValueError("MCQ questions must have at least 2 choices")
        
        correct_count = sum(1 for choice in choices if choice.get("is_correct", False))
        if correct_count != 1:
            raise ValueError(f"MCQ questions must have exactly 1 correct answer, found {correct_count}")
    
    # Validate coding questions
    elif kind == "coding":
        if "metadata" not in question:
            question["metadata"] = {"tests": []}
        elif not isinstance(question.get("metadata"), dict):
            question["metadata"] = {"tests": []}
    
    return question

def get_or_create_quiz(db: Session, topic_id: str, user_id: str) -> Quiz:
    """Get existing quiz for topic or create new one using LLM."""
    # Check if quiz already exists for this topic
    existing_quiz = db.query(Quiz).filter(Quiz.topic_id == topic_id).first()
    
    if existing_quiz:
        logger.info(f"Found existing quiz {existing_quiz.id} for topic {topic_id}")
        return existing_quiz
    
    # Get topic information
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise ValueError(f"Topic {topic_id} not found")
    
    logger.info(f"Creating new quiz for topic: {topic.name}")
    
    # Classify quiz type using LLM
    quiz_type = classify_quiz_type(topic.name, topic.explanation_md)
    
    # Generate quiz content using LLM
    quiz_content = generate_quiz_content(
        topic_name=topic.name,
        quiz_type=quiz_type,
        topic_content=topic.explanation_md,
        num_questions=5
    )
    
    # Create quiz in database
    quiz = Quiz(
        topic_id=topic_id,
        milestone_id=topic.milestone_id,
        quiz_type=QuizType(quiz_type),
        scope=QuizScope.quick,
        generator=Generator.llm,
        created_by=user_id
    )
    db.add(quiz)
    db.flush()  # Get quiz ID
    
    # Create questions and choices
    for question_data in quiz_content["questions"]:
        question = Question(
            quiz_id=quiz.id,
            kind=QuestionKind(question_data["kind"]),
            prompt=question_data["prompt"],
            question_metadata=question_data.get("metadata"),
            order_index=question_data.get("order_index", 0)
        )
        db.add(question)
        db.flush()  # Get question ID
        
        # Add choices for MCQ questions
        if question_data["kind"] == "mcq" and "choices" in question_data:
            for i, choice_data in enumerate(question_data["choices"]):
                choice = Choice(
                    question_id=question.id,
                    label=choice_data["label"],
                    is_correct=choice_data.get("is_correct", False),
                    order_index=i
                )
                db.add(choice)
    
    db.commit()
    logger.info(f"Created quiz {quiz.id} with {len(quiz_content['questions'])} questions")
    return quiz

def start_quiz_attempt(db: Session, quiz_id: int, user_id: str) -> QuizAttempt:
    """Create a new quiz attempt for the user."""
    # Get the latest attempt index for this user and quiz
    latest_attempt = db.query(QuizAttempt).filter(
        QuizAttempt.quiz_id == quiz_id,
        QuizAttempt.user_id == user_id
    ).order_by(QuizAttempt.attempt_index.desc()).first()
    
    next_attempt_index = (latest_attempt.attempt_index + 1) if latest_attempt else 1
    
    attempt = QuizAttempt(
        quiz_id=quiz_id,
        user_id=user_id,
        attempt_index=next_attempt_index,
        started_at=datetime.now(timezone.utc)
    )
    
    db.add(attempt)
    db.commit()
    
    logger.info(f"Started quiz attempt {attempt.id} for user {user_id}, quiz {quiz_id}")
    return attempt

def get_quiz_with_questions(db: Session, quiz_id: int) -> Optional[Dict[str, Any]]:
    """Get quiz with all questions and choices."""
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        return None
    
    # Get topic name for response
    topic = db.query(Topic).filter(Topic.id == quiz.topic_id).first()
    topic_name = topic.name if topic else None
    
    questions_data = []
    for question in quiz.questions:
        question_dict = {
            "id": question.id,
            "kind": question.kind.value,
            "prompt": question.prompt,
            "metadata": question.question_metadata
        }
        
        # Add choices for MCQ questions
        if question.kind == QuestionKind.mcq:
            question_dict["choices"] = [
                {"id": choice.id, "label": choice.label}
                for choice in question.choices
            ]
        
        questions_data.append(question_dict)
    
    return {
        "quiz_id": quiz.id,
        "quiz_type": quiz.quiz_type.value,
        "topic_name": topic_name,
        "questions": questions_data
    }
