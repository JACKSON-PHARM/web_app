"""
Create Supabase tables for users, credentials, and materialized views
Run this once to set up the database schema
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import hashlib
import logging

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_users_table(conn):
    """Create users table in Supabase"""
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_users (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                is_admin BOOLEAN DEFAULT FALSE,
                active BOOLEAN DEFAULT TRUE,
                subscription_days INTEGER DEFAULT 0,
                subscription_expires TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated_by TEXT,
                deactivated_at TIMESTAMP,
                deactivated_by TEXT
            )
        """)
        
        # Create index on username for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_app_users_username ON app_users(username)
        """)
        
        # Create index on active status
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_app_users_active ON app_users(active)
        """)
        
        conn.commit()
        logger.info("✅ Created app_users table")
        
        # Create default admin user if not exists
        default_password_hash = hashlib.sha256('9542'.encode()).hexdigest()
        cursor.execute("""
            INSERT INTO app_users (username, password_hash, is_admin, subscription_days, subscription_expires, active)
            VALUES ('9542', %s, TRUE, 36500, %s, TRUE)
            ON CONFLICT (username) DO NOTHING
        """, (default_password_hash, (datetime.now() + timedelta(days=36500)).isoformat()))
        
        conn.commit()
        logger.info("✅ Created default admin user (username: 9542)")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating users table: {e}")
        raise

def create_credentials_table(conn):
    """Create credentials table in Supabase"""
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_credentials (
                id SERIAL PRIMARY KEY,
                company_name TEXT NOT NULL UNIQUE,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                base_url TEXT,
                is_enabled BOOLEAN DEFAULT TRUE,
                last_tested TIMESTAMP,
                last_test_success BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create index on company_name
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_app_credentials_company ON app_credentials(company_name)
        """)
        
        # Create index on is_enabled
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_app_credentials_enabled ON app_credentials(is_enabled)
        """)
        
        conn.commit()
        logger.info("✅ Created app_credentials table")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating credentials table: {e}")
        raise

