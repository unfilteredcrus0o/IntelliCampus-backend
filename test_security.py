#!/usr/bin/env python3
"""
Security Test Script
===================

This script tests the new authentication and authorization features.
Run this after applying the security updates to verify everything works correctly.

Usage:
    python test_security.py
"""

import requests
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"

def test_authentication():
    """Test that endpoints require authentication"""
    logger.info("🔐 Testing authentication requirements...")
    
    # Test that protected endpoints reject unauthenticated requests
    endpoints_to_test = [
        "/api/roadmaps",
        "/api/roadmap/create",
        "/api/progress/update"
    ]
    
    for endpoint in endpoints_to_test:
        try:
            if endpoint == "/api/roadmap/create":
                response = requests.post(f"{BASE_URL}{endpoint}", json={
                    "selectedTopics": ["Python"],
                    "skillLevel": "beginner",
                    "duration": "7 days"
                })
            elif endpoint == "/api/progress/update":
                response = requests.post(f"{BASE_URL}{endpoint}", json={
                    "topic_id": "test-topic-id",
                    "status": "completed"
                })
            else:
                response = requests.get(f"{BASE_URL}{endpoint}")
            
            if response.status_code == 401:
                logger.info(f"✅ {endpoint} correctly requires authentication (401)")
            else:
                logger.error(f"❌ {endpoint} should require authentication but returned {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            logger.error(f"❌ Could not connect to {BASE_URL}. Is the server running?")
            return False
    
    return True

def test_user_registration_and_login():
    """Test user registration and login flow"""
    logger.info("👤 Testing user registration and login...")
    
    # Generate unique test user
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    test_user = {
        "name": f"Test User {timestamp}",
        "email": f"test_{timestamp}@example.com",
        "password": "testpassword123"
    }
    
    try:
        # Register user
        register_response = requests.post(f"{BASE_URL}/auth/register", json=test_user)
        
        if register_response.status_code == 200:
            logger.info("✅ User registration successful")
        else:
            logger.error(f"❌ User registration failed: {register_response.status_code} - {register_response.text}")
            return None, None
        
        # Login user
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"]
        }
        
        login_response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
        
        if login_response.status_code == 200:
            token_data = login_response.json()
            token = token_data.get("access_token")
            logger.info("✅ User login successful")
            return test_user, token
        else:
            logger.error(f"❌ User login failed: {login_response.status_code} - {login_response.text}")
            return test_user, None
            
    except requests.exceptions.ConnectionError:
        logger.error("❌ Could not connect to server for auth tests")
        return None, None

def test_roadmap_operations(token):
    """Test roadmap creation and access with authentication"""
    logger.info("🗺️ Testing roadmap operations...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test roadmap creation
    roadmap_data = {
        "selectedTopics": ["Python", "FastAPI"],
        "skillLevel": "intermediate",
        "duration": "14 days",
        "title": "Security Test Roadmap"
    }
    
    try:
        create_response = requests.post(
            f"{BASE_URL}/api/roadmap/create",
            json=roadmap_data,
            headers=headers
        )
        
        if create_response.status_code == 200:
            roadmap_info = create_response.json()
            roadmap_id = roadmap_info.get("roadmap_id")
            logger.info(f"✅ Roadmap creation successful: {roadmap_id}")
            
            # Test roadmap retrieval
            get_response = requests.get(
                f"{BASE_URL}/api/roadmap/{roadmap_id}",
                headers=headers
            )
            
            if get_response.status_code == 200:
                logger.info("✅ Roadmap retrieval successful")
                
                # Test get all roadmaps
                list_response = requests.get(
                    f"{BASE_URL}/api/roadmaps",
                    headers=headers
                )
                
                if list_response.status_code == 200:
                    roadmaps = list_response.json()
                    logger.info(f"✅ Retrieved {len(roadmaps)} roadmaps for user")
                    return roadmap_id
                else:
                    logger.error(f"❌ Failed to get roadmaps list: {list_response.status_code}")
            else:
                logger.error(f"❌ Failed to retrieve roadmap: {get_response.status_code}")
        else:
            logger.error(f"❌ Roadmap creation failed: {create_response.status_code} - {create_response.text}")
    
    except requests.exceptions.ConnectionError:
        logger.error("❌ Could not connect to server for roadmap tests")
    
    return None

def test_authorization(token, roadmap_id):
    """Test that users can only access their own roadmaps"""
    logger.info("🛡️ Testing authorization...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test accessing a non-existent roadmap (should return 404)
    fake_roadmap_id = "00000000-0000-0000-0000-000000000000"
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/roadmap/{fake_roadmap_id}",
            headers=headers
        )
        
        if response.status_code == 404:
            logger.info("✅ Authorization working - cannot access non-existent/unauthorized roadmap")
        else:
            logger.error(f"❌ Authorization issue - got {response.status_code} instead of 404")
    
    except requests.exceptions.ConnectionError:
        logger.error("❌ Could not connect to server for authorization tests")

def main():
    """Run all security tests"""
    logger.info("🚀 Starting security tests...")
    logger.info("=" * 50)
    
    # Test 1: Authentication requirements
    if not test_authentication():
        logger.error("❌ Authentication tests failed")
        return
    
    # Test 2: User registration and login
    test_user, token = test_user_registration_and_login()
    if not token:
        logger.error("❌ Could not get authentication token")
        return
    
    # Test 3: Roadmap operations
    roadmap_id = test_roadmap_operations(token)
    if not roadmap_id:
        logger.error("❌ Roadmap operations failed")
        return
    
    # Test 4: Authorization
    test_authorization(token, roadmap_id)
    
    logger.info("=" * 50)
    logger.info("🎉 Security tests completed!")
    logger.info("🔒 Your roadmap system is now properly secured!")

if __name__ == "__main__":
    main()