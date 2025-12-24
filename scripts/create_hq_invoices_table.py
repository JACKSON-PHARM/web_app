"""
Create HQ Invoices table in Supabase
This table stores processed invoice and transfer data from BABA DOGO HQ
"""
import sys
import os
import psycopg2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_hq_invoices_table(connection_string: str):
    """Create hq_invoices table in Supabase"""
    
    try:
        conn = psycopg2.connect(connection_string)
        cursor = conn.cursor()
        
        logger.info("Creating hq_invoices table...")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hq_invoices (
                id SERIAL PRIMARY KEY,
                branch TEXT NOT NULL,
                invoice_number TEXT NOT NULL,
                item_code TEXT NOT NULL,
                item_name TEXT,
                quantity REAL DEFAULT 0,
                ref TEXT,
                date DATE NOT NULL,
                this_month_qty REAL DEFAULT 0,
                document_type TEXT DEFAULT 'Invoice',  -- 'Invoice' or 'Branch Transfer'
                source_branch TEXT,  -- For transfers: source branch
                destination_branch TEXT,  -- For transfers: destination branch
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(branch, invoice_number, item_code, date)
            );
        """)
        
        # Create indexes for faster queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_hq_invoices_branch ON hq_invoices(branch);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_hq_invoices_item ON hq_invoices(item_code);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_hq_invoices_date ON hq_invoices(date DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_hq_invoices_branch_item ON hq_invoices(branch, item_code);")
        
        conn.commit()
        logger.info("SUCCESS: hq_invoices table created successfully")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating table: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
            cursor.close()
            conn.close()
        return False

if __name__ == "__main__":
    # Try to get connection string from config
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, os.path.join(script_dir, ".."))
        from app.config import settings
        if settings.DATABASE_URL:
            connection_string = settings.DATABASE_URL
            print("Using DATABASE_URL from app.config")
        else:
            print("ERROR: DATABASE_URL not set in config")
            sys.exit(1)
    except Exception as e:
        if len(sys.argv) < 2:
            print("Usage: python create_hq_invoices_table.py [connection_string]")
            print("\nIf connection_string is not provided, the script will try to load from app.config")
            sys.exit(1)
        connection_string = sys.argv[1]
    
    success = create_hq_invoices_table(connection_string)
    
    if success:
        print("\nSUCCESS: HQ invoices table created successfully!")
    else:
        print("\nERROR: Failed to create table")
        sys.exit(1)