def create_stock_view_materialized_view(conn):
    """Create materialized view for stock view with all required columns"""
    cursor = conn.cursor()
    
    try:
        # Drop existing materialized view if exists
        cursor.execute("DROP MATERIALIZED VIEW IF EXISTS stock_view_materialized CASCADE")
        
        # Full materialized view with all joins - pre-computed for performance
        cursor.execute("""
            CREATE MATERIALIZED VIEW stock_view_materialized AS
            WITH unique_items AS (
                SELECT DISTINCT 
                    item_code,
                    MAX(item_name) as item_name
                FROM current_stock
                GROUP BY item_code
            ),
            target_branch_stock AS (
                SELECT 
                    item_code,
                    item_name,
                    branch,
                    company,
                    stock_pieces as branch_stock,
                    pack_size,
                    unit_price,
                    stock_value
                FROM current_stock
            ),
            source_branch_stock AS (
                SELECT 
                    item_code,
                    branch,
                    company,
                    stock_pieces as supplier_stock
                FROM current_stock
            ),
            last_order_info AS (
                SELECT 
                    item_code,
                    branch,
                    company,
                    MAX(document_date) as last_order_date
                FROM (
                    SELECT item_code, document_date, branch, company
                    FROM purchase_orders
                    UNION ALL
                    SELECT item_code, document_date, branch, company
                    FROM branch_orders
                    UNION ALL
                    SELECT item_code, date as document_date, branch, 'NILA' as company
                    FROM hq_invoices
                ) all_orders
                GROUP BY item_code, branch, company
            ),
            last_order_details AS (
                SELECT DISTINCT ON (ao.item_code, ao.branch, ao.company)
                    ao.item_code,
                    ao.branch,
                    ao.company,
                    ao.document_number as last_order_doc,
                    ao.quantity as last_order_quantity
                FROM (
                    SELECT item_code, document_date, document_number, quantity, branch, company
                    FROM purchase_orders
                    UNION ALL
                    SELECT item_code, document_date, document_number, quantity, branch, company
                    FROM branch_orders
                    UNION ALL
                    SELECT item_code, date as document_date, invoice_number as document_number, quantity, branch, 'NILA' as company
                    FROM hq_invoices
                ) ao
                INNER JOIN last_order_info loi ON ao.item_code = loi.item_code 
                    AND ao.document_date = loi.last_order_date
                    AND ao.branch = loi.branch
                    AND ao.company = loi.company
                ORDER BY ao.item_code, ao.branch, ao.company, ao.document_date DESC, ao.document_number DESC
            ),
            last_supply_info AS (
                SELECT 
                    item_code,
                    branch,
                    company,
                    MAX(document_date) as last_supply_date
                FROM supplier_invoices
                GROUP BY item_code, branch, company
            ),
            last_supply_details AS (
                SELECT DISTINCT ON (si.item_code, si.branch, si.company)
                    si.item_code,
                    si.branch,
                    si.company,
                    si.document_number as last_supply_doc,
                    si.units as last_supply_quantity
                FROM supplier_invoices si
                INNER JOIN last_supply_info lsi ON si.item_code = lsi.item_code 
                    AND si.document_date = lsi.last_supply_date
                    AND si.branch = lsi.branch
                    AND si.company = lsi.company
                ORDER BY si.item_code, si.branch, si.company, si.document_date DESC, si.document_number DESC
            ),
            last_invoice_info AS (
                SELECT 
                    item_code,
                    branch,
                    MAX(date) as last_invoice_date
                FROM hq_invoices
                GROUP BY item_code, branch
            ),
            last_invoice_details AS (
                SELECT DISTINCT ON (hi.item_code, hi.branch)
                    hi.item_code,
                    hi.branch,
                    hi.invoice_number as last_invoice_doc,
                    hi.quantity as last_invoice_quantity
                FROM hq_invoices hi
                INNER JOIN last_invoice_info lii ON hi.item_code = lii.item_code 
                    AND hi.date = lii.last_invoice_date
                    AND hi.branch = lii.branch
                ORDER BY hi.item_code, hi.branch, hi.date DESC, hi.invoice_number DESC
            ),
            inventory_analysis AS (
                SELECT 
                    item_code,
                    branch_name as branch,
                    company_name as company,
                    abc_class,
                    COALESCE(adjusted_amc, base_amc, 0) as amc_pieces,
                    stock_recommendation as stock_comment
                FROM inventory_analysis_new
            )
            SELECT 
                ui.item_code,
                COALESCE(tbs.item_name, ui.item_name) as item_name,
                tbs.branch as target_branch,
                tbs.company as target_company,
                COALESCE(sbs.supplier_stock, 0) as supplier_stock,
                COALESCE(tbs.branch_stock, 0) as branch_stock,
                COALESCE(tbs.pack_size, 1) as pack_size,
                COALESCE(tbs.unit_price, 0) as unit_price,
                COALESCE(tbs.stock_value, 0) as stock_value,
                loi.last_order_date,
                lod.last_order_doc,
                lod.last_order_quantity,
                lii.last_invoice_date,
                lid.last_invoice_doc,
                lid.last_invoice_quantity,
                lsi.last_supply_date,
                lsd.last_supply_doc,
                lsd.last_supply_quantity,
                lsi.last_supply_date as last_grn_date,
                lsd.last_supply_quantity as last_grn_quantity,
                lsd.last_supply_doc as last_grn_doc,
                ia.abc_class,
                COALESCE(ia.amc_pieces, 0) as amc,
                ia.stock_comment,
                0.0 as stock_level_pct
            FROM unique_items ui
            LEFT JOIN target_branch_stock tbs ON ui.item_code = tbs.item_code
            LEFT JOIN source_branch_stock sbs ON ui.item_code = sbs.item_code 
                AND sbs.branch = tbs.branch AND sbs.company = tbs.company
            LEFT JOIN last_order_info loi ON ui.item_code = loi.item_code 
                AND loi.branch = tbs.branch AND loi.company = tbs.company
            LEFT JOIN last_order_details lod ON ui.item_code = lod.item_code 
                AND lod.branch = tbs.branch AND lod.company = tbs.company
            LEFT JOIN last_supply_info lsi ON ui.item_code = lsi.item_code 
                AND lsi.branch = tbs.branch AND lsi.company = tbs.company
            LEFT JOIN last_supply_details lsd ON ui.item_code = lsd.item_code 
                AND lsd.branch = tbs.branch AND lsd.company = tbs.company
            LEFT JOIN last_invoice_info lii ON ui.item_code = lii.item_code 
                AND lii.branch = tbs.branch
            LEFT JOIN last_invoice_details lid ON ui.item_code = lid.item_code 
                AND lid.branch = tbs.branch
            LEFT JOIN inventory_analysis ia ON ui.item_code = ia.item_code 
                AND ia.branch = tbs.branch AND ia.company = tbs.company
        """)
        
        # Create unique index for CONCURRENT refresh
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_stock_view_unique 
            ON stock_view_materialized(item_code, target_branch, target_company)
        """)
        
        # Create indexes for fast lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stock_view_item_code ON stock_view_materialized(item_code)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stock_view_branch_company ON stock_view_materialized(target_branch, target_company)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stock_view_company ON stock_view_materialized(target_company)
        """)
        
        conn.commit()
        logger.info("✅ Created stock_view_materialized view (full columns)")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating stock view materialized view: {e}")
        raise

