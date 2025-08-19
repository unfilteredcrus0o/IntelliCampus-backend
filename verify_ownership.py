#!/usr/bin/env python3
"""
Roadmap Ownership Verification Utility
======================================

This script shows you how to manually verify that roadmaps belong to specific users.
Useful for debugging, testing, and understanding the ownership model.

Usage:
    python verify_ownership.py
"""

from sqlalchemy.orm import Session, joinedload
from app.db.database import SessionLocal
from app.models.user import User
from app.models.roadmap import Roadmap, Milestone, Topic, UserProgress
from app.core.security import verify_token
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_roadmap_ownership(roadmap_id: str, user_email: str = None, user_id: str = None):
    """
    Check if a roadmap belongs to a specific user
    
    Args:
        roadmap_id: UUID of the roadmap to check
        user_email: Email of the user (optional)
        user_id: UUID of the user (optional, takes precedence over email)
    
    Returns:
        dict: Ownership verification results
    """
    with SessionLocal() as db:
        # Get the roadmap
        roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
        
        if not roadmap:
            return {
                "roadmap_exists": False,
                "error": f"Roadmap {roadmap_id} not found"
            }
        
        # Get the user
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
        elif user_email:
            user = db.query(User).filter(User.email == user_email).first()
        else:
            return {
                "roadmap_exists": True,
                "error": "Must provide either user_id or user_email"
            }
        
        if not user:
            return {
                "roadmap_exists": True,
                "user_exists": False,
                "error": f"User not found"
            }
        
        # Check ownership
        owns_roadmap = roadmap.user_id == user.id
        
        return {
            "roadmap_exists": True,
            "user_exists": True,
            "roadmap_id": roadmap.id,
            "roadmap_title": roadmap.title,
            "roadmap_user_id": roadmap.user_id,
            "checking_user_id": user.id,
            "checking_user_email": user.email,
            "owns_roadmap": owns_roadmap,
            "access_granted": owns_roadmap
        }

def check_topic_ownership(topic_id: str, user_email: str = None, user_id: str = None):
    """
    Check if a topic belongs to a roadmap owned by a specific user
    
    Args:
        topic_id: UUID of the topic to check
        user_email: Email of the user (optional)
        user_id: UUID of the user (optional, takes precedence over email)
    
    Returns:
        dict: Topic ownership verification results
    """
    with SessionLocal() as db:
        # Get the user
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
        elif user_email:
            user = db.query(User).filter(User.email == user_email).first()
        else:
            return {"error": "Must provide either user_id or user_email"}
        
        if not user:
            return {"error": "User not found"}
        
        # Get topic with roadmap information (same query as in the API)
        topic = (
            db.query(Topic)
            .join(Milestone)
            .join(Roadmap)
            .filter(Topic.id == topic_id, Roadmap.user_id == user.id)
            .first()
        )
        
        # Also get topic without user filter to see if it exists
        topic_exists = db.query(Topic).filter(Topic.id == topic_id).first()
        
        if not topic_exists:
            return {
                "topic_exists": False,
                "error": f"Topic {topic_id} not found"
            }
        
        # Get the actual roadmap info
        milestone = db.query(Milestone).filter(Milestone.id == topic_exists.milestone_id).first()
        roadmap = db.query(Roadmap).filter(Roadmap.id == milestone.roadmap_id).first() if milestone else None
        
        return {
            "topic_exists": True,
            "topic_id": topic_exists.id,
            "topic_name": topic_exists.name,
            "roadmap_id": roadmap.id if roadmap else None,
            "roadmap_title": roadmap.title if roadmap else None,
            "roadmap_owner_id": roadmap.user_id if roadmap else None,
            "checking_user_id": user.id,
            "checking_user_email": user.email,
            "owns_topic": topic is not None,
            "access_granted": topic is not None
        }

