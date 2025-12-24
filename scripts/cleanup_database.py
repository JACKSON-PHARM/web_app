"""
Database Cleanup Script
Removes old data to minimize database size for Supabase migration
Keeps only procurement-essential data (last 3 months)
"""
import sqlite3
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_database(db_path: str, keep_months: int = 3):
    """
    Clean database to keep only essential procurement data
    
    Args:
        db_path: Path to SQLite database
        keep_months: Number of months of historical data to keep (default: 3)
    """
    if not os.path.exists(db_path):
        logger.error(f"Database not found: {db_path}")
        return False
    
    # Get original size
    original_size_mb = os.path.getsize(db_path) / (1024 * 1024)
    logger.info(f"📊 Original database size: {original_size_mb:.2f} MB")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Calculate cutoff date (3 months ago)
        cutoff_date = (datetime.now() - timedelta(days=keep_months * 30)).strftime('%Y-%m-%d')
        logger.info(f"🗓️ Keeping data from {cutoff_date} onwards")
        
        # 1. Clean old purchase orders
        logger.info("🧹 Cleaning old purchase orders...")
        cursor.execute("""
            DELETE FROM purchase_orders 
            WHERE document_date < ?
        """, (cutoff_date,))
        deleted_po = cursor.rowcount
        logger.info(f"   Deleted {deleted_po} old purchase orders")
        
        # 2. Clean old branch orders
        logger.info("🧹 Cleaning old branch orders...")
        cursor.execute("""
            DELETE FROM branch_orders 
            WHERE document_date < ?
        """, (cutoff_date,))
        deleted_bo = cursor.rowcount
        logger.info(f"   Deleted {deleted_bo} old branch orders")
        
        # 3. Clean old supplier invoices
        logger.info("🧹 Cleaning old supplier invoices...")
        # Check which date column exists
        cursor.execute("PRAGMA table_info(supplier_invoices)")
        columns = [row[1] for row in cursor.fetchall()]
        
        date_column = None
        if 'invoice_date' in columns:
            date_column = 'invoice_date'
        elif 'document_date' in columns:
            date_column = 'document_date'
        elif 'date' in columns:
            date_column = 'date'
        
        if date_column:
            cursor.execute(f"""
                DELETE FROM supplier_invoices 
                WHERE {date_column} < ?
            """, (cutoff_date,))
            deleted_inv = cursor.rowcount
            logger.info(f"   Deleted {deleted_inv} old supplier invoices (using {date_column})")
        else:
            logger.warning(f"   Could not find date column in supplier_invoices (columns: {columns})")
            deleted_inv = 0
        
        # 4. Remove ALL stock snapshots (we only need current_stock, replaced on each refresh)
        logger.info("🧹 Removing all stock snapshots (keeping only current_stock)...")
        cursor.execute("DELETE FROM stock_data")
        deleted_stock = cursor.rowcount
        logger.info(f"   Deleted {deleted_stock} stock snapshots (keeping only current_stock)")
        
        # Optionally drop the stock_data table entirely (not needed for procurement)
        try:
            cursor.execute("DROP TABLE IF EXISTS stock_data")
            logger.info("   Dropped stock_data table (not needed - using current_stock only)")
        except Exception as e:
            logger.warning(f"   Could not drop stock_data table: {e}")
        
        # 5. Remove sales data (not needed for procurement)
        logger.info("🧹 Removing sales data (not needed for procurement)...")
        try:
            cursor.execute("DROP TABLE IF EXISTS sales")
            cursor.execute("DROP TABLE IF EXISTS sales_details")
            logger.info("   Removed sales tables")
        except Exception as e:
            logger.warning(f"   Could not remove sales tables: {e}")
        
        # 6. Add indexes for performance
        logger.info("📊 Creating indexes...")
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_purchase_orders_date ON purchase_orders(document_date DESC)",
            "CREATE INDEX IF NOT EXISTS idx_branch_orders_date ON branch_orders(document_date DESC)",
            "CREATE INDEX IF NOT EXISTS idx_supplier_invoices_date ON supplier_invoices(invoice_date DESC)",
            "CREATE INDEX IF NOT EXISTS idx_current_stock_branch ON current_stock(branch, company, item_code)",
        ]
        
        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
            except Exception as e:
                logger.warning(f"   Could not create index: {e}")
        
        # Commit changes
        conn.commit()
        
        # Vacuum to reclaim space
        logger.info("🧹 Vacuuming database to reclaim space...")
        cursor.execute("VACUUM")
        
        # Get new size
        conn.close()
        new_size_mb = os.path.getsize(db_path) / (1024 * 1024)
        reduction = original_size_mb - new_size_mb
        reduction_pct = (reduction / original_size_mb * 100) if original_size_mb > 0 else 0
        
        logger.info(f"✅ Cleanup complete!")
        logger.info(f"📊 New database size: {new_size_mb:.2f} MB")
        logger.info(f"📉 Reduced by: {reduction:.2f} MB ({reduction_pct:.1f}%)")
        
        if new_size_mb < 500:
            logger.info(f"✅ Database fits in Supabase free tier (500MB limit)")
        else:
            logger.warning(f"⚠️ Database still too large ({new_size_mb:.2f} MB). Consider:")
            logger.warning("   - Reducing keep_months to 2 or 1")
            logger.warning("   - Removing more stock snapshots")
            logger.warning("   - Compressing large text fields")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error during cleanup: {e}")
        import traceback
        logger.error(traceback.format_exc())
        conn.rollback()
        conn.close()
        return False

def get_table_sizes(db_path: str):
    """Get size of each table"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' 
        ORDER BY name
    """)
    tables = cursor.fetchall()
    
    logger.info("\n📊 Table sizes:")
    total_rows = 0
    
    for (table_name,) in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            total_rows += count
            
            # Estimate size (rough)
            cursor.execute(f"SELECT COUNT(*) FROM pragma_table_info('{table_name}')")
            col_count = cursor.fetchone()[0]
            estimated_size_mb = (count * col_count * 100) / (1024 * 1024)  # Rough estimate
            
            logger.info(f"   {table_name}: {count:,} rows (~{estimated_size_mb:.2f} MB)")
        except Exception as e:
            logger.warning(f"   {table_name}: Could not get size ({e})")
    
    logger.info(f"\n   Total rows: {total_rows:,}")
    conn.close()

if __name__ == "__main__":
    import sys
    
    # Default database path
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        # Try to find database
        possible_paths = [
            "cache/pharma_stock.db",
            "web_app/cache/pharma_stock.db",
            "../cache/pharma_stock.db",
            "pharma_stock.db"
        ]
        
        db_path = None
        for path in possible_paths:
            if os.path.exists(path):
                db_path = path
                break
        
        if not db_path:
            logger.error("Database not found. Please provide path as argument:")
            logger.error("  python cleanup_database.py /path/to/pharma_stock.db")
            sys.exit(1)
    
    logger.info(f"🗄️ Database: {db_path}")
    
    # Show table sizes before cleanup
    logger.info("\n📊 BEFORE CLEANUP:")
    get_table_sizes(db_path)
    
    # Run cleanup
    keep_months = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    success = cleanup_database(db_path, keep_months=keep_months)
    
    if success:
        # Show table sizes after cleanup
        logger.info("\n📊 AFTER CLEANUP:")
        get_table_sizes(db_path)
        
        logger.info("\n✅ Ready for Supabase migration!")
    else:
        logger.error("\n❌ Cleanup failed. Check errors above.")
        sys.exit(1)

