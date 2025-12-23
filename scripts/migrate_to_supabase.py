"""
Migrate SQLite database to Supabase PostgreSQL
"""
import sqlite3
import psycopg2
from psycopg2.extras import execute_values
import os
import logging
from typing import Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Tables to migrate (in order due to foreign keys)
TABLES_TO_MIGRATE = [
    'items',  # Master data first
    'current_stock',
    'stock_data',
    'purchase_orders',
    'branch_orders',
    'supplier_invoices',
    'inventory_analysis',  # If exists
]

def get_sqlite_schema(cursor, table_name: str) -> List[Dict]:
    """Get column info from SQLite table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = []
    for row in cursor.fetchall():
        columns.append({
            'cid': row[0],
            'name': row[1],
            'type': row[2],
            'notnull': row[3],
            'default': row[4],
            'pk': row[5]
        })
    return columns

def sqlite_to_postgres_type(sqlite_type: str) -> str:
    """Convert SQLite types to PostgreSQL types"""
    sqlite_type = sqlite_type.upper()
    
    type_map = {
        'INTEGER': 'INTEGER',
        'REAL': 'REAL',
        'TEXT': 'TEXT',
        'BLOB': 'BYTEA',
        'NUMERIC': 'NUMERIC',
        'DATE': 'DATE',
        'DATETIME': 'TIMESTAMP',
        'TIMESTAMP': 'TIMESTAMP',
    }
    
    # Handle common variations
    if 'INT' in sqlite_type:
        return 'INTEGER'
    elif 'CHAR' in sqlite_type or 'TEXT' in sqlite_type or 'VARCHAR' in sqlite_type:
        return 'TEXT'
    elif 'REAL' in sqlite_type or 'FLOAT' in sqlite_type or 'DOUBLE' in sqlite_type:
        return 'REAL'
    elif 'DATE' in sqlite_type or 'TIME' in sqlite_type:
        return 'TIMESTAMP'
    elif 'BOOL' in sqlite_type:
        return 'BOOLEAN'
    else:
        return 'TEXT'  # Default

def create_postgres_table(pg_cursor, table_name: str, columns: List[Dict]):
    """Create PostgreSQL table from SQLite schema"""
    col_defs = []
    primary_keys = []
    
    for col in columns:
        col_name = col['name']
        col_type = sqlite_to_postgres_type(col['type'])
        col_def = f'"{col_name}" {col_type}'
        
        if col['notnull']:
            col_def += ' NOT NULL'
        
        if col['default']:
            col_def += f" DEFAULT {col['default']}"
        
        col_defs.append(col_def)
        
        if col['pk']:
            primary_keys.append(f'"{col_name}"')
    
    # Create table
    create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" (\n'
    create_sql += ',\n'.join(col_defs)
    
    if primary_keys:
        create_sql += f',\nPRIMARY KEY ({", ".join(primary_keys)})'
    
    create_sql += '\n);'
    
    logger.info(f"Creating table {table_name}...")
    pg_cursor.execute(create_sql)
    
    # Create indexes
    if table_name == 'purchase_orders':
        pg_cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{table_name}_date ON "{table_name}"(document_date DESC);')
    elif table_name == 'branch_orders':
        pg_cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{table_name}_date ON "{table_name}"(document_date DESC);')
    elif table_name == 'supplier_invoices':
        pg_cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{table_name}_date ON "{table_name}"(invoice_date DESC);')
    elif table_name == 'current_stock':
        pg_cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{table_name}_branch ON "{table_name}"(branch, company, item_code);')

def migrate_table(sqlite_cursor, pg_cursor, table_name: str, batch_size: int = 1000):
    """Migrate data from SQLite to PostgreSQL"""
    logger.info(f"Migrating {table_name}...")
    
    # Get all data
    sqlite_cursor.execute(f'SELECT * FROM {table_name}')
    columns = [desc[0] for desc in sqlite_cursor.description]
    
    # Get column count
    sqlite_cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
    total_rows = sqlite_cursor.fetchone()[0]
    
    if total_rows == 0:
        logger.info(f"  Table {table_name} is empty, skipping")
        return
    
    logger.info(f"  Migrating {total_rows:,} rows...")
    
    # Migrate in batches
    offset = 0
    migrated = 0
    
    while offset < total_rows:
        sqlite_cursor.execute(f'SELECT * FROM {table_name} LIMIT ? OFFSET ?', (batch_size, offset))
        rows = sqlite_cursor.fetchall()
        
        if not rows:
            break
        
        # Prepare insert statement
        col_names = ', '.join([f'"{col}"' for col in columns])
        placeholders = ', '.join(['%s'] * len(columns))
        insert_sql = f'INSERT INTO "{table_name}" ({col_names}) VALUES %s ON CONFLICT DO NOTHING'
        
        # Insert batch
        execute_values(pg_cursor, insert_sql, rows)
        
        migrated += len(rows)
        offset += batch_size
        
        if migrated % 10000 == 0:
            logger.info(f"  Migrated {migrated:,}/{total_rows:,} rows...")
    
    logger.info(f"✅ Migrated {migrated:,} rows from {table_name}")

def migrate_database(sqlite_path: str, supabase_url: str):
    """
    Migrate SQLite database to Supabase PostgreSQL
    
    Args:
        sqlite_path: Path to SQLite database
        supabase_url: PostgreSQL connection string from Supabase
    """
    if not os.path.exists(sqlite_path):
        logger.error(f"SQLite database not found: {sqlite_path}")
        return False
    
    # Connect to SQLite
    logger.info(f"📂 Connecting to SQLite: {sqlite_path}")
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_cursor = sqlite_conn.cursor()
    
    # Connect to PostgreSQL
    logger.info("🔌 Connecting to Supabase PostgreSQL...")
    pg_conn = psycopg2.connect(supabase_url)
    pg_cursor = pg_conn.cursor()
    
    try:
        # Get list of tables
        sqlite_cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        all_tables = [row[0] for row in sqlite_cursor.fetchall()]
        
        # Filter to tables we want to migrate
        tables_to_migrate = [t for t in TABLES_TO_MIGRATE if t in all_tables]
        
        logger.info(f"📊 Found {len(tables_to_migrate)} tables to migrate")
        
        # Create tables and migrate data
        for table_name in tables_to_migrate:
            try:
                # Get schema
                columns = get_sqlite_schema(sqlite_cursor, table_name)
                
                # Create PostgreSQL table
                create_postgres_table(pg_cursor, table_name, columns)
                pg_conn.commit()
                
                # Migrate data
                migrate_table(sqlite_cursor, pg_cursor, table_name)
                pg_conn.commit()
                
            except Exception as e:
                logger.error(f"❌ Error migrating {table_name}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                pg_conn.rollback()
        
        logger.info("✅ Migration complete!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        pg_conn.rollback()
        return False
        
    finally:
        sqlite_conn.close()
        pg_conn.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python migrate_to_supabase.py <sqlite_path> <supabase_url>")
        print("\nExample:")
        print("  python migrate_to_supabase.py cache/pharma_stock.db 'postgresql://user:pass@host:5432/dbname'")
        sys.exit(1)
    
    sqlite_path = sys.argv[1]
    supabase_url = sys.argv[2]
    
    success = migrate_database(sqlite_path, supabase_url)
    
    if success:
        logger.info("\n🎉 Migration successful! Update your app config to use Supabase.")
    else:
        logger.error("\n❌ Migration failed. Check errors above.")
        sys.exit(1)