def create_priority_items_materialized_view(conn):
    """Create materialized view for priority items with all required columns"""
    cursor = conn.cursor()
    
    try:
        # Drop existing materialized view if exists
        cursor.execute("DROP MATERIALIZED VIEW IF EXISTS priority_items_materialized CASCADE")
        
        # Full view with inventory analysis data
        cursor.execute("""
            CREATE MATERIALIZED VIEW priority_items_materialized AS
            WITH source_stock AS (
                SELECT 
                    item_code,
                    item_name,
                    branch as source_branch,
                    company as source_company,
                    stock_pieces as source_stock_pieces,
                    pack_size as source_pack_size
                FROM current_stock
                WHERE stock_pieces > 0
            ),
            target_stock AS (
                SELECT 
                    item_code,
                    branch as target_branch,
                    company as target_company,
                    stock_pieces as target_stock_pieces,
                    pack_size as target_pack_size
                FROM current_stock
            ),
            inventory_analysis AS (
                SELECT 
                    item_code,
                    branch_name as target_branch,
                    company_name as target_company,
                    abc_class,
                    COALESCE(adjusted_amc, base_amc, 0) as amc_pieces,
                    stock_recommendation as stock_comment
                FROM inventory_analysis_new
            ),
            last_order_info AS (
                SELECT 
                    item_code,
                    branch,
                    company,
                    MAX(document_date) as last_order_date
                FROM (
                    SELECT item_code, document_date, branch, company
                    FROM purchase_orders
                    UNION ALL
                    SELECT item_code, document_date, branch, company
                    FROM branch_orders
                    UNION ALL
                    SELECT item_code, date as document_date, branch, 'NILA' as company
                    FROM hq_invoices
                ) all_orders
                GROUP BY item_code, branch, company
            )
            SELECT 
                ss.item_code,
                MAX(ss.item_name) as item_name,
                ss.source_branch,
                ss.source_company,
                MAX(ss.source_stock_pieces) as source_stock_pieces,
                MAX(ss.source_pack_size) as source_pack_size,
                ts.target_branch,
                ts.target_company,
                COALESCE(MAX(ts.target_stock_pieces), 0) as target_stock_pieces,
                COALESCE(MAX(ts.target_pack_size), MAX(ss.source_pack_size), 1) as pack_size,
                COALESCE(ia.abc_class, '') as abc_class,
                COALESCE(ia.amc_pieces, 0) as amc_pieces,
                ia.stock_comment,
                loi.last_order_date,
                0.0 as stock_level_pct
            FROM source_stock ss
            LEFT JOIN target_stock ts ON ss.item_code = ts.item_code
            LEFT JOIN inventory_analysis ia ON ss.item_code = ia.item_code 
                AND ts.target_branch = ia.target_branch 
                AND ts.target_company = ia.target_company
            LEFT JOIN last_order_info loi ON ss.item_code = loi.item_code 
                AND loi.branch = ts.target_branch 
                AND loi.company = ts.target_company
            WHERE (ts.target_stock_pieces IS NULL 
                OR ts.target_stock_pieces <= 0
                OR ts.target_stock_pieces < 1000)
                AND (ia.abc_class IS NULL OR ia.abc_class IN ('A', 'B', 'C'))
            GROUP BY ss.item_code, ss.source_branch, ss.source_company, 
                     ts.target_branch, ts.target_company, 
                     ia.abc_class, ia.amc_pieces, ia.stock_comment, loi.last_order_date
        """)
        
        # Create unique index for CONCURRENT refresh
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_priority_items_unique 
            ON priority_items_materialized(item_code, source_branch, source_company, target_branch, target_company)
        """)
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_priority_items_source ON priority_items_materialized(source_branch, source_company)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_priority_items_target ON priority_items_materialized(target_branch, target_company)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_priority_items_item_code ON priority_items_materialized(item_code)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_priority_items_abc ON priority_items_materialized(abc_class)
        """)
        
        conn.commit()
        logger.info("✅ Created priority_items_materialized view (full columns)")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating priority items materialized view: {e}")
        raise

