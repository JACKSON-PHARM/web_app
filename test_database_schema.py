"""
Test database schema to verify tables are set up correctly
Run this to check if tables have proper id columns and can accept inserts
"""
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.postgres_database_manager import PostgresDatabaseManager
from app.dependencies import get_db_manager
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_database_tables():
    """Test all database tables to verify schemas"""
    try:
        # Get database manager
        db_manager = get_db_manager()
        
        if not isinstance(db_manager, PostgresDatabaseManager):
            logger.error("❌ Not using PostgresDatabaseManager - cannot test")
            return
        
        tables_to_test = ['purchase_orders', 'branch_orders', 'supplier_invoices', 'current_stock']
        
        logger.info("=" * 80)
        logger.info("🧪 TESTING DATABASE TABLE SCHEMAS")
        logger.info("=" * 80)
        
        for table_name in tables_to_test:
            logger.info(f"\n📋 Testing {table_name}...")
            result = db_manager.test_table_schema(table_name)
            
            if result.get('status') == 'error':
                logger.error(f"❌ {table_name}: {result.get('error')}")
                continue
            
            logger.info(f"✅ {table_name}: {result['row_count']} rows")
            logger.info(f"   Columns ({len(result['columns'])}):")
            
            for col in result['columns']:
                auto_gen = "🔧 AUTO-GEN" if col['is_auto_generated'] else ""
                pk = "🔑 PK" if col['is_primary_key'] else ""
                nullable = "NULL" if col['nullable'] == 'YES' else "NOT NULL"
                default = f" DEFAULT {col['default']}" if col['default'] else ""
                
                logger.info(f"      - {col['name']}: {col['type']} {nullable}{default} {pk} {auto_gen}")
            
            # Check if id column is properly configured
            id_col = next((c for c in result['columns'] if c['name'] == 'id'), None)
            if id_col:
                if id_col['is_auto_generated']:
                    logger.info(f"   ✅ 'id' column is properly auto-generated")
                else:
                    logger.warning(f"   ⚠️ 'id' column is NOT auto-generated - this may cause insert errors!")
                    logger.warning(f"      Fix: ALTER TABLE {table_name} ALTER COLUMN id SET DEFAULT nextval('{table_name}_id_seq');")
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ Database schema test complete")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Error testing database: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == '__main__':
    test_database_tables()

