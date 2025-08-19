#!/usr/bin/env python3
"""
Ownership Testing Scenarios
===========================

This script tests various ownership scenarios to ensure security works correctly.
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def create_test_users():
    """Create two test users for ownership testing"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    users = [
        {
            "name": f"Alice {timestamp}",
            "email": f"alice_{timestamp}@example.com",
            "password": "password123"
        },
        {
            "name": f"Bob {timestamp}",
            "email": f"bob_{timestamp}@example.com", 
            "password": "password123"
        }
    ]
    
    tokens = []
    
    for user in users:
        # Register
        register_response = requests.post(f"{BASE_URL}/auth/register", json=user)
        if register_response.status_code != 200:
            print(f"❌ Failed to register {user['name']}: {register_response.text}")
            return None, None
        
        # Login
        login_response = requests.post(f"{BASE_URL}/auth/login", json={
            "email": user["email"],
            "password": user["password"]
        })
        
        if login_response.status_code == 200:
            token = login_response.json()["access_token"]
            tokens.append((user, token))
            print(f"✅ Created user: {user['name']}")
        else:
            print(f"❌ Failed to login {user['name']}: {login_response.text}")
            return None, None
    
    return tokens[0], tokens[1]  # (alice, bob)

def test_ownership_scenarios():
    """Test various ownership scenarios"""
    print("\n🧪 Testing Ownership Scenarios")
    print("=" * 40)
    
    # Create test users
    alice_data, bob_data = create_test_users()
    if not alice_data or not bob_data:
        print("❌ Failed to create test users")
        return
    
    alice_user, alice_token = alice_data
    bob_user, bob_token = bob_data
    
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    
    print(f"\n👤 Alice: {alice_user['email']}")
    print(f"👤 Bob: {bob_user['email']}")
    
    # Scenario 1: Alice creates a roadmap
    print("\n📋 Scenario 1: Alice creates a roadmap")
    roadmap_data = {
        "selectedTopics": ["Python"],
        "skillLevel": "beginner",
        "duration": "7 days",
        "title": "Alice's Python Roadmap"
    }
    
    create_response = requests.post(
        f"{BASE_URL}/api/roadmap/create",
        json=roadmap_data,
        headers=alice_headers
    )
    
    if create_response.status_code == 200:
        alice_roadmap_id = create_response.json()["roadmap_id"]
        print(f"✅ Alice created roadmap: {alice_roadmap_id}")
    else:
        print(f"❌ Alice failed to create roadmap: {create_response.text}")
        return
    
    # Scenario 2: Alice can access her own roadmap
    print("\n📋 Scenario 2: Alice accesses her own roadmap")
    get_response = requests.get(
        f"{BASE_URL}/api/roadmap/{alice_roadmap_id}",
        headers=alice_headers
    )
    
    if get_response.status_code == 200:
        roadmap = get_response.json()
        print(f"✅ Alice can access her roadmap: '{roadmap['title']}'")
    else:
        print(f"❌ Alice cannot access her own roadmap: {get_response.text}")
    
    # Scenario 3: Bob CANNOT access Alice's roadmap
    print("\n🚫 Scenario 3: Bob tries to access Alice's roadmap")
    bob_get_response = requests.get(
        f"{BASE_URL}/api/roadmap/{alice_roadmap_id}",
        headers=bob_headers
    )
    
    if bob_get_response.status_code == 404:
        print("✅ SECURITY WORKING: Bob cannot access Alice's roadmap (404)")
    elif bob_get_response.status_code == 403:
        print("✅ SECURITY WORKING: Bob cannot access Alice's roadmap (403)")
    else:
        print(f"❌ SECURITY BREACH: Bob accessed Alice's roadmap! Status: {bob_get_response.status_code}")
        print(f"Response: {bob_get_response.text}")
    
    # Scenario 4: Bob creates his own roadmap
    print("\n📋 Scenario 4: Bob creates his own roadmap")
    bob_roadmap_data = {
        "selectedTopics": ["JavaScript"],
        "skillLevel": "intermediate",
        "duration": "14 days",
        "title": "Bob's JavaScript Roadmap"
    }
    
    bob_create_response = requests.post(
        f"{BASE_URL}/api/roadmap/create",
        json=bob_roadmap_data,
        headers=bob_headers
    )
    
    if bob_create_response.status_code == 200:
        bob_roadmap_id = bob_create_response.json()["roadmap_id"]
        print(f"✅ Bob created roadmap: {bob_roadmap_id}")
    else:
        print(f"❌ Bob failed to create roadmap: {bob_create_response.text}")
        return
    
    # Scenario 5: Each user sees only their own roadmaps
    print("\n📋 Scenario 5: Users see only their own roadmaps")
    
    # Alice's roadmaps
    alice_list_response = requests.get(f"{BASE_URL}/api/roadmaps", headers=alice_headers)
    if alice_list_response.status_code == 200:
        alice_roadmaps = alice_list_response.json()
        print(f"✅ Alice sees {len(alice_roadmaps)} roadmap(s)")
        for rm in alice_roadmaps:
            print(f"   - {rm['title']} (ID: {rm['id'][:8]}...)")
    
    # Bob's roadmaps
    bob_list_response = requests.get(f"{BASE_URL}/api/roadmaps", headers=bob_headers)
    if bob_list_response.status_code == 200:
        bob_roadmaps = bob_list_response.json()
        print(f"✅ Bob sees {len(bob_roadmaps)} roadmap(s)")
        for rm in bob_roadmaps:
            print(f"   - {rm['title']} (ID: {rm['id'][:8]}...)")
    
    # Scenario 6: Cross-user roadmap access fails
    print("\n🚫 Scenario 6: Cross-user access verification")
    
    # Alice tries to access Bob's roadmap
    alice_access_bob = requests.get(
        f"{BASE_URL}/api/roadmap/{bob_roadmap_id}",
        headers=alice_headers
    )
    
    if alice_access_bob.status_code in [404, 403]:
        print("✅ SECURITY WORKING: Alice cannot access Bob's roadmap")
    else:
        print(f"❌ SECURITY BREACH: Alice accessed Bob's roadmap! Status: {alice_access_bob.status_code}")
    
    # Bob tries to access Alice's roadmap (double-check)
    bob_access_alice = requests.get(
        f"{BASE_URL}/api/roadmap/{alice_roadmap_id}",
        headers=bob_headers
    )
    
    if bob_access_alice.status_code in [404, 403]:
        print("✅ SECURITY WORKING: Bob cannot access Alice's roadmap")
    else:
        print(f"❌ SECURITY BREACH: Bob accessed Alice's roadmap! Status: {bob_access_alice.status_code}")
    
    # Scenario 7: Unauthenticated access fails
    print("\n🚫 Scenario 7: Unauthenticated access")
    
    unauth_response = requests.get(f"{BASE_URL}/api/roadmap/{alice_roadmap_id}")
    if unauth_response.status_code == 401:
        print("✅ SECURITY WORKING: Unauthenticated request rejected (401)")
    else:
        print(f"❌ SECURITY ISSUE: Unauthenticated request got: {unauth_response.status_code}")
    
    print("\n🎉 Ownership testing completed!")
    
    return {
        "alice_roadmap_id": alice_roadmap_id,
        "bob_roadmap_id": bob_roadmap_id,
        "alice_token": alice_token,
        "bob_token": bob_token
    }

if __name__ == "__main__":
    test_ownership_scenarios()