def refresh_materialized_views(conn):
    """Refresh materialized views"""
    cursor = conn.cursor()
    
    try:
        logger.info("🔄 Refreshing materialized views...")
        cursor.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY stock_view_materialized")
        logger.info("✅ Refreshed stock_view_materialized")
        
        cursor.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY priority_items_materialized")
        logger.info("✅ Refreshed priority_items_materialized")
        
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error refreshing materialized views: {e}")
        # Try without CONCURRENTLY if it fails
        try:
            cursor.execute("REFRESH MATERIALIZED VIEW stock_view_materialized")
            cursor.execute("REFRESH MATERIALIZED VIEW priority_items_materialized")
            conn.commit()
            logger.info("✅ Refreshed materialized views (without CONCURRENTLY)")
        except Exception as e2:
            logger.error(f"Error refreshing without CONCURRENTLY: {e2}")
            raise

def main():
    """Main function to create all tables and views"""
    # Check if we're in the right directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    expected_dir = os.path.join(script_dir, '..')
    if not os.path.exists(os.path.join(expected_dir, 'app', 'config.py')):
        logger.error(f"❌ Script must be run from web_app directory")
        logger.error(f"   Current script location: {script_dir}")
        logger.error(f"   Expected web_app directory: {expected_dir}")
        logger.error(f"   Please run: cd C:\\PharmaStockApp\\web_app")
        logger.error(f"   Then run: python scripts/create_supabase_tables.py")
        return
    
    if not settings.DATABASE_URL:
        logger.error("❌ DATABASE_URL not set in environment variables")
        logger.error("   Set it in Render: Environment → DATABASE_URL")
        logger.error("   Or set it locally: $env:DATABASE_URL='your_connection_string'")
        return
    
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        logger.info("✅ Connected to Supabase PostgreSQL")
        
        # Create tables
        create_users_table(conn)
        create_credentials_table(conn)
        
        # Create materialized views
        create_stock_view_materialized_view(conn)
        create_priority_items_materialized_view(conn)
        
        # Refresh views
        refresh_materialized_views(conn)
        
        logger.info("✅ All tables and views created successfully!")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise

if __name__ == "__main__":
    main()

