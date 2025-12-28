"""
Deploy stock_snapshot function and indexes to Supabase
Run this script to set up the PostgreSQL-first architecture
"""
import sys
import os
import logging

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from app.services.postgres_database_manager import PostgresDatabaseManager
from app.dependencies import get_db_manager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def deploy_stock_snapshot():
    """Deploy stock_snapshot function and indexes"""
    try:
        db_manager = get_db_manager()
        
        if not isinstance(db_manager, PostgresDatabaseManager):
            logger.error("❌ Not using PostgresDatabaseManager - cannot deploy")
            return False
        
        logger.info("📦 Deploying stock_snapshot function and indexes...")
        
        # Read SQL files
        script_dir = os.path.dirname(__file__)
        
        # Deploy function
        function_path = os.path.join(script_dir, 'create_stock_snapshot_function.sql')
        if os.path.exists(function_path):
            logger.info("📄 Reading function SQL...")
            with open(function_path, 'r', encoding='utf-8') as f:
                function_sql = f.read()
            
            logger.info("🔧 Creating stock_snapshot function...")
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(function_sql)
            conn.commit()
            cursor.close()
            db_manager.put_connection(conn)
            logger.info("✅ Function created successfully")
        else:
            logger.error(f"❌ Function SQL file not found: {function_path}")
            return False
        
        # Deploy indexes
        indexes_path = os.path.join(script_dir, 'create_stock_snapshot_indexes.sql')
        if os.path.exists(indexes_path):
            logger.info("📄 Reading indexes SQL...")
            with open(indexes_path, 'r', encoding='utf-8') as f:
                indexes_sql = f.read()
            
            logger.info("🔧 Creating indexes...")
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(indexes_sql)
            conn.commit()
            cursor.close()
            db_manager.put_connection(conn)
            logger.info("✅ Indexes created successfully")
        else:
            logger.warning(f"⚠️ Indexes SQL file not found: {indexes_path}")
        
        # Test the function
        logger.info("🧪 Testing stock_snapshot function...")
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM stock_snapshot('BABA DOGO HQ', 'BABA DOGO HQ', 'NILA') LIMIT 1
        """)
        result = cursor.fetchone()
        cursor.close()
        db_manager.put_connection(conn)
        
        if result:
            logger.info("✅ Function test successful!")
            logger.info(f"   Sample result: {list(result.keys())[:5]}...")
            return True
        else:
            logger.warning("⚠️ Function test returned no results (may be normal if no data)")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error deploying stock_snapshot: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = deploy_stock_snapshot()
    if success:
        logger.info("🎉 Deployment complete! You can now use stock_snapshot() function.")
        logger.info("💡 Next: Update services to use stock_snapshot() instead of materialized views")
    else:
        logger.error("❌ Deployment failed. Check errors above.")
        sys.exit(1)

