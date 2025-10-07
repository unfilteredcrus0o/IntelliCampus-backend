"""
Quiz Service
============

Business logic for quiz management following the quick quiz pattern:
1. If quiz exists → fetch latest quiz
2. If not → call LLM, generate quiz, insert into DB
3. Create new quiz_attempts row
4. Return quiz with quiz_id, attempt_id, questions
"""

from sqlalchemy.orm import Session
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone
import logging

from app.models.quiz import (
    Quiz, Question, Choice, QuizAttempt, UserAnswer,
    QuizScope, QuizType, QuizGenerator, QuestionKind
)
from app.models.roadmap import Milestone, Topic
from app.models.user import User
from app.services.llm_client import call_llm, LLMClientError

logger = logging.getLogger(__name__)


def start_milestone_quiz(
    db: Session,
    milestone_id: str,
    user_id: str,
    quiz_type: QuizType = QuizType.mixed,
    generator: QuizGenerator = QuizGenerator.llm
) -> Optional[Dict[str, Any]]:
    """
    Start a full scope quiz for a milestone.
    Follows quick quiz pattern but with scope=full, linked to milestone.
    """
    try:
        milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()
        if not milestone:
            logger.error(f"Milestone {milestone_id} not found")
            return None

        existing_quiz = db.query(Quiz).filter(
            Quiz.milestone_id == milestone_id,
            Quiz.scope == QuizScope.full,
            Quiz.quiz_type == quiz_type
        ).first()

        if existing_quiz:
            quiz = existing_quiz
            logger.info(f"Using existing quiz {quiz.id} for milestone {milestone_id}")
        else:
            quiz = Quiz(
                milestone_id=milestone_id,
                scope=QuizScope.full,
                quiz_type=quiz_type,
                generator=generator,
                created_by=user_id
            )
            db.add(quiz)
            db.flush()

            if generator == QuizGenerator.llm:
                success = _generate_milestone_questions_llm(db, quiz, milestone)
                if not success:
                    db.rollback()
                    logger.error(f"Failed to generate questions for milestone quiz {quiz.id}")
                    return None

            logger.info(f"Created new milestone quiz {quiz.id} for milestone {milestone_id}")

        last_attempt = db.query(QuizAttempt).filter(
            QuizAttempt.quiz_id == quiz.id,
            QuizAttempt.user_id == user_id
        ).order_by(QuizAttempt.attempt_index.desc()).first()

        next_attempt_index = (last_attempt.attempt_index + 1) if last_attempt else 1

        attempt = QuizAttempt(
            quiz_id=quiz.id,
            user_id=user_id,
            attempt_index=next_attempt_index
        )
        db.add(attempt)
        db.commit()

        questions = db.query(Question).filter(
            Question.quiz_id == quiz.id
        ).order_by(Question.order_index).all()

        logger.info(f"Started milestone quiz attempt {attempt.id} for user {user_id}")

        return {
            "quiz_id": quiz.id,
            "attempt_id": attempt.id,
            "questions": questions
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error starting milestone quiz: {str(e)}")
        return None


def start_topic_quiz(
    db: Session,
    topic_id: str,
    user_id: str,
    quiz_type: QuizType = QuizType.mixed,
    generator: QuizGenerator = QuizGenerator.llm
) -> Optional[Dict[str, Any]]:
    """
    Start a quick scope quiz for a topic.
    Original quick quiz logic pattern.
    """
    try:
        topic = db.query(Topic).filter(Topic.id == topic_id).first()
        if not topic:
            logger.error(f"Topic {topic_id} not found")
            return None

        existing_quiz = db.query(Quiz).filter(
            Quiz.topic_id == topic_id,
            Quiz.scope == QuizScope.quick,
            Quiz.quiz_type == quiz_type
        ).first()

        if existing_quiz:
            quiz = existing_quiz
            logger.info(f"Using existing quiz {quiz.id} for topic {topic_id}")
        else:
            quiz = Quiz(
                topic_id=topic_id,
                scope=QuizScope.quick,
                quiz_type=quiz_type,
                generator=generator,
                created_by=user_id
            )
            db.add(quiz)
            db.flush() 

            if generator == QuizGenerator.llm:
                success = _generate_topic_questions_llm(db, quiz, topic)
                if not success:
                    db.rollback()
                    logger.error(f"Failed to generate questions for topic quiz {quiz.id}")
                    return None

            logger.info(f"Created new topic quiz {quiz.id} for topic {topic_id}")

        last_attempt = db.query(QuizAttempt).filter(
            QuizAttempt.quiz_id == quiz.id,
            QuizAttempt.user_id == user_id
        ).order_by(QuizAttempt.attempt_index.desc()).first()

        next_attempt_index = (last_attempt.attempt_index + 1) if last_attempt else 1

        attempt = QuizAttempt(
            quiz_id=quiz.id,
            user_id=user_id,
            attempt_index=next_attempt_index
        )
        db.add(attempt)
        db.commit()

        questions = db.query(Question).filter(
            Question.quiz_id == quiz.id
        ).order_by(Question.order_index).all()

        logger.info(f"Started topic quiz attempt {attempt.id} for user {user_id}")

        return {
            "quiz_id": quiz.id,
            "attempt_id": attempt.id,
            "questions": questions
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error starting topic quiz: {str(e)}")
        return None


def _generate_milestone_questions_llm(db: Session, quiz: Quiz, milestone: Milestone) -> bool:
    """Generate questions for a milestone quiz using LLM."""
    try:
        topics = db.query(Topic).filter(Topic.milestone_id == milestone.id).all()
        
        if not topics:
            logger.warning(f"No topics found for milestone {milestone.id}")
            return False

        topics_content = []
        for topic in topics:
            topics_content.append(f"- {topic.name}: {topic.explanation_md or 'No explanation available'}")

        content = f"""
Milestone: {milestone.name}
Description: {milestone.description or 'No description available'}

Topics covered:
{chr(10).join(topics_content)}
        """

        question_count = _get_milestone_question_count(quiz.quiz_type)
        
        logger.error(f" LLM GENERATION DEBUG - Quiz type: {quiz.quiz_type}")
        logger.error(f" LLM GENERATION DEBUG - Question count: {question_count}")
        
        if quiz.quiz_type == QuizType.coding_only:
            logger.error(f" LLM GENERATION DEBUG - Using CODING_ONLY prompt!")
            question_type_instructions = "- Generate ONLY coding questions that require writing or analyzing Python code"
            question_format_example = '''{{
      "kind": "coding",
      "prompt": "Write a Python function called 'calculate_average' that takes a list of numbers and returns their average. Handle empty lists by returning 0.",
      "answer_key": "def calculate_average(numbers):\\n    if not numbers:\\n        return 0\\n    return sum(numbers) / len(numbers)"
    }},
    {{
      "kind": "coding",
      "prompt": "What is the output of this Python code?\\n\\nfor i in range(3):\\n    print(i * 2)",
      "answer_key": "0\\n2\\n4"
    }}'''
        elif quiz.quiz_type == QuizType.mcq_only:
            logger.error(f" LLM GENERATION DEBUG - Using MCQ_ONLY prompt!")
            question_type_instructions = "- Generate ONLY multiple choice questions with 4 options each"
            question_format_example = '''{{
      "kind": "mcq",
      "prompt": "In Python, which of the following is the correct way to define a string variable?",
      "choices": [
        "name = 'John'",
        "string name = 'John'",
        "var name = 'John'",
        "define name = 'John'"
      ],
      "correct_choice": 0
    }},
    {{
      "kind": "mcq", 
      "prompt": "What will happen if you run this Python code: print('Hello' + 5)?",
      "choices": [
        "It will print Hello5",
        "It will print Hello 5", 
        "It will raise a TypeError",
        "It will print 5Hello"
      ],
      "correct_choice": 2
    }}'''
        else:
            logger.error(f" LLM GENERATION DEBUG - Using MIXED prompt!")
            question_type_instructions = "- Generate a mix of multiple choice and coding questions"
            question_format_example = '''{{
      "kind": "mcq",
      "prompt": "In Python, which of the following is the correct way to define a string variable?",
      "choices": [
        "name = 'John'",
        "string name = 'John'",
        "var name = 'John'",
        "define name = 'John'"
      ],
      "correct_choice": 0
    }},
    {{
      "kind": "coding",
      "prompt": "Write a Python function that takes two numbers and returns their sum.",
      "answer_key": "def add_numbers(a, b):\\n    return a + b"
    }}'''

        prompt = f"""You are an expert Python programming instructor creating a practical quiz.

MILESTONE: {milestone.name}
DESCRIPTION: {milestone.description}

TOPICS TO COVER:
{chr(10).join(topics_content)}

Create {question_count} specific Python programming questions that test real knowledge:

QUESTION REQUIREMENTS:
- Focus on practical Python programming concepts from the topics above
- Test actual coding knowledge, syntax, and programming logic
- Include questions about Python installation, syntax, data types, variables, control structures, and functions
{question_type_instructions}
- Make questions realistic and test common misconceptions
- Avoid generic questions - be specific to Python programming

REQUIRED FORMAT (JSON only, no markdown):
{{
  "questions": [
    {question_format_example}
  ]
}}"""

        try:
            logger.error(f"🎯 LLM PROMPT DEBUG - Sending prompt (first 500 chars): {prompt[:500]}...")
            response = call_llm(prompt, temperature=0.3)
            logger.info(f"LLM response for milestone {milestone.id}: {response[:200]}...")
            
            import json
            cleaned_response = response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]  
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]  
            cleaned_response = cleaned_response.strip()
            
            import re
            cleaned_response = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned_response)
            
            quiz_data = json.loads(cleaned_response)
            
            for i, q_data in enumerate(quiz_data.get("questions", [])):
                question = Question(
                    quiz_id=quiz.id,
                    kind=QuestionKind(q_data["kind"]),
                    prompt=q_data["prompt"],
                    answer_key={"correct_choice": q_data.get("correct_choice")} if q_data["kind"] == "mcq" else {"answer": q_data.get("answer_key")},
                    order_index=i + 1
                )
                db.add(question)
                db.flush()

                if question.kind == QuestionKind.mcq and "choices" in q_data:
                    for j, choice_text in enumerate(q_data["choices"]):
                        choice = Choice(
                            question_id=question.id,
                            label=choice_text,
                            order_index=j + 1
                        )
                        db.add(choice)

            return True

        except (json.JSONDecodeError, LLMClientError) as e:
            logger.error(f"LLM call failed for milestone {milestone.id}: {str(e)}")
            logger.error(f"LLM response was: {response[:500] if 'response' in locals() else 'No response received'}")
            return _create_fallback_questions(db, quiz, "milestone", milestone.name)

    except Exception as e:
        logger.error(f"Error generating milestone questions: {str(e)}")
        return False


