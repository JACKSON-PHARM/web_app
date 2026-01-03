"""
Update stock_snapshot SQL function to support cross-company stock views
Run this script to update the function in your database
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_stock_snapshot_function():
    """Update the stock_snapshot function in the database"""
    conn = None
    cursor = None
    
    try:
        # Connect to database
        if not settings.DATABASE_URL:
            logger.error("❌ DATABASE_URL not set in environment variables")
            logger.error("   Please set DATABASE_URL in your .env file or environment")
            return False
        
        logger.info("🔌 Connecting to database...")
        conn = psycopg2.connect(settings.DATABASE_URL)
        logger.info("✅ Connected to database")
        
        cursor = conn.cursor()
        
        # Read SQL function file
        sql_file_path = os.path.join(os.path.dirname(__file__), 'create_stock_snapshot_function.sql')
        logger.info(f"📖 Reading SQL function from: {sql_file_path}")
        
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_function = f.read()
        
        # Execute the function creation
        logger.info("🔄 Updating stock_snapshot function...")
        cursor.execute(sql_function)
        conn.commit()
        
        logger.info("✅ Successfully updated stock_snapshot function!")
        logger.info("   The function now supports cross-company stock views:")
        logger.info("   - p_target_company: Company for target branch")
        logger.info("   - p_source_company: Company for source branch (optional, defaults to target_company)")
        
        # Verify the function was created
        cursor.execute("""
            SELECT 
                p.proname as function_name,
                pg_get_function_arguments(p.oid) as arguments
            FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            WHERE n.nspname = 'public' 
            AND p.proname = 'stock_snapshot'
        """)
        
        result = cursor.fetchone()
        if result:
            logger.info(f"✅ Verified function exists: {result[0]}({result[1]})")
        else:
            logger.warning("⚠️ Could not verify function creation")
        
        cursor.close()
        conn.close()
        
        return True
        
    except FileNotFoundError:
        logger.error(f"❌ SQL file not found: {sql_file_path}")
        return False
    except psycopg2.Error as e:
        logger.error(f"❌ Database error: {e}")
        if conn:
            conn.rollback()
        return False
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("🔄 Updating stock_snapshot SQL Function")
    logger.info("=" * 70)
    
    success = update_stock_snapshot_function()
    
    if success:
        logger.info("=" * 70)
        logger.info("✅ Update completed successfully!")
        logger.info("=" * 70)
        sys.exit(0)
    else:
        logger.error("=" * 70)
        logger.error("❌ Update failed!")
        logger.error("=" * 70)
        sys.exit(1)