def list_user_roadmaps(user_email: str = None, user_id: str = None):
    """
    List all roadmaps for a specific user
    
    Args:
        user_email: Email of the user (optional)
        user_id: UUID of the user (optional, takes precedence over email)
    
    Returns:
        dict: User's roadmaps
    """
    with SessionLocal() as db:
        # Get the user
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
        elif user_email:
            user = db.query(User).filter(User.email == user_email).first()
        else:
            return {"error": "Must provide either user_id or user_email"}
        
        if not user:
            return {"error": "User not found"}
        
        # Get user's roadmaps (same query as in the API)
        roadmaps = (
            db.query(Roadmap)
            .filter(Roadmap.user_id == user.id)
            .all()
        )
        
        return {
            "user_id": user.id,
            "user_email": user.email,
            "user_name": user.name,
            "roadmap_count": len(roadmaps),
            "roadmaps": [
                {
                    "id": r.id,
                    "title": r.title,
                    "level": r.level,
                    "status": r.status.value,
                    "created_at": r.created_at.isoformat() if r.created_at else None
                }
                for r in roadmaps
            ]
        }

def verify_jwt_ownership(jwt_token: str, roadmap_id: str):
    """
    Verify roadmap ownership using a JWT token (simulates API call)
    
    Args:
        jwt_token: JWT token string
        roadmap_id: UUID of roadmap to check
    
    Returns:
        dict: Verification results
    """
    try:
        # Extract email from JWT (same as API does)
        email = verify_token(jwt_token)
        
        # Check ownership using email
        result = check_roadmap_ownership(roadmap_id, user_email=email)
        result["jwt_valid"] = True
        result["jwt_email"] = email
        
        return result
        
    except Exception as e:
        return {
            "jwt_valid": False,
            "error": f"JWT verification failed: {str(e)}"
        }

def interactive_check():
    """Interactive ownership checker"""
    print("\n🔍 Roadmap Ownership Verification Tool")
    print("=" * 40)
    
    while True:
        print("\nOptions:")
        print("1. Check roadmap ownership by user email")
        print("2. Check roadmap ownership by user ID")
        print("3. Check topic ownership")
        print("4. List user's roadmaps")
        print("5. Verify with JWT token")
        print("6. Exit")
        
        choice = input("\nEnter choice (1-6): ").strip()
        
        if choice == "1":
            roadmap_id = input("Enter roadmap ID: ").strip()
            user_email = input("Enter user email: ").strip()
            result = check_roadmap_ownership(roadmap_id, user_email=user_email)
            print(f"\nResult: {result}")
            
        elif choice == "2":
            roadmap_id = input("Enter roadmap ID: ").strip()
            user_id = input("Enter user ID: ").strip()
            result = check_roadmap_ownership(roadmap_id, user_id=user_id)
            print(f"\nResult: {result}")
            
        elif choice == "3":
            topic_id = input("Enter topic ID: ").strip()
            user_email = input("Enter user email: ").strip()
            result = check_topic_ownership(topic_id, user_email=user_email)
            print(f"\nResult: {result}")
            
        elif choice == "4":
            user_email = input("Enter user email: ").strip()
            result = list_user_roadmaps(user_email=user_email)
            print(f"\nResult: {result}")
            
        elif choice == "5":
            jwt_token = input("Enter JWT token: ").strip()
            roadmap_id = input("Enter roadmap ID: ").strip()
            result = verify_jwt_ownership(jwt_token, roadmap_id)
            print(f"\nResult: {result}")
            
        elif choice == "6":
            print("Goodbye!")
            break
            
        else:
            print("Invalid choice!")

if __name__ == "__main__":
    print("🔍 Roadmap Ownership Verification Utility")
    print("This tool helps you verify that roadmaps belong to specific users.")
    print("\nExample usage:")
    print("  python -c \"from verify_ownership import *; print(list_user_roadmaps(user_email='user@example.com'))\"")
    print("\nStarting interactive mode...")
    
    interactive_check()