def _generate_topic_questions_llm(db: Session, quiz: Quiz, topic: Topic) -> bool:
    """Generate questions for a topic quiz using LLM."""
    try:
        content = f"""
Topic: {topic.name}
Content: {topic.explanation_md or 'No explanation available'}
        """

        prompt = f"""You are an expert educator creating a focused quiz for a specific programming topic.

TOPIC CONTEXT:
{content}

INSTRUCTIONS:
- Create {_get_topic_question_count(quiz.quiz_type)} focused questions that test understanding of this specific topic
- Questions should be practical and test both conceptual knowledge and application
- For MCQ questions: create realistic, challenging choices with one clearly correct answer
- For short_answer questions: ask for specific explanations or implementations
- Ensure questions directly relate to the topic content provided

REQUIRED JSON FORMAT (respond with ONLY this JSON, no other text):
{{
  "questions": [
    {{
      "kind": "mcq",
      "prompt": "Question about the specific topic concept",
      "choices": [
        "Correct answer that directly relates to the topic",
        "Plausible but incorrect option",
        "Another plausible but incorrect option", 
        "Clear distractor option"
      ],
      "correct_choice": 0
    }},
    {{
      "kind": "short_answer",
      "prompt": "Explain a key concept from this topic with an example",
      "choices": [],
      "answer_key": "Expected answer showing understanding of the topic"
    }}
  ]
}}

Generate questions now based on the topic content above:"""

        try:
            response = call_llm(prompt, temperature=0.3)
            logger.info(f"LLM response for topic {topic.id}: {response[:200]}...")
            
            import json
            cleaned_response = response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3] 
            cleaned_response = cleaned_response.strip()
            
            import re
            cleaned_response = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned_response)
            
            quiz_data = json.loads(cleaned_response)
            
            for i, q_data in enumerate(quiz_data.get("questions", [])):
                question = Question(
                    quiz_id=quiz.id,
                    kind=QuestionKind(q_data["kind"]),
                    prompt=q_data["prompt"],
                    answer_key={"correct_choice": q_data.get("correct_choice")} if q_data["kind"] == "mcq" else {"answer": q_data.get("answer_key")},
                    order_index=i + 1
                )
                db.add(question)
                db.flush()

                if question.kind == QuestionKind.mcq and "choices" in q_data:
                    for j, choice_text in enumerate(q_data["choices"]):
                        choice = Choice(
                            question_id=question.id,
                            label=choice_text,
                            order_index=j + 1
                        )
                        db.add(choice)

            return True

        except (json.JSONDecodeError, LLMClientError) as e:
            logger.error(f"LLM call failed for topic {topic.id}: {str(e)}")
            logger.error(f"LLM response was: {response[:500] if 'response' in locals() else 'No response received'}")
            return _create_fallback_questions(db, quiz, "topic", topic.name)

    except Exception as e:
        logger.error(f"Error generating topic questions: {str(e)}")
        return False


