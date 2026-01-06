"""
Script to clean up duplicate stock records in current_stock table.
This ensures only one version per (branch, company, item_code) exists,
keeping only the most recent version (highest id).

Run this script to immediately reduce database size by removing duplicates.
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


def cleanup_duplicates():
    """Clean up duplicate stock records"""
    if not settings.DATABASE_URL:
        logger.error("❌ DATABASE_URL not set! Please set it in environment variable or .env file")
        logger.error("   Example: export DATABASE_URL='postgresql://user:pass@host:port/db'")
        return
    
    db_manager = PostgresDatabaseManager(settings.DATABASE_URL)
    conn = None
    
    try:
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        # Count total records before cleanup
        cursor.execute("SELECT COUNT(*) FROM current_stock")
        total_before = cursor.fetchone()[0]
        logger.info(f"📊 Total records before cleanup: {total_before:,}")
        
        # Count duplicate groups
        cursor.execute("""
            SELECT COUNT(*) 
            FROM (
                SELECT branch, company, item_code, COUNT(*) as cnt
                FROM current_stock
                GROUP BY branch, company, item_code
                HAVING COUNT(*) > 1
            ) duplicates
        """)
        duplicate_groups = cursor.fetchone()[0]
        logger.info(f"📊 Duplicate groups found: {duplicate_groups:,}")
        
        if duplicate_groups == 0:
            logger.info("✅ No duplicates found - database is clean!")
            return
        
        # Delete old versions, keeping only the most recent (highest id)
        logger.info("🧹 Deleting old stock versions (keeping most recent per branch/company/item_code)...")
        cursor.execute("""
            DELETE FROM current_stock a
            USING current_stock b
            WHERE UPPER(TRIM(a.branch)) = UPPER(TRIM(b.branch))
              AND UPPER(TRIM(a.company)) = UPPER(TRIM(b.company))
              AND a.item_code = b.item_code
              AND a.id < b.id
        """)
        deleted_count = cursor.rowcount
        # Don't commit yet - we'll commit after counting
        
        # Count total records after cleanup
        cursor.execute("SELECT COUNT(*) FROM current_stock")
        total_after = cursor.fetchone()[0]
        
        logger.info(f"✅ Cleanup complete!")
        logger.info(f"   Deleted: {deleted_count:,} duplicate records")
        logger.info(f"   Remaining: {total_after:,} records")
        logger.info(f"   Space saved: {total_before - total_after:,} records ({(total_before - total_after) / total_before * 100:.1f}% reduction)")
        
        # Commit the transaction first
        conn.commit()
        
        # Vacuum to reclaim space (must run outside transaction)
        logger.info("🧹 Running VACUUM to reclaim space...")
        # Close cursor and get a new connection for VACUUM (VACUUM can't run in transaction)
        cursor.close()
        db_manager.put_connection(conn)
        
        # Get a new connection for VACUUM (autocommit mode)
        vacuum_conn = db_manager.get_connection()
        vacuum_conn.set_session(autocommit=True)  # VACUUM requires autocommit
        vacuum_cursor = vacuum_conn.cursor()
        try:
            vacuum_cursor.execute("VACUUM ANALYZE current_stock")
            logger.info("✅ VACUUM complete - space reclaimed!")
        finally:
            vacuum_cursor.close()
            vacuum_conn.close()  # Close instead of returning to pool (autocommit connection)
        
    except Exception as e:
        logger.error(f"❌ Error during cleanup: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            cursor.close()
            db_manager.put_connection(conn)


def check_duplicates():
    """Check for duplicates without deleting"""
    if not settings.DATABASE_URL:
        logger.error("❌ DATABASE_URL not set! Please set it in environment variable or .env file")
        logger.error("   Example: export DATABASE_URL='postgresql://user:pass@host:port/db'")
        return {"total": 0, "unique": 0, "duplicates": 0}
    
    db_manager = PostgresDatabaseManager(settings.DATABASE_URL)
    conn = None
    
    try:
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        # Count total records
        cursor.execute("SELECT COUNT(*) FROM current_stock")
        total = cursor.fetchone()[0]
        
        # Count unique (branch, company, item_code) combinations
        cursor.execute("""
            SELECT COUNT(DISTINCT (UPPER(TRIM(branch)), UPPER(TRIM(company)), item_code))
            FROM current_stock
        """)
        unique_combinations = cursor.fetchone()[0]
        
        duplicates = total - unique_combinations
        
        logger.info(f"📊 Current Stock Analysis:")
        logger.info(f"   Total records: {total:,}")
        logger.info(f"   Unique combinations: {unique_combinations:,}")
        logger.info(f"   Duplicate records: {duplicates:,}")
        
        if duplicates > 0:
            logger.info(f"   ⚠️  Duplicates found! Run cleanup to remove them.")
        else:
            logger.info(f"   ✅ No duplicates - database is clean!")
        
        return {
            "total": total,
            "unique": unique_combinations,
            "duplicates": duplicates
        }
        
    except Exception as e:
        logger.error(f"❌ Error checking duplicates: {e}")
        raise
    finally:
        if conn:
            cursor.close()
            db_manager.put_connection(conn)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean up duplicate stock records")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check for duplicates, don't delete"
    )
    
    args = parser.parse_args()
    
    if args.check_only:
        check_duplicates()
    else:
        # First check, then clean
        logger.info("🔍 Checking for duplicates...")
        stats = check_duplicates()
        
        if stats["duplicates"] > 0:
            logger.info("\n🧹 Starting cleanup...")
            cleanup_duplicates()
        else:
            logger.info("\n✅ No cleanup needed - database is already clean!")

