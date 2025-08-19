# 🔒 Security Update: User-Roadmap Authentication & Authorization

This update fixes critical security vulnerabilities in the roadmap system and implements proper user authentication and authorization.

## 🚨 Critical Issues Fixed

### Before (Insecure)
- ❌ No authentication required for roadmap endpoints
- ❌ Anyone could access any roadmap by guessing the ID
- ❌ Client could set `user_id` to impersonate other users
- ❌ No authorization checks on roadmap ownership
- ❌ Weak database constraints

### After (Secure)
- ✅ JWT authentication required for all roadmap operations
- ✅ Users can only access their own roadmaps
- ✅ Server-side user ID extraction from JWT tokens
- ✅ Proper authorization checks on all endpoints
- ✅ Strong database foreign key constraints

## 📋 Changes Made

### 1. Enhanced Authentication (`app/core/security.py`)
```python
# New functions added:
- verify_token(token: str)           # Validates JWT and extracts email
- get_current_user(credentials)      # Dependency for authenticated routes
```

### 2. Updated Database Models (`app/models/roadmap.py`)
```python
# Roadmap model changes:
user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

# UserProgress model changes:  
user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
```

### 3. Secure API Schemas (`app/schemas/roadmap.py`)
```python
# RoadmapCreate - removed client-side user_id
class RoadmapCreate(BaseModel):
    selectedTopics: List[str]
    skillLevel: str
    duration: str
    title: Optional[str] = None  # No more user_id!

# ProgressUpdate - removed client-side user_id  
class ProgressUpdate(BaseModel):
    topic_id: str
    status: str  # No more user_id!
```

### 4. Protected API Endpoints (`api/roadmap.py`)

All endpoints now require authentication and implement proper authorization:

#### 🔐 POST `/api/roadmap/create`
- **Authentication**: Required (JWT Bearer token)
- **Authorization**: Creates roadmap for authenticated user only
- **Change**: `user_id` extracted from JWT, not from client

#### 🔐 GET `/api/roadmap/{roadmap_id}`
- **Authentication**: Required (JWT Bearer token)
- **Authorization**: Only returns roadmap if owned by authenticated user
- **Change**: Added `WHERE user_id = current_user.id` filter

#### 🔐 GET `/api/topic/{topic_id}/explanation`
- **Authentication**: Required (JWT Bearer token)
- **Authorization**: Only returns explanation for topics in user's roadmaps
- **Change**: Joins through roadmap to verify ownership

#### 🆕 GET `/api/roadmaps`
- **Authentication**: Required (JWT Bearer token)
- **Authorization**: Returns only authenticated user's roadmaps
- **Change**: New endpoint for getting user's roadmap list

#### 🆕 POST `/api/progress/update`
- **Authentication**: Required (JWT Bearer token)
- **Authorization**: Only updates progress for user's topics
- **Change**: New secure endpoint for progress tracking

## 🚀 How to Apply the Update

### Step 1: Install Dependencies
```bash
# Make sure you have the required packages
pip install python-jose[cryptography] python-multipart
```

### Step 2: Run Database Migration
```bash
# IMPORTANT: Run this before starting your application
python migrate_database.py
```

### Step 3: Update Your Frontend

#### Authentication Headers
All roadmap API calls now require authentication:

```javascript
// Before (insecure)
fetch('/api/roadmap/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        selectedTopics: ['Python'],
        skillLevel: 'beginner',
        duration: '7 days',
        user_id: 'some-user-id'  // ❌ Client-controlled
    })
});

// After (secure)  
fetch('/api/roadmap/create', {
    method: 'POST',
    headers: { 
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${userToken}`  // ✅ JWT token
    },
    body: JSON.stringify({
        selectedTopics: ['Python'],
        skillLevel: 'beginner', 
        duration: '7 days'
        // ✅ No user_id - extracted from JWT
    })
});
```

#### New Endpoints to Use
```javascript
// Get all user's roadmaps
fetch('/api/roadmaps', {
    headers: { 'Authorization': `Bearer ${userToken}` }
});

// Update topic progress
fetch('/api/progress/update', {
    method: 'POST',
    headers: { 
        'Authorization': `Bearer ${userToken}`,
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        topic_id: 'topic-uuid',
        status: 'completed'
        // ✅ No user_id needed
    })
});
```

### Step 4: Update Environment Variables
Make sure your `.env` file has a strong secret key:
```env
SECRET_KEY=your-super-secret-key-here-make-it-long-and-random
```

## 🧪 Testing the Security

### Test Authentication
```bash
# This should fail with 401 Unauthorized
curl -X GET http://localhost:8000/api/roadmaps

# This should work with valid token
curl -X GET http://localhost:8000/api/roadmaps \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Test Authorization
```bash
# Try to access another user's roadmap - should return 404
curl -X GET http://localhost:8000/api/roadmap/other-users-roadmap-id \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## 🔄 API Changes Summary

| Endpoint | Before | After |
|----------|--------|-------|
| `POST /api/roadmap/create` | ❌ No auth, client `user_id` | ✅ JWT auth, server `user_id` |
| `GET /api/roadmap/{id}` | ❌ No auth, any roadmap | ✅ JWT auth, user's roadmap only |
| `GET /api/topic/{id}/explanation` | ❌ No auth, any topic | ✅ JWT auth, user's topics only |
| `GET /api/roadmaps` | ❌ Didn't exist | ✅ New: get user's roadmaps |
| `POST /api/progress/update` | ❌ Didn't exist | ✅ New: update user's progress |

## ⚠️ Breaking Changes

1. **All roadmap endpoints now require authentication**
   - Add `Authorization: Bearer {token}` header to all requests

2. **Remove `user_id` from client requests**
   - `RoadmapCreate` schema no longer accepts `user_id`
   - `ProgressUpdate` schema no longer accepts `user_id`

3. **Database schema changes**
   - Run migration script before starting application
   - Foreign key constraints added
   - Orphaned data will be cleaned up

## 🛡️ Security Best Practices Implemented

1. **Principle of Least Privilege**: Users can only access their own data
2. **Server-side Authorization**: All permissions checked on server
3. **JWT Token Validation**: Proper token verification and user extraction
4. **Database Constraints**: Foreign keys prevent orphaned records
5. **Input Validation**: User ID cannot be manipulated by client
6. **Error Handling**: Consistent 404 responses for unauthorized access

## 🔍 Monitoring & Logging

The system now logs authentication and authorization events. Monitor for:
- Failed authentication attempts
- Attempts to access unauthorized resources
- Unusual patterns in roadmap access

## 📞 Support

If you encounter issues after applying this update:

1. Check that JWT tokens are being sent correctly
2. Verify the database migration completed successfully
3. Ensure all API calls include the `Authorization` header
4. Review the logs for specific error messages

This security update is **critical** and should be applied immediately to protect user data and prevent unauthorized access.