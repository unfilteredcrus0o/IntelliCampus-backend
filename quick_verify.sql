-- Quick Database Verification Queries
-- Copy and paste these into pgcli to verify roadmap-user associations

-- 1. Show all users and their roadmap counts
SELECT 
    u.id,
    u.name,
    u.email,
    COUNT(r.id) as roadmap_count
FROM users u
LEFT JOIN roadmaps r ON u.id = r.user_id
GROUP BY u.id, u.name, u.email
ORDER BY u.created_at;

-- 2. Show all roadmaps with their owners
SELECT 
    r.id as roadmap_id,
    SUBSTRING(r.id, 1, 8) || '...' as short_id,
    r.title,
    r.status,
    u.name as owner,
    u.email as owner_email,
    r.created_at
FROM roadmaps r
JOIN users u ON r.user_id = u.id
ORDER BY r.created_at DESC;

-- 3. Check for any orphaned roadmaps (should be empty)
SELECT 
    r.id,
    r.title,
    r.user_id,
    'ORPHANED - NO OWNER FOUND' as issue
FROM roadmaps r
LEFT JOIN users u ON r.user_id = u.id
WHERE u.id IS NULL;

-- 4. Verify foreign key constraints are working
SELECT 
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY' 
    AND tc.table_name IN ('roadmaps', 'user_progress');

-- 5. Test the exact security query used by the API
-- Replace these UUIDs with real ones from your database:
-- SELECT r.* FROM roadmaps r WHERE r.id = 'YOUR_ROADMAP_ID' AND r.user_id = 'YOUR_USER_ID';

-- 6. Show user progress associations
SELECT 
    u.email as user_email,
    r.title as roadmap_title,
    m.name as milestone_name,
    t.name as topic_name,
    up.status as progress_status
FROM user_progress up
JOIN users u ON up.user_id = u.id
JOIN topics t ON up.topic_id = t.id
JOIN milestones m ON t.milestone_id = m.id
JOIN roadmaps r ON m.roadmap_id = r.id
ORDER BY u.email, r.title, m.order;