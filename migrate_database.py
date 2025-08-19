#!/usr/bin/env python3
"""
Database Migration Script for User-Roadmap Security Updates
===========================================================

This script handles the migration from the old insecure schema to the new secure schema:

Changes:
1. Add foreign key constraints on user_id fields
2. Make user_id fields non-nullable where appropriate
3. Add indexes for better performance
4. Clean up any orphaned data

Run this script AFTER updating your models but BEFORE running your application.

Usage:
    python migrate_database.py
"""

import logging
from sqlalchemy import text
from app.db.database import engine, SessionLocal
from app.models.user import User
from app.models.roadmap import Roadmap, UserProgress

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_database():
    """Perform database migration to add security constraints"""
    
    with SessionLocal() as db:
        try:
            logger.info("Starting database migration...")
            
            # Step 1: Clean up orphaned roadmaps (roadmaps with invalid user_ids)
            logger.info("Step 1: Cleaning up orphaned roadmaps...")
            
            # Find roadmaps with null or invalid user_ids
            orphaned_roadmaps = db.execute(text("""
                SELECT r.id, r.title, r.user_id 
                FROM roadmaps r 
                LEFT JOIN users u ON r.user_id = u.id 
                WHERE r.user_id IS NULL OR u.id IS NULL
            """)).fetchall()
            
            if orphaned_roadmaps:
                logger.warning(f"Found {len(orphaned_roadmaps)} orphaned roadmaps:")
                for roadmap in orphaned_roadmaps:
                    logger.warning(f"  - Roadmap ID: {roadmap.id}, Title: {roadmap.title}, User ID: {roadmap.user_id}")
                
                # Delete orphaned roadmaps (this will cascade to milestones and topics)
                db.execute(text("""
                    DELETE FROM roadmaps 
                    WHERE user_id IS NULL 
                    OR user_id NOT IN (SELECT id FROM users)
                """))
                logger.info(f"Deleted {len(orphaned_roadmaps)} orphaned roadmaps")
            else:
                logger.info("No orphaned roadmaps found")
            
            # Step 2: Clean up orphaned user progress
            logger.info("Step 2: Cleaning up orphaned user progress...")
            
            orphaned_progress = db.execute(text("""
                SELECT up.id, up.user_id, up.topic_id 
                FROM user_progress up 
                LEFT JOIN users u ON up.user_id = u.id 
                WHERE u.id IS NULL
            """)).fetchall()
            
            if orphaned_progress:
                logger.warning(f"Found {len(orphaned_progress)} orphaned progress records")
                db.execute(text("""
                    DELETE FROM user_progress 
                    WHERE user_id NOT IN (SELECT id FROM users)
                """))
                logger.info(f"Deleted {len(orphaned_progress)} orphaned progress records")
            else:
                logger.info("No orphaned progress records found")
            
            # Step 3: Add indexes if they don't exist (PostgreSQL syntax)
            logger.info("Step 3: Adding database indexes...")
            
            try:
                # Add index on roadmaps.user_id if it doesn't exist
                db.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_roadmaps_user_id ON roadmaps(user_id)
                """))
                
                # Add index on user_progress.user_id if it doesn't exist
                db.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_user_progress_user_id ON user_progress(user_id)
                """))
                
                logger.info("Database indexes added successfully")
            except Exception as e:
                logger.warning(f"Could not add indexes (this is normal for SQLite): {e}")
            
            # Step 4: Add foreign key constraints (if using PostgreSQL)
            logger.info("Step 4: Adding foreign key constraints...")
            
            try:
                # Add foreign key constraint for roadmaps.user_id
                db.execute(text("""
                    ALTER TABLE roadmaps 
                    ADD CONSTRAINT fk_roadmaps_user_id 
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                """))
                logger.info("Added foreign key constraint for roadmaps.user_id")
            except Exception as e:
                logger.warning(f"Could not add foreign key constraint for roadmaps (may already exist): {e}")
            
            try:
                # Add foreign key constraint for user_progress.user_id
                db.execute(text("""
                    ALTER TABLE user_progress 
                    ADD CONSTRAINT fk_user_progress_user_id 
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                """))
                logger.info("Added foreign key constraint for user_progress.user_id")
            except Exception as e:
                logger.warning(f"Could not add foreign key constraint for user_progress (may already exist): {e}")
            
            # Step 5: Make user_id columns NOT NULL (if using PostgreSQL)
            logger.info("Step 5: Setting user_id columns to NOT NULL...")
            
            try:
                db.execute(text("ALTER TABLE roadmaps ALTER COLUMN user_id SET NOT NULL"))
                logger.info("Set roadmaps.user_id to NOT NULL")
            except Exception as e:
                logger.warning(f"Could not set roadmaps.user_id to NOT NULL: {e}")
            
            try:
                db.execute(text("ALTER TABLE user_progress ALTER COLUMN user_id SET NOT NULL"))
                logger.info("Set user_progress.user_id to NOT NULL")
            except Exception as e:
                logger.warning(f"Could not set user_progress.user_id to NOT NULL: {e}")
            
            # Commit all changes
            db.commit()
            logger.info("Database migration completed successfully!")
            
            # Step 6: Verify the migration
            logger.info("Step 6: Verifying migration...")
            
            total_roadmaps = db.execute(text("SELECT COUNT(*) FROM roadmaps")).scalar()
            total_users = db.execute(text("SELECT COUNT(*) FROM users")).scalar()
            total_progress = db.execute(text("SELECT COUNT(*) FROM user_progress")).scalar()
            
            logger.info(f"Migration verification:")
            logger.info(f"  - Total users: {total_users}")
            logger.info(f"  - Total roadmaps: {total_roadmaps}")
            logger.info(f"  - Total progress records: {total_progress}")
            
            if total_roadmaps > 0 and total_users == 0:
                logger.error("ERROR: Found roadmaps but no users! This indicates a problem.")
                return False
            
            logger.info("Migration verification passed!")
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            db.rollback()
            raise

if __name__ == "__main__":
    try:
        success = migrate_database()
        if success:
            logger.info("✅ Database migration completed successfully!")
            logger.info("You can now start your application with the new security features.")
        else:
            logger.error("❌ Database migration failed!")
            exit(1)
    except Exception as e:
        logger.error(f"❌ Migration script failed: {e}")
        exit(1)