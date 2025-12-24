"""
Cleanup Script for Old Data
Removes data older than 30 days to stay within Supabase free tier limits

Tables cleaned:
- supplier_invoices (document_date < 30 days ago)
- grn (grn_date < 30 days ago)
- purchase_orders (order_date < 30 days ago)
- branch_orders (order_date < 30 days ago)
- hq_invoices (document_date < 30 days ago)

Stock data: Only keeps most recent version (handled by stock fetcher)
Inventory analysis: Kept constant (not cleaned)
"""
import os
import sys
from datetime import datetime, timedelta
import logging

# Add app root to path
app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, app_root)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_old_data(connection_string: str, retention_days: int = 30):
    """
    Clean up data older than retention_days
    
    Args:
        connection_string: PostgreSQL connection string
        retention_days: Number of days to retain (default 30)
    """
    try:
        import psycopg2
        
        logger.info("=" * 70)
        logger.info("🧹 DATA CLEANUP - Removing Old Records")
        logger.info("=" * 70)
        logger.info(f"📅 Retention period: {retention_days} days")
        
        cutoff_date = (datetime.now() - timedelta(days=retention_days)).date()
        logger.info(f"🗑️  Removing records older than: {cutoff_date}")
        
        # Connect to database
        conn = psycopg2.connect(connection_string)
        conn.autocommit = False
        cursor = conn.cursor()
        
        total_deleted = 0
        
        # Cleanup supplier_invoices
        logger.info("\n📋 Cleaning supplier_invoices...")
        try:
            cursor.execute("""
                DELETE FROM supplier_invoices 
                WHERE document_date < %s;
            """, (cutoff_date,))
            deleted = cursor.rowcount
            conn.commit()
            total_deleted += deleted
            logger.info(f"   ✅ Deleted {deleted:,} supplier invoice records")
        except Exception as e:
            logger.warning(f"   ⚠️ Error cleaning supplier_invoices: {e}")
            conn.rollback()
        
        # Cleanup GRN
        logger.info("📋 Cleaning grn...")
        try:
            cursor.execute("""
                DELETE FROM grn 
                WHERE grn_date < %s;
            """, (cutoff_date,))
            deleted = cursor.rowcount
            conn.commit()
            total_deleted += deleted
            logger.info(f"   ✅ Deleted {deleted:,} GRN records")
        except Exception as e:
            logger.warning(f"   ⚠️ Error cleaning grn: {e}")
            conn.rollback()
        
        # Cleanup purchase_orders
        logger.info("📋 Cleaning purchase_orders...")
        try:
            cursor.execute("""
                DELETE FROM purchase_orders 
                WHERE order_date < %s;
            """, (cutoff_date,))
            deleted = cursor.rowcount
            conn.commit()
            total_deleted += deleted
            logger.info(f"   ✅ Deleted {deleted:,} purchase order records")
        except Exception as e:
            logger.warning(f"   ⚠️ Error cleaning purchase_orders: {e}")
            conn.rollback()
        
        # Cleanup branch_orders
        logger.info("📋 Cleaning branch_orders...")
        try:
            cursor.execute("""
                DELETE FROM branch_orders 
                WHERE order_date < %s;
            """, (cutoff_date,))
            deleted = cursor.rowcount
            conn.commit()
            total_deleted += deleted
            logger.info(f"   ✅ Deleted {deleted:,} branch order records")
        except Exception as e:
            logger.warning(f"   ⚠️ Error cleaning branch_orders: {e}")
            conn.rollback()
        
        # Cleanup hq_invoices
        logger.info("📋 Cleaning hq_invoices...")
        try:
            cursor.execute("""
                DELETE FROM hq_invoices 
                WHERE document_date < %s;
            """, (cutoff_date,))
            deleted = cursor.rowcount
            conn.commit()
            total_deleted += deleted
            logger.info(f"   ✅ Deleted {deleted:,} HQ invoice records")
        except Exception as e:
            logger.warning(f"   ⚠️ Error cleaning hq_invoices: {e}")
            conn.rollback()
        
        # Show summary
        logger.info("\n" + "=" * 70)
        logger.info(f"✅ CLEANUP COMPLETE!")
        logger.info(f"   Total records deleted: {total_deleted:,}")
        logger.info("=" * 70)
        
        # Show current record counts
        logger.info("\n📊 Current record counts:")
        tables = [
            ('supplier_invoices', 'document_date'),
            ('grn', 'grn_date'),
            ('purchase_orders', 'order_date'),
            ('branch_orders', 'order_date'),
            ('hq_invoices', 'document_date')
        ]
        
        for table_name, date_col in tables:
            try:
                cursor.execute(f"""
                    SELECT COUNT(*) FROM {table_name} 
                    WHERE {date_col} >= %s;
                """, (cutoff_date,))
                count = cursor.fetchone()[0]
                logger.info(f"   {table_name}: {count:,} records (last {retention_days} days)")
            except Exception as e:
                logger.warning(f"   Could not count {table_name}: {e}")
        
        cursor.close()
        conn.close()
        
        return {"success": True, "total_deleted": total_deleted}
        
    except Exception as e:
        logger.error(f"❌ Error during cleanup: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"success": False, "total_deleted": 0, "error": str(e)}

if __name__ == "__main__":
    # Get connection string
    connection_string = None
    
    if len(sys.argv) >= 2:
        connection_string = sys.argv[1]
    else:
        # Try to load from app config
        try:
            from app.config import settings
            if settings.DATABASE_URL:
                connection_string = settings.DATABASE_URL
                logger.info("✅ Using DATABASE_URL from app.config")
        except Exception as e:
            logger.warning(f"Could not load from config: {e}")
    
    if not connection_string:
        print("Usage: python cleanup_old_data.py [connection_string] [retention_days]")
        print("\nIf connection_string is not provided, the script will try to load from app.config")
        print("\nExample:")
        print('  python cleanup_old_data.py')
        print('  python cleanup_old_data.py "postgresql://user:pass@host:port/db"')
        print('  python cleanup_old_data.py "postgresql://user:pass@host:port/db" 30')
        sys.exit(1)
    
    retention_days = 30
    if len(sys.argv) >= 3:
        try:
            retention_days = int(sys.argv[2])
        except:
            logger.warning(f"Invalid retention_days, using default: 30")
    
    success = cleanup_old_data(connection_string, retention_days)
    
    if success:
        print("\n✅ Cleanup completed successfully!")
    else:
        print("\n❌ Cleanup failed!")
        sys.exit(1)

