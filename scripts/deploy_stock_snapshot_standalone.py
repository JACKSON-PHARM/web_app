"""
Standalone script to deploy stock_snapshot function to Supabase
Can be run directly with DATABASE_URL environment variable or as argument
"""
import sys
import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def deploy_stock_snapshot(connection_string: str = None):
    """Deploy stock_snapshot function and indexes"""
    try:
        # Get connection string from argument, environment variable, or .env file
        if connection_string:
            db_url = connection_string
        elif os.getenv('DATABASE_URL'):
            db_url = os.getenv('DATABASE_URL')
        else:
            logger.error("❌ DATABASE_URL not provided. Usage:")
            logger.error("   python scripts/deploy_stock_snapshot_standalone.py [DATABASE_URL]")
            logger.error("   OR set DATABASE_URL environment variable")
            return False
        
        logger.info("🔌 Connecting to Supabase PostgreSQL...")
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Test connection
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        logger.info(f"✅ Connected! PostgreSQL version: {version.split(',')[0]}")
        
        # Read and execute function SQL
        script_dir = os.path.dirname(__file__)
        function_path = os.path.join(script_dir, 'create_stock_snapshot_function.sql')
        
        if not os.path.exists(function_path):
            logger.error(f"❌ Function SQL file not found: {function_path}")
            return False
        
        logger.info("📄 Reading function SQL...")
        with open(function_path, 'r', encoding='utf-8') as f:
            function_sql = f.read()
        
        logger.info("🔧 Creating stock_snapshot function...")
        cursor.execute(function_sql)
        conn.commit()
        logger.info("✅ Function created successfully")
        
        # Read and execute indexes SQL
        indexes_path = os.path.join(script_dir, 'create_stock_snapshot_indexes.sql')
        if os.path.exists(indexes_path):
            logger.info("📄 Reading indexes SQL...")
            with open(indexes_path, 'r', encoding='utf-8') as f:
                indexes_sql = f.read()
            
            logger.info("🔧 Creating indexes...")
            cursor.execute(indexes_sql)
            conn.commit()
            logger.info("✅ Indexes created successfully")
        else:
            logger.warning(f"⚠️ Indexes SQL file not found: {indexes_path}")
        
        # Test the function
        logger.info("🧪 Testing stock_snapshot function...")
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT * FROM stock_snapshot('BABA DOGO HQ', 'BABA DOGO HQ', 'NILA') LIMIT 1
        """)
        result = cursor.fetchone()
        
        if result:
            logger.info("✅ Function test successful!")
            logger.info(f"   Sample columns: {list(result.keys())[:5]}...")
        else:
            logger.warning("⚠️ Function test returned no results (may be normal if no data)")
        
        cursor.close()
        conn.close()
        
        logger.info("🎉 Deployment complete! You can now use stock_snapshot() function.")
        return True
        
    except psycopg2.OperationalError as e:
        logger.error(f"❌ Connection failed: {e}")
        logger.error("\nTroubleshooting:")
        logger.error("   1. Check if DATABASE_URL is correct")
        logger.error("   2. Check if password is URL-encoded (special characters)")
        logger.error("   3. Try Session Pooler connection string instead")
        return False
    except Exception as e:
        logger.error(f"❌ Error deploying stock_snapshot: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    # Get connection string from command line argument or environment
    db_url = None
    if len(sys.argv) > 1:
        db_url = sys.argv[1]
    
    success = deploy_stock_snapshot(db_url)
    if not success:
        sys.exit(1)

