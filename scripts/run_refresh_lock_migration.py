"""
Run migration to create refresh lock functions
This is optional - the app will work without these functions, but they provide
better concurrent refresh protection.
"""
import os
import sys
import logging
import psycopg2
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Run the refresh lock migration"""
    try:
        # Read migration SQL file
        migration_file = Path(__file__).parent / "migrations" / "001_fix_id_sequences_and_refresh_lock.sql"
        
        if not migration_file.exists():
            logger.error(f"❌ Migration file not found: {migration_file}")
            return False
        
        logger.info(f"📄 Reading migration file: {migration_file}")
        with open(migration_file, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        # Connect to database
        logger.info("🔌 Connecting to database...")
        conn = psycopg2.connect(settings.DATABASE_URL)
        cursor = conn.cursor()
        
        # Execute migration
        logger.info("🚀 Running migration...")
        cursor.execute(migration_sql)
        conn.commit()
        
        # Verify functions were created
        cursor.execute("""
            SELECT proname 
            FROM pg_proc 
            WHERE proname IN ('acquire_refresh_lock', 'is_refresh_locked', 'release_refresh_lock')
        """)
        functions = [row[0] for row in cursor.fetchall()]
        
        if len(functions) == 3:
            logger.info("✅ Migration completed successfully!")
            logger.info(f"   Created functions: {', '.join(functions)}")
            
            # Verify table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'refresh_lock'
                )
            """)
            table_exists = cursor.fetchone()[0]
            
            if table_exists:
                logger.info("✅ refresh_lock table exists")
            else:
                logger.warning("⚠️ refresh_lock table not found (may have been created in a different schema)")
        else:
            logger.warning(f"⚠️ Expected 3 functions, found {len(functions)}: {functions}")
        
        cursor.close()
        conn.close()
        
        logger.info("✅ Migration script completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("🔄 Refresh Lock Migration Script")
    logger.info("=" * 70)
    logger.info("")
    logger.info("This script creates refresh lock functions in the database.")
    logger.info("These functions are OPTIONAL - the app will work without them,")
    logger.info("but they provide better protection against concurrent refreshes.")
    logger.info("")
    
    success = run_migration()
    
    if success:
        logger.info("")
        logger.info("✅ Migration completed! Refresh lock functions are now available.")
        logger.info("   The app will now use these functions for concurrent refresh protection.")
        sys.exit(0)
    else:
        logger.error("")
        logger.error("❌ Migration failed. Check the error messages above.")
        logger.error("   The app will continue to work without lock functions.")
        sys.exit(1)

