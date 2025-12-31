"""
Diagnostic script to check NILA stock data in the database
"""
import os
import sys
import logging

# Add app root to path
app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, app_root)

from app.config import settings
from app.services.postgres_database_manager import PostgresDatabaseManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_nila_stock():
    """Check NILA stock data in the database"""
    if not settings.DATABASE_URL:
        logger.error("❌ DATABASE_URL is not set. Cannot check database.")
        return
    
    try:
        db_manager = PostgresDatabaseManager(settings.DATABASE_URL)
        
        logger.info("=" * 80)
        logger.info("🔍 Checking NILA Stock Data in Database")
        logger.info("=" * 80)
        
        # Check total stock records
        total_stock = db_manager.execute_query("SELECT COUNT(*) as count FROM current_stock")
        logger.info(f"\n📊 Total stock records: {total_stock[0]['count'] if total_stock else 0}")
        
        # Check NILA stock records
        nila_stock = db_manager.execute_query(
            "SELECT COUNT(*) as count FROM current_stock WHERE company = %s",
            ('NILA',)
        )
        logger.info(f"📊 NILA stock records: {nila_stock[0]['count'] if nila_stock else 0}")
        
        # Check DAIMA stock records
        daima_stock = db_manager.execute_query(
            "SELECT COUNT(*) as count FROM current_stock WHERE company = %s",
            ('DAIMA',)
        )
        logger.info(f"📊 DAIMA stock records: {daima_stock[0]['count'] if daima_stock else 0}")
        
        # Check NILA branches
        nila_branches = db_manager.execute_query(
            "SELECT DISTINCT branch, COUNT(*) as count FROM current_stock WHERE company = %s GROUP BY branch ORDER BY branch",
            ('NILA',)
        )
        logger.info(f"\n🏢 NILA Branches with stock data ({len(nila_branches)} branches):")
        for branch in nila_branches:
            logger.info(f"   {branch['branch']}: {branch['count']:,} items")
        
        # Sample NILA stock items
        sample_items = db_manager.execute_query(
            "SELECT item_code, item_name, branch, stock_pieces, company FROM current_stock WHERE company = %s LIMIT 10",
            ('NILA',)
        )
        logger.info(f"\n📦 Sample NILA stock items (first 10):")
        for item in sample_items:
            logger.info(f"   {item['item_code']} | {item['item_name'][:50]} | {item['branch']} | Stock: {item['stock_pieces']}")
        
        # Check branch_orders
        branch_orders_count = db_manager.execute_query("SELECT COUNT(*) as count FROM branch_orders")
        logger.info(f"\n📋 Total branch_orders records: {branch_orders_count[0]['count'] if branch_orders_count else 0}")
        
        nila_branch_orders = db_manager.execute_query(
            "SELECT COUNT(*) as count FROM branch_orders WHERE company = %s",
            ('NILA',)
        )
        logger.info(f"📋 NILA branch_orders records: {nila_branch_orders[0]['count'] if nila_branch_orders else 0}")
        
        # Check other tables
        tables_to_check = ['purchase_orders', 'supplier_invoices', 'hq_invoices']
        logger.info(f"\n📊 Other table counts:")
        for table in tables_to_check:
            try:
                count = db_manager.execute_query(f"SELECT COUNT(*) as count FROM {table}")
                nila_count = db_manager.execute_query(
                    f"SELECT COUNT(*) as count FROM {table} WHERE company = %s",
                    ('NILA',)
                )
                logger.info(f"   {table}: {count[0]['count'] if count else 0} total, {nila_count[0]['count'] if nila_count else 0} NILA")
            except Exception as e:
                logger.warning(f"   {table}: Error - {e}")
        
        # Check if there are any items with zero stock
        zero_stock = db_manager.execute_query(
            "SELECT COUNT(*) as count FROM current_stock WHERE company = %s AND stock_pieces = 0",
            ('NILA',)
        )
        logger.info(f"\n⚠️ NILA items with zero stock: {zero_stock[0]['count'] if zero_stock else 0}")
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ Diagnostic check complete")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Error checking database: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    check_nila_stock()

