"""
Update stock_snapshot SQL function on Render/Supabase database
This script can be run locally but connects to Render's database using DATABASE_URL
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config import settings

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def update_stock_snapshot_function_on_render():
    """Update the stock_snapshot function on Render's database"""
    conn = None
    cursor = None
    
    try:
        # Check if DATABASE_URL is set
        database_url = os.getenv('DATABASE_URL') or settings.DATABASE_URL
        
        if not database_url:
            logger.error("ERROR: DATABASE_URL not set in environment variables")
            logger.error("   Please set DATABASE_URL to your Render/Supabase connection string")
            logger.error("   Example: postgresql://user:pass@host:port/dbname")
            return False
        
        logger.info("Connecting to Render/Supabase database...")
        logger.info(f"   Database host: {database_url.split('@')[1].split('/')[0] if '@' in database_url else 'N/A'}")
        
        conn = psycopg2.connect(database_url)
        logger.info("SUCCESS: Connected to database")
        
        cursor = conn.cursor()
        
        # Read SQL function file
        sql_file_path = os.path.join(os.path.dirname(__file__), 'create_stock_snapshot_function.sql')
        logger.info(f"Reading SQL function from: {sql_file_path}")
        
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_function = f.read()
        
        # Execute the function creation
        logger.info("Updating stock_snapshot function on Render database...")
        cursor.execute(sql_function)
        conn.commit()
        
        logger.info("SUCCESS: stock_snapshot function updated on Render!")
        logger.info("   The function now supports:")
        logger.info("   - Cross-company stock views (target and source can be different companies)")
        logger.info("   - Improved item name fallback (NO SALES DATA items show actual names)")
        
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
            logger.info(f"Verified: Function exists with signature: stock_snapshot({result[1]})")
            if 'p_target_company' in result[1] and 'p_source_company' in result[1]:
                logger.info("SUCCESS: Function has cross-company support!")
            else:
                logger.warning("WARNING: Function may not have been updated correctly")
        else:
            logger.warning("WARNING: Could not verify function creation")
        
        cursor.close()
        conn.close()
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("UPDATE COMPLETE!")
        logger.info("=" * 70)
        logger.info("The stock_snapshot function has been updated on Render.")
        logger.info("Refresh your stock view page to see the changes.")
        logger.info("=" * 70)
        
        return True
        
    except FileNotFoundError:
        logger.error(f"ERROR: SQL file not found: {sql_file_path}")
        return False
    except psycopg2.OperationalError as e:
        logger.error(f"ERROR: Database connection failed: {e}")
        logger.error("   Please check:")
        logger.error("   1. DATABASE_URL is set correctly")
        logger.error("   2. Database is accessible from your network")
        logger.error("   3. Firewall allows your IP address")
        return False
    except psycopg2.Error as e:
        logger.error(f"ERROR: Database error: {e}")
        if conn:
            conn.rollback()
        return False
    except Exception as e:
        logger.error(f"ERROR: {e}")
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
    print("=" * 70)
    print("Updating stock_snapshot SQL Function on Render/Supabase")
    print("=" * 70)
    print("")
    print("This script will update the stock_snapshot function on your")
    print("Render/Supabase database to support:")
    print("  - Cross-company stock views")
    print("  - Improved item name fallback (NO SALES DATA -> actual names)")
    print("")
    print("Make sure DATABASE_URL is set to your Render/Supabase connection string.")
    print("")
    
    success = update_stock_snapshot_function_on_render()
    
    if success:
        sys.exit(0)
    else:
        print("")
        print("UPDATE FAILED!")
        print("Please check the error messages above and try again.")
        sys.exit(1)

