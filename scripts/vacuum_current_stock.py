"""
Script to run VACUUM FULL on current_stock table to reclaim disk space.
This will shrink the table file after duplicate cleanup.

WARNING: VACUUM FULL takes an exclusive lock on the table.
Do not run this during active use - it will block all operations on current_stock.
"""
import os
import sys
import logging

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config import settings
from app.services.postgres_database_manager import PostgresDatabaseManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_table_size(cursor, table_name: str) -> dict:
    """Get table size information"""
    cursor.execute("""
        SELECT 
            pg_size_pretty(pg_total_relation_size(%s)) as total_size,
            pg_size_pretty(pg_relation_size(%s)) as table_size,
            pg_size_pretty(pg_total_relation_size(%s) - pg_relation_size(%s)) as index_size,
            pg_size_pretty(pg_total_relation_size(%s) - pg_relation_size(%s, 'main')) as total_with_toast
        FROM (SELECT %s::regclass) t
    """, (table_name, table_name, table_name, table_name, table_name, table_name, table_name))
    
    result = cursor.fetchone()
    return {
        'total_size': result[0],
        'table_size': result[1],
        'index_size': result[2],
        'total_with_toast': result[3]
    }


def vacuum_full_current_stock():
    """Run VACUUM FULL on current_stock table"""
    db_manager = PostgresDatabaseManager(settings.DATABASE_URL)
    conn = None
    
    try:
        logger.info("🔌 Connecting to database...")
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        # Get table size before VACUUM
        logger.info("📊 Checking table size before VACUUM...")
        size_before = get_table_size(cursor, 'current_stock')
        
        # Get row count
        cursor.execute("SELECT COUNT(*) FROM current_stock")
        row_count = cursor.fetchone()[0]
        
        logger.info(f"📊 Current Stock Table Status:")
        logger.info(f"   Rows: {row_count:,}")
        logger.info(f"   Total Size: {size_before['total_size']}")
        logger.info(f"   Table Size: {size_before['table_size']}")
        logger.info(f"   Index Size: {size_before['index_size']}")
        
        # Confirm before proceeding
        logger.warning("⚠️  WARNING: VACUUM FULL will:")
        logger.warning("   1. Take an EXCLUSIVE LOCK on current_stock table")
        logger.warning("   2. Block ALL operations on the table during execution")
        logger.warning("   3. Rewrite the entire table (this may take a few minutes)")
        logger.warning("")
        logger.info("🔄 Starting VACUUM FULL...")
        logger.info("   This may take a few minutes depending on table size...")
        
        # Close current connection (VACUUM FULL requires autocommit mode)
        cursor.close()
        db_manager.put_connection(conn)
        
        # Get a new connection in autocommit mode for VACUUM
        import psycopg2
        vacuum_conn = psycopg2.connect(settings.DATABASE_URL)
        vacuum_conn.set_session(autocommit=True)
        vacuum_cursor = vacuum_conn.cursor()
        
        # Run VACUUM FULL with VERBOSE for progress
        vacuum_cursor.execute("VACUUM (FULL, ANALYZE, VERBOSE) current_stock")
        
        logger.info("✅ VACUUM FULL completed!")
        
        # Get table size after VACUUM (need regular connection for queries)
        vacuum_cursor.close()
        vacuum_conn.close()
        
        # Get new connection for size check
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        logger.info("📊 Checking table size after VACUUM...")
        size_after = get_table_size(cursor, 'current_stock')
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("📊 VACUUM RESULTS")
        logger.info("=" * 60)
        logger.info(f"Before:")
        logger.info(f"   Total Size: {size_before['total_size']}")
        logger.info(f"   Table Size: {size_before['table_size']}")
        logger.info(f"")
        logger.info(f"After:")
        logger.info(f"   Total Size: {size_after['total_size']}")
        logger.info(f"   Table Size: {size_after['table_size']}")
        logger.info(f"")
        logger.info("✅ Space reclaimed successfully!")
        logger.info("=" * 60)
        
        cursor.close()
        db_manager.put_connection(conn)
        
    except Exception as e:
        logger.error(f"❌ Error during VACUUM: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if conn:
            try:
                conn.close()
            except:
                pass
        raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run VACUUM FULL on current_stock table")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Skip confirmation prompt (use with caution)"
    )
    
    args = parser.parse_args()
    
    if not args.confirm:
        print("WARNING: This will lock the current_stock table during execution!")
        print("   Make sure no one is actively using the application.")
        print("   Press Ctrl+C to cancel, or wait 5 seconds to continue...")
        import time
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            print("\nCancelled by user")
            sys.exit(0)
    
    try:
        vacuum_full_current_stock()
        print("\nVACUUM FULL completed successfully!")
        print("   Check Supabase dashboard to see the reduced table size.")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)

