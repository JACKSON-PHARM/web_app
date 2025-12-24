"""
Load Inventory_Analysis.csv into Supabase PostgreSQL
Uses PostgreSQL COPY command for fast, reliable bulk loading
"""
import os
import sys
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from io import StringIO
from urllib.parse import urlparse
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_inventory_analysis(connection_string: str, csv_path: str):
    """Load Inventory_Analysis.csv into Supabase using COPY command"""
    
    if not os.path.exists(csv_path):
        logger.error(f"❌ CSV file not found: {csv_path}")
        return False
    
    conn = None
    try:
        # Connect to Supabase
        logger.info("🔌 Connecting to Supabase...")
        conn = psycopg2.connect(connection_string)
        conn.autocommit = False
        cursor = conn.cursor()
        
        logger.info(f"📊 Reading Inventory_Analysis.csv from: {csv_path}")
        
        # Detect encoding
        file_encoding = 'utf-8'
        try:
            sample_df = pd.read_csv(csv_path, nrows=100, encoding='utf-8')
        except UnicodeDecodeError:
            logger.info("   UTF-8 encoding failed, trying latin-1...")
            file_encoding = 'latin-1'
            sample_df = pd.read_csv(csv_path, nrows=100, encoding='latin-1')
        
        logger.info(f"   Detected columns: {list(sample_df.columns)}")
        logger.info(f"   Using encoding: {file_encoding}")
        
        # Get total row count
        try:
            total_rows = sum(1 for _ in open(csv_path, 'r', encoding=file_encoding)) - 1
            logger.info(f"   Total rows: {total_rows:,}")
        except:
            total_rows = None
        
        # Create NEW table with different name to avoid timeout issues
        new_table_name = "inventory_analysis_new"
        old_table_name = "inventory_analysis"
        
        logger.info(f"📋 Creating new table: {new_table_name}...")
        cursor.execute(f"""
            DROP TABLE IF EXISTS {new_table_name} CASCADE;
        """)
        conn.commit()
        
        cursor.execute(f"""
            CREATE TABLE {new_table_name} (
                id SERIAL PRIMARY KEY,
                company_name TEXT NOT NULL,
                branch_name TEXT NOT NULL,
                item_code TEXT NOT NULL,
                item_name TEXT,
                total_pieces_sold REAL DEFAULT 0,
                total_sales_value REAL DEFAULT 0,
                sale_days_nosun INTEGER DEFAULT 0,
                base_amc REAL DEFAULT 0,
                adjusted_amc REAL DEFAULT 0,
                days_since_first_sale INTEGER DEFAULT 0,
                days_since_last_sale INTEGER DEFAULT 0,
                stock_days_nosun INTEGER DEFAULT 0,
                snapshot_days_nosun INTEGER DEFAULT 0,
                stock_availability_pct REAL DEFAULT 0,
                abc_class TEXT,
                abc_priority REAL DEFAULT 0,
                customer_appeal REAL DEFAULT 0,
                modal_units_sold INTEGER DEFAULT 0,
                last_stock_level INTEGER DEFAULT 0,
                ideal_stock_pieces REAL DEFAULT 0,
                stock_recommendation TEXT,
                loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        logger.info(f"   ✅ Created new table: {new_table_name}")
        
        # Ensure old table exists (for app compatibility)
        logger.info(f"📋 Ensuring {old_table_name} table exists...")
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {old_table_name} (
                id SERIAL PRIMARY KEY,
                company_name TEXT NOT NULL,
                branch_name TEXT NOT NULL,
                item_code TEXT NOT NULL,
                item_name TEXT,
                total_pieces_sold REAL DEFAULT 0,
                total_sales_value REAL DEFAULT 0,
                sale_days_nosun INTEGER DEFAULT 0,
                base_amc REAL DEFAULT 0,
                adjusted_amc REAL DEFAULT 0,
                days_since_first_sale INTEGER DEFAULT 0,
                days_since_last_sale INTEGER DEFAULT 0,
                stock_days_nosun INTEGER DEFAULT 0,
                snapshot_days_nosun INTEGER DEFAULT 0,
                stock_availability_pct REAL DEFAULT 0,
                abc_class TEXT,
                abc_priority REAL DEFAULT 0,
                customer_appeal REAL DEFAULT 0,
                modal_units_sold INTEGER DEFAULT 0,
                last_stock_level INTEGER DEFAULT 0,
                ideal_stock_pieces REAL DEFAULT 0,
                stock_recommendation TEXT,
                loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        logger.info(f"   ✅ Old table ready (will be replaced later)")
        
        # Read CSV in chunks and prepare for COPY
        logger.info("📥 Processing CSV and preparing for bulk load...")
        
        columns = [
            'company_name', 'branch_name', 'item_code', 'item_name',
            'total_pieces_sold', 'total_sales_value', 'sale_days_nosun',
            'base_amc', 'adjusted_amc', 'days_since_first_sale',
            'days_since_last_sale', 'stock_days_nosun', 'snapshot_days_nosun',
            'stock_availability_pct', 'abc_class', 'abc_priority',
            'customer_appeal', 'modal_units_sold', 'last_stock_level',
            'ideal_stock_pieces', 'stock_recommendation'
        ]
        
        # Process in chunks and use COPY for bulk insert
        chunk_size = 10000  # Process 10k rows at a time
        chunk_number = 0
        total_inserted = 0
        
        chunk_reader = pd.read_csv(csv_path, chunksize=chunk_size, low_memory=False, encoding=file_encoding)
        
        for chunk_df in chunk_reader:
            chunk_number += 1
            logger.info(f"\n📦 Processing chunk {chunk_number} ({len(chunk_df):,} rows)...")
            
            # Ensure all columns exist
            for col in columns:
                if col not in chunk_df.columns:
                    chunk_df[col] = None
            
            # Remove duplicates within chunk (keep last)
            initial_count = len(chunk_df)
            chunk_df = chunk_df.drop_duplicates(subset=['company_name', 'branch_name', 'item_code'], keep='last')
            if len(chunk_df) < initial_count:
                logger.info(f"   Removed {initial_count - len(chunk_df):,} duplicates within chunk")
            
            # Prepare data for COPY - convert to CSV format in memory
            # Only include the columns we need, in the right order
            chunk_df_subset = chunk_df[columns].copy()
            
            # Replace NaN with empty string for COPY command
            chunk_df_subset = chunk_df_subset.fillna('')
            
            # Convert to CSV string in memory
            csv_buffer = StringIO()
            chunk_df_subset.to_csv(csv_buffer, index=False, header=False, sep='\t', na_rep='')
            csv_buffer.seek(0)
            
            # Use COPY FROM for fast bulk insert into NEW table
            try:
                cursor.copy_from(
                    csv_buffer,
                    new_table_name,
                    columns=columns,
                    sep='\t',
                    null=''
                )
                conn.commit()
                total_inserted += len(chunk_df)
                
                if total_inserted % 5000 == 0:
                    progress_pct = f"({100*total_inserted//total_rows}%)" if total_rows else ""
                    logger.info(f"   ✅ Inserted {total_inserted:,} rows {progress_pct}...")
            except Exception as e:
                logger.error(f"   ❌ COPY failed for chunk {chunk_number}: {e}")
                conn.rollback()
                
                # Fallback to execute_values if COPY fails
                logger.info(f"   Trying alternative method (execute_values)...")
                try:
                    # Prepare data as list of tuples
                    data_tuples = []
                    for _, row in chunk_df.iterrows():
                        values = [row.get(col) for col in columns]
                        values = [None if pd.isna(v) else v for v in values]
                        data_tuples.append(tuple(values))
                    
                    # Use execute_values for bulk insert into NEW table
                    column_names = ', '.join([f'"{col}"' for col in columns])
                    placeholders = ', '.join(['%s'] * len(columns))
                    insert_sql = f"""
                        INSERT INTO {new_table_name} ({column_names})
                        VALUES ({placeholders})
                    """
                    
                    execute_values(cursor, insert_sql, data_tuples, page_size=1000)
                    conn.commit()
                    total_inserted += len(chunk_df)
                    logger.info(f"   ✅ Inserted {len(chunk_df):,} rows using execute_values")
                except Exception as e2:
                    logger.error(f"   ❌ Alternative method also failed: {e2}")
                    conn.rollback()
                    # Try row by row as last resort
                    logger.info(f"   Trying row-by-row insert...")
                    inserted_in_chunk = 0
                    for _, row in chunk_df.iterrows():
                        try:
                            values = [row.get(col) for col in columns]
                            values = [None if pd.isna(v) else v for v in values]
                            cursor.execute(insert_sql, values)
                            conn.commit()
                            inserted_in_chunk += 1
                        except Exception as e3:
                            conn.rollback()
                            continue
                    total_inserted += inserted_in_chunk
                    logger.info(f"   ✅ Inserted {inserted_in_chunk:,} rows row-by-row")
            
            logger.info(f"   ✅ Completed chunk {chunk_number}: {total_inserted:,} total rows inserted")
        
        logger.info(f"\n✅ Data loading complete!")
        logger.info(f"   Total inserted: {total_inserted:,}")
        
        # Clean up duplicates in NEW table (keep most recent based on id)
        logger.info("\n🧹 Cleaning up remaining duplicates in new table...")
        try:
            cursor.execute(f"""
                DELETE FROM {new_table_name} a
                USING {new_table_name} b
                WHERE a.id < b.id
                AND a.company_name = b.company_name
                AND a.branch_name = b.branch_name
                AND a.item_code = b.item_code;
            """)
            deleted = cursor.rowcount
            conn.commit()
            logger.info(f"   ✅ Removed {deleted:,} duplicate rows")
        except Exception as e:
            logger.warning(f"   ⚠️ Could not clean duplicates: {e}")
            conn.rollback()
        
        # Verify data in NEW table
        cursor.execute(f"SELECT COUNT(*) FROM {new_table_name}")
        result = cursor.fetchone()
        count = result[0] if result else 0
        logger.info(f"\n✅ Verified: {count:,} rows in {new_table_name} table")
        
        # Add unique constraint to NEW table
        logger.info("\n📋 Adding unique constraint to new table...")
        try:
            cursor.execute(f"""
                CREATE UNIQUE INDEX idx_{new_table_name}_unique 
                ON {new_table_name}(company_name, branch_name, item_code);
            """)
            conn.commit()
            logger.info("   ✅ Added unique constraint")
        except Exception as e:
            logger.warning(f"   ⚠️ Could not add unique constraint: {e}")
            conn.rollback()
        
        # Create indexes on NEW table
        logger.info("\n📋 Creating indexes on new table...")
        indexes_created = 0
        
        index_queries = [
            (f"idx_{new_table_name}_branch", f"CREATE INDEX IF NOT EXISTS idx_{new_table_name}_branch ON {new_table_name}(company_name, branch_name);"),
            (f"idx_{new_table_name}_item", f"CREATE INDEX IF NOT EXISTS idx_{new_table_name}_item ON {new_table_name}(item_code);"),
            (f"idx_{new_table_name}_abc", f"CREATE INDEX IF NOT EXISTS idx_{new_table_name}_abc ON {new_table_name}(abc_class);")
        ]
        
        for idx_name, idx_query in index_queries:
            try:
                cursor.execute(idx_query)
                conn.commit()
                indexes_created += 1
                logger.info(f"   ✅ Created {idx_name}")
            except Exception as e:
                logger.warning(f"   ⚠️ Could not create {idx_name}: {e}")
                conn.rollback()
        
        logger.info(f"✅ Index creation complete ({indexes_created}/3 indexes created)")
        
        # Show branch summary from NEW table
        try:
            cursor.execute(f"""
                SELECT company_name, branch_name, COUNT(*) as item_count
                FROM {new_table_name}
                GROUP BY company_name, branch_name
                ORDER BY company_name, branch_name
                LIMIT 50
            """)
            branches = cursor.fetchall()
            logger.info(f"\n📊 Sample branches found in {new_table_name} (showing first 50):")
            for company, branch, count in branches:
                logger.info(f"   - {company} / {branch}: {count:,} items")
        except Exception as e:
            logger.warning(f"Could not show branch summary: {e}")
        
        # Swap tables: Drop old table and rename new one
        logger.info("\n🔄 Swapping tables (replacing old with new)...")
        try:
            # Drop old table (this might timeout, but we'll try)
            logger.info(f"   Attempting to drop old table: {old_table_name}...")
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {old_table_name} CASCADE;")
                conn.commit()
                logger.info(f"   ✅ Dropped old table")
            except Exception as e:
                logger.warning(f"   ⚠️ Could not drop old table (may timeout): {e}")
                logger.info(f"   Will rename it to backup and continue...")
                conn.rollback()
                # Rename old table to backup instead
                try:
                    backup_name = f"{old_table_name}_backup_{int(datetime.now().timestamp())}"
                    cursor.execute(f"ALTER TABLE IF EXISTS {old_table_name} RENAME TO {backup_name};")
                    conn.commit()
                    logger.info(f"   ✅ Renamed old table to: {backup_name}")
                    logger.info(f"   💡 You can delete {backup_name} later when convenient")
                except Exception as e2:
                    logger.warning(f"   ⚠️ Could not rename old table: {e2}")
                    conn.rollback()
            
            # Rename new table to original name
            logger.info(f"   Renaming {new_table_name} to {old_table_name}...")
            cursor.execute(f"ALTER TABLE {new_table_name} RENAME TO {old_table_name};")
            conn.commit()
            logger.info(f"   ✅ Successfully renamed {new_table_name} to {old_table_name}")
            
            # Rename indexes to match
            try:
                cursor.execute(f"ALTER INDEX IF EXISTS idx_{new_table_name}_unique RENAME TO idx_inventory_analysis_unique;")
                cursor.execute(f"ALTER INDEX IF EXISTS idx_{new_table_name}_branch RENAME TO idx_inventory_analysis_branch;")
                cursor.execute(f"ALTER INDEX IF EXISTS idx_{new_table_name}_item RENAME TO idx_inventory_analysis_item;")
                cursor.execute(f"ALTER INDEX IF EXISTS idx_{new_table_name}_abc RENAME TO idx_inventory_analysis_abc;")
                conn.commit()
                logger.info(f"   ✅ Renamed indexes")
            except Exception as e:
                logger.warning(f"   ⚠️ Could not rename indexes: {e}")
                conn.rollback()
            
        except Exception as e:
            logger.error(f"   ❌ Error swapping tables: {e}")
            logger.warning(f"   ⚠️ New table is available as: {new_table_name}")
            logger.warning(f"   ⚠️ You may need to manually rename it or update app to use {new_table_name}")
            conn.rollback()
        
        cursor.close()
        conn.close()
        
        logger.info("\n" + "="*60)
        logger.info("✅ SUCCESS: Inventory analysis loaded successfully!")
        logger.info("="*60)
        return True
        
    except Exception as e:
        logger.error(f"❌ Error loading inventory analysis: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if conn:
            try:
                conn.rollback()
                cursor.close()
                conn.close()
            except:
                pass
        return False

if __name__ == "__main__":
    # Try to get connection string from config if not provided
    connection_string = None
    
    if len(sys.argv) >= 2:
        connection_string = sys.argv[1]
    else:
        # Try to load from app config
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            sys.path.insert(0, os.path.join(script_dir, ".."))
            from app.config import settings
            if settings.DATABASE_URL:
                connection_string = settings.DATABASE_URL
                print(f"✅ Using DATABASE_URL from app.config")
        except Exception as e:
            logger.warning(f"Could not load from config: {e}")
    
    if not connection_string:
        print("Usage: python load_inventory_analysis_to_supabase.py [connection_string] [csv_path]")
        print("\nIf connection_string is not provided, the script will try to load from app.config")
        print("\nExample:")
        print('  python load_inventory_analysis_to_supabase.py')
        print('  python load_inventory_analysis_to_supabase.py "postgresql://user:pass@host:port/db"')
        print('  python load_inventory_analysis_to_supabase.py "postgresql://user:pass@host:port/db" "path/to/file.csv"')
        sys.exit(1)
    
    # Set UTF-8 encoding for Windows console
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    
    # Default CSV path - use the specified path
    if len(sys.argv) >= 3:
        csv_path = sys.argv[2]
    else:
        # Use the specified path from user
        csv_path = r"D:\DATA ANALYTICS\inventory summaries\Inventory_Analysis - Copy.csv"
        
        # If that doesn't exist, try to find CSV in common locations
        if not os.path.exists(csv_path):
            script_dir = os.path.dirname(os.path.abspath(__file__))
            possible_paths = [
                os.path.join(script_dir, "..", "resources", "templates", "Inventory_Analysis.csv"),
                os.path.join(script_dir, "..", "..", "resources", "templates", "Inventory_Analysis.csv"),
                "resources/templates/Inventory_Analysis.csv",
            ]
            
            csv_path = None
            for path in possible_paths:
                abs_path = os.path.abspath(path)
                if os.path.exists(abs_path):
                    csv_path = abs_path
                    break
            
            if not csv_path:
                print(f"❌ Could not find Inventory_Analysis.csv in any of these locations:")
                print(f"   - D:\\DATA ANALYTICS\\inventory summaries\\Inventory_Analysis - Copy.csv")
                for path in possible_paths:
                    print(f"   - {os.path.abspath(path)}")
                sys.exit(1)
    
    print(f"Using CSV: {csv_path}")
    print(f"Connecting to Supabase...")
    
    success = load_inventory_analysis(connection_string, csv_path)
    
    if success:
        print("\n" + "="*60)
        print("SUCCESS: Inventory analysis loaded successfully!")
        print("SUCCESS: Branches, ABC classes, AMC, and other data are now available in Supabase")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("ERROR: Failed to load inventory analysis")
        print("="*60)
        sys.exit(1)