def _create_fallback_questions(db: Session, quiz: Quiz, content_type: str, content_name: str) -> bool:
    """Create fallback questions when LLM fails."""
    try:
        if content_type == "milestone":
            num_questions = _get_milestone_question_count(quiz.quiz_type)
        else:
            num_questions = _get_topic_question_count(quiz.quiz_type)

        if content_type == "milestone" and "Python" in content_name:
            fallback_questions = [
                {
                    "prompt": "In Python, which of the following is the correct way to define a variable?",
                    "choices": ["x = 10", "int x = 10", "var x = 10", "define x = 10"]
                },
                {
                    "prompt": "What is the correct file extension for Python files?",
                    "choices": [".py", ".python", ".txt", ".exe"]
                },
                {
                    "prompt": "Which data type is used to store True or False values in Python?",
                    "choices": ["bool", "boolean", "true_false", "binary"]
                },
                {
                    "prompt": "What will this Python code output: print(type(5))?",
                    "choices": ["<class 'int'>", "integer", "5", "number"]
                },
                {
                    "prompt": "In Python, what is used to indicate a block of code?",
                    "choices": ["Indentation", "Curly braces {}", "Parentheses ()", "Square brackets []"]
                },
                {
                    "prompt": "Which operator is used for string concatenation in Python?",
                    "choices": ["+", "&", "||", "concat()"]
                },
                {
                    "prompt": "What keyword is used to define a function in Python?",
                    "choices": ["def", "function", "define", "func"]
                },
                {
                    "prompt": "Which of these is a valid Python comment?",
                    "choices": ["# This is a comment", "// This is a comment", "/* This is a comment */", "-- This is a comment"]
                }
            ]
        else:
            fallback_questions = [
                {
                    "prompt": f"What is the main concept taught in {content_name}?",
                    "choices": ["Core programming fundamentals", "Advanced algorithms only", "Database design only", "Web development only"]
                },
                {
                    "prompt": f"Which skill would you develop after completing {content_name}?",
                    "choices": ["Problem-solving and logical thinking", "Memorization skills", "Drawing skills", "Language translation"]
                },
                {
                    "prompt": f"What is the best way to practice concepts from {content_name}?",
                    "choices": ["Writing and running code examples", "Reading without practicing", "Copying code without understanding", "Avoiding hands-on practice"]
                },
                {
                    "prompt": f"How should you approach learning {content_name}?",
                    "choices": ["Step by step with practice", "All at once quickly", "Only theoretical study", "Skipping difficult parts"]
                },
                {
                    "prompt": f"What indicates mastery of {content_name}?",
                    "choices": ["Ability to apply concepts to solve problems", "Memorizing all syntax", "Reading all documentation", "Completing without understanding"]
                }
            ]

        for i in range(min(num_questions, len(fallback_questions))):
            question_data = fallback_questions[i]
            question = Question(
                quiz_id=quiz.id,
                kind=QuestionKind.mcq,
                prompt=question_data["prompt"],
                answer_key={"correct_choice": 0},
                order_index=i + 1
            )
            db.add(question)
            db.flush()

            for j, choice_text in enumerate(question_data["choices"]):
                choice = Choice(
                    question_id=question.id,
                    label=choice_text,
                    order_index=j + 1
                )
                db.add(choice)

        return True

    except Exception as e:
        logger.error(f"Failed to create fallback questions: {str(e)}")
        return False


def _get_milestone_question_count(quiz_type: QuizType) -> int:
    """Get number of questions for milestone quiz."""
    if quiz_type == QuizType.mcq_only:
        return 6 
    elif quiz_type == QuizType.coding_only:
        return 2
    else:  
        return 6


def _get_topic_question_count(quiz_type: QuizType) -> int:
    """Get number of questions for topic quiz (focused, shorter)."""
    if quiz_type == QuizType.mcq_only:
        return 4
    elif quiz_type == QuizType.coding_only:
        return 2
    else:
        return 3