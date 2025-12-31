"""
PostgreSQL Database Manager for Supabase
Replaces SQLite database manager with PostgreSQL support
"""
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from psycopg2.pool import ThreadedConnectionPool
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import os
import socket

logger = logging.getLogger(__name__)

class PostgresDatabaseManager:
    """
    PostgreSQL database manager for Supabase
    Provides same interface as SQLite DatabaseManager but uses PostgreSQL
    """
    
    def __init__(self, connection_string: str):
        """
        Initialize PostgreSQL database manager
        
        Args:
            connection_string: PostgreSQL connection string (e.g., postgresql://user:pass@host:port/db)
        """
        self.connection_string = connection_string
        # db_path is set via property setter (defined below)
        self._db_path_value = "Supabase PostgreSQL"  # Set internal value first
        self.setup_logging()
        
        # Check if using direct connection (will fail with IPv6 on free tier)
        # CRITICAL: Render + Supabase free tier requires pooler connection (IPv4 compatible)
        if 'db.' in connection_string and '.supabase.co' in connection_string and 'pooler' not in connection_string:
            logger.error("❌ DETECTED: You're using Supabase DIRECT connection string")
            logger.error("   Direct connections (db.xxx.supabase.co) only support IPv6")
            logger.error("   Supabase FREE TIER doesn't support IPv6!")
            logger.error("")
            logger.error("   🔧 SOLUTION: Use POOLER connection string instead")
            logger.error("   1. Go to: https://supabase.com/dashboard → Your Project")
            logger.error("   2. Settings → Database")
            logger.error("   3. Scroll to 'Connection pooling' section")
            logger.error("   4. Click 'Session mode' or 'Transaction mode'")
            logger.error("   5. Copy the connection string (starts with pooler.supabase.com)")
            logger.error("   6. Update DATABASE_URL in Render with that pooler connection string")
            logger.error("")
            logger.error("   Current connection string uses: db.xxx.supabase.co (WRONG - IPv6 only)")
            logger.error("   Need connection string with: pooler.supabase.com (CORRECT - IPv4 supported)")
            raise ValueError(
                "Supabase direct connection (db.xxx.supabase.co) doesn't support IPv4. "
                "You MUST use the pooler connection string from Supabase Dashboard. "
                "Go to: Settings → Database → Connection pooling → Copy pooler connection string"
            )
        
        # Create connection pool
        # IMPORTANT: For Supabase free tier (no IPv6 support), you MUST use the pooler connection string
        # Get it from: Supabase Dashboard → Settings → Database → Connection pooling → Copy connection string
        # Do NOT use the direct connection string (db.xxx.supabase.co) - it only has IPv6
        try:
            # Increase pool size to handle concurrent requests
            # Min 2, Max 20 connections (Supabase free tier allows up to 60 connections)
            self.pool = ThreadedConnectionPool(2, 20, connection_string)
            logger.info("✅ PostgreSQL connection pool created")
            self._init_database()
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Failed to create PostgreSQL connection pool: {e}")
            
            # Provide helpful error message for common issues
            if "Tenant or user not found" in error_msg:
                logger.error("💡 ERROR: 'Tenant or user not found'")
                logger.error("   This means the connection string username format is incorrect.")
                logger.error("   SOLUTION: Get the EXACT pooler connection string from Supabase Dashboard:")
                logger.error("   1. Go to Supabase Dashboard → Your Project")
                logger.error("   2. Settings → Database")
                logger.error("   3. Scroll to 'Connection pooling' section")
                logger.error("   4. Select 'Session mode' or 'Transaction mode'")
                logger.error("   5. Copy the connection string EXACTLY as shown")
                logger.error("   6. Update DATABASE_URL in Render with that exact string")
            elif "Network is unreachable" in error_msg or "IPv6" in error_msg or "2a05:" in error_msg:
                logger.error("💡 ERROR: IPv6 connection issue detected")
                logger.error("   Supabase free tier doesn't support IPv6.")
                logger.error("   Your connection string is still using direct connection (db.xxx.supabase.co)")
                logger.error("")
                logger.error("   🔧 SOLUTION: Update DATABASE_URL in Render with pooler connection string")
                logger.error("   1. Go to Supabase Dashboard → Settings → Database → Connection pooling")
                logger.error("   2. Copy the pooler connection string (has 'pooler.supabase.com' in it)")
                logger.error("   3. Go to Render Dashboard → Your Service → Environment")
                logger.error("   4. Edit DATABASE_URL and paste the pooler connection string")
                logger.error("   5. Save - Render will restart automatically")
            
            raise
    
    def _force_ipv4_connection(self, connection_string: str) -> str:
        """
        Force IPv4 connection for Supabase (free tier doesn't support IPv6)
        Converts Supabase direct connection to pooler connection which supports IPv4
        """
        try:
            # Parse connection string
            if connection_string.startswith('postgresql://'):
                # Extract components from connection string
                # Format: postgresql://user:pass@host:port/db
                parts = connection_string.split('@')
                if len(parts) == 2:
                    auth_part = parts[0]  # postgresql://user:pass
                    host_db_part = parts[1]  # host:port/db
                    
                    # Extract hostname, port, and database
                    if '/' in host_db_part:
                        host_port, db_part = host_db_part.split('/', 1)
                        if ':' in host_port:
                            hostname, port = host_port.rsplit(':', 1)
                        else:
                            hostname = host_port
                            port = '5432'
                    else:
                        hostname = host_db_part
                        port = '5432'
                        db_part = 'postgres'
                    
                    # Check if this is a Supabase direct connection (db.xxx.supabase.co)
                    if 'db.' in hostname and '.supabase.co' in hostname:
                        # Convert to pooler connection for IPv4 support
                        # Extract project ref from hostname: db.REF.supabase.co
                        project_ref = hostname.replace('db.', '').replace('.supabase.co', '')
                        
                        # Use pooler hostname (supports IPv4)
                        # Try different pooler hostnames based on region
                        pooler_hostnames = [
                            f'aws-0-us-east-1.pooler.supabase.com',  # US East
                            f'aws-0-us-west-1.pooler.supabase.com',  # US West
                            f'aws-0-eu-west-1.pooler.supabase.com',  # EU West
                            f'{project_ref}.pooler.supabase.com',     # Project-specific
                        ]
                        
                        # Use port 6543 for connection pooling
                        pooler_port = '6543'
                        
                        # Try to construct pooler connection string
                        # Format: postgresql://postgres.REF:PASSWORD@pooler.supabase.com:6543/postgres
                        # Extract user and password from auth_part
                        auth_clean = auth_part.replace('postgresql://', '')
                        if ':' in auth_clean:
                            user, password = auth_clean.split(':', 1)
                            # For pooler, user format is: postgres.REF
                            pooler_user = f'postgres.{project_ref}'
                            
                            # Build pooler connection string
                            pooler_connection = f'postgresql://{pooler_user}:{password}@{pooler_hostnames[0]}:{pooler_port}/{db_part}'
                            
                            logger.info(f"Converting Supabase direct connection to pooler connection")
                            logger.info(f"Original: {hostname}:{port}")
                            logger.info(f"Pooler: {pooler_hostnames[0]}:{pooler_port}")
                            
                            return pooler_connection
                    
                    # If not Supabase or conversion failed, try IPv4 resolution
                    try:
                        # Force IPv4 by using socket.AF_INET
                        ipv4_addresses = socket.getaddrinfo(hostname, int(port), socket.AF_INET, socket.SOCK_STREAM)
                        if ipv4_addresses:
                            ipv4_address = ipv4_addresses[0][4][0]
                            logger.info(f"Resolved {hostname} to IPv4: {ipv4_address}")
                            connection_string_ipv4 = connection_string.replace(hostname, ipv4_address)
                            return connection_string_ipv4
                    except (socket.gaierror, ValueError) as e:
                        logger.warning(f"Could not resolve {hostname} to IPv4: {e}")
                        return connection_string
                else:
                    logger.warning("Could not parse connection string for IPv4 conversion")
                    return connection_string
            else:
                # Not a postgresql:// URL, return as-is
                return connection_string
        except Exception as e:
            logger.warning(f"Error forcing IPv4 connection: {e}, using original connection string")
            import traceback
            logger.warning(traceback.format_exc())
            return connection_string
    
    def setup_logging(self):
        """Setup logging for database operations"""
        self.logger = logging.getLogger("PostgresDatabaseManager")
    
    def _init_database(self):
        """Initialize database - ensure tables exist"""
        try:
            conn = self.pool.getconn()
            cursor = conn.cursor()
            
            # Check if tables exist
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            # Create tables if they don't exist (migration script should have done this)
            if 'current_stock' not in existing_tables:
                logger.warning("⚠️ Tables not found - run migration script first!")
            
            conn.commit()
            cursor.close()
            self.pool.putconn(conn)
            logger.info("✅ PostgreSQL database initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize database: {e}")
            if conn:
                self.pool.putconn(conn)
            raise
    
    def get_connection(self):
        """Get a database connection from pool"""
        return self.pool.getconn()
    
    def put_connection(self, conn):
        """Return connection to pool"""
        self.pool.putconn(conn)
    
    # ============================================================
    # REFRESH LOCK METHODS (for concurrent refresh safety)
    # ============================================================
    
    def acquire_refresh_lock(self, lock_type: str = 'global', timeout_seconds: int = 3600) -> bool:
        """
        Acquire a refresh lock to prevent concurrent refreshes.
        Returns True if lock acquired, False if already locked.
        
        Args:
            lock_type: Type of lock ('global', 'stock', 'orders', etc.)
            timeout_seconds: Lock expiration time (default 1 hour)
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Use PostgreSQL function to acquire lock
            import socket
            locked_by = f"{socket.gethostname()}-{os.getpid()}"
            
            cursor.execute(
                "SELECT acquire_refresh_lock(%s, %s, %s)",
                (lock_type, locked_by, timeout_seconds)
            )
            acquired = cursor.fetchone()[0]
            conn.commit()
            
            if acquired:
                self.logger.info(f"🔒 Acquired refresh lock: {lock_type}")
            else:
                self.logger.warning(f"⚠️ Refresh lock already held: {lock_type}")
            
            return acquired
        except Exception as e:
            self.logger.error(f"❌ Failed to acquire refresh lock: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                cursor.close()
                self.put_connection(conn)
    
    def release_refresh_lock(self, lock_type: str = 'global') -> bool:
        """
        Release a refresh lock.
        Returns True if released, False if not found.
        
        Args:
            lock_type: Type of lock to release
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT release_refresh_lock(%s, NULL)", (lock_type,))
            released = cursor.fetchone()[0]
            conn.commit()
            
            if released:
                self.logger.info(f"🔓 Released refresh lock: {lock_type}")
            else:
                self.logger.warning(f"⚠️ No active lock to release: {lock_type}")
            
            return released
        except Exception as e:
            self.logger.error(f"❌ Failed to release refresh lock: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                cursor.close()
                self.put_connection(conn)
    
    def is_refresh_locked(self, lock_type: str = 'global') -> bool:
        """
        Check if a refresh lock is currently active.
        Returns True if locked, False if available.
        
        Args:
            lock_type: Type of lock to check
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT is_refresh_locked(%s)", (lock_type,))
            is_locked = cursor.fetchone()[0]
            
            return is_locked
        except Exception as e:
            self.logger.error(f"❌ Failed to check refresh lock: {e}")
            return False
        finally:
            if conn:
                cursor.close()
                self.put_connection(conn)
    
    def insert_current_stock(self, stock_data: List[Dict], replace_all: bool = True) -> int:
        """
        Insert current stock data - ATOMIC REPLACEMENT using staging table swap.
        This ensures current_stock is NEVER empty during refresh.
        
        Process:
        1. Insert all new data into current_stock_staging
        2. Once successful, atomically swap staging -> main table
        3. If any step fails, main table remains unchanged
        
        Args:
            stock_data: List of stock records from API
            replace_all: If True (default), replace all existing stock (uses staging swap)
                         If False, append to existing stock
        """
        if not stock_data:
            return 0
        
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Use staging table for atomic replacement
            if replace_all:
                # Step 1: Clear staging table
                cursor.execute("TRUNCATE TABLE current_stock_staging")
                self.logger.info("🧹 Cleared staging table for atomic stock refresh")
                target_table = "current_stock_staging"
            else:
                # Append mode - insert directly into main table
                target_table = "current_stock"
            
            # Get schema from target table (main or staging - they have same structure)
            cursor.execute("""
                SELECT 
                    column_name, 
                    data_type,
                    column_default,
                    is_nullable
                FROM information_schema.columns 
                WHERE table_name = %s 
                AND table_schema = 'public'
                ORDER BY ordinal_position
            """, (target_table,))
            schema_info = cursor.fetchall()
            schema_columns = {row[0]: row[1] for row in schema_info}
            column_defaults = {row[0]: row[2] for row in schema_info}
            column_nullable = {row[0]: row[3] for row in schema_info}
            
            if not schema_columns:
                raise ValueError(f"{target_table} table does not exist or has no columns")
            
            self.logger.info(f"📋 {target_table} table schema: {list(schema_columns.keys())}")
            
            # Get columns from first record and validate against schema
            data_columns = list(stock_data[0].keys())
            self.logger.info(f"📋 Data columns from fetcher: {data_columns}")
            
            # Filter to only include columns that exist in the table
            # IMPORTANT: If a column is in the data, we ALWAYS include it (even if it has a default)
            # We only exclude columns that are NOT in the data but have defaults (auto-generated)
            # This ensures we replace with actual API values, not use database defaults
            valid_columns = []
            excluded_auto_columns = []
            problematic_columns = []
            
            # Include ALL columns that are in both data and table schema
            # We want to insert actual API values, not use database defaults
            for col in data_columns:
                if col in schema_columns:
                    valid_columns.append(col)  # Always include if in data
            
            # Check for table columns that aren't in data
            for col in schema_columns.keys():
                if col not in data_columns:
                    default = column_defaults.get(col)
                    nullable = column_nullable.get(col, 'NO')
                    if default is not None:
                        # Has default, will be auto-generated
                        excluded_auto_columns.append(col)
                        self.logger.debug(f"Table column {col} has default and will be auto-generated: {default}")
                    elif nullable == 'NO':
                        # NOT NULL and no default - this is a problem if we don't provide it
                        problematic_columns.append(col)
                        self.logger.warning(f"⚠️ Column {col} is NOT NULL with no default but not in data - this will cause errors!")
            
            missing_columns = [col for col in data_columns if col not in schema_columns]
            extra_columns = [col for col in schema_columns.keys() if col not in data_columns and col not in excluded_auto_columns and col not in problematic_columns]
            
            if missing_columns:
                self.logger.warning(f"⚠️ Data has columns not in table: {missing_columns}")
            if extra_columns:
                self.logger.info(f"ℹ️ Table has extra columns (will use defaults): {extra_columns}")
            if excluded_auto_columns:
                self.logger.info(f"ℹ️ Excluded table columns with defaults (not in data, auto-generated): {excluded_auto_columns}")
            if problematic_columns:
                self.logger.error(f"❌ Problematic columns (NOT NULL, no default, not in data): {problematic_columns}")
                self.logger.error(f"   These columns need to be fixed in the database schema!")
                # Try to fix the id column if it's the only problematic one
                if problematic_columns == ['id']:
                    self.logger.info("🔧 Attempting to fix 'id' column by making it SERIAL...")
                    try:
                        # Check current id column type
                        cursor.execute("""
                            SELECT data_type, column_default
                            FROM information_schema.columns
                            WHERE table_name = 'current_stock' 
                            AND column_name = 'id'
                            AND table_schema = 'public'
                        """)
                        id_info = cursor.fetchone()
                        if id_info:
                            id_type, id_default = id_info
                            if id_default is None:
                                # Try to convert to SERIAL by creating a sequence and setting default
                                self.logger.info("   Creating sequence for id column...")
                                cursor.execute("""
                                    CREATE SEQUENCE IF NOT EXISTS current_stock_id_seq;
                                    ALTER TABLE current_stock 
                                    ALTER COLUMN id SET DEFAULT nextval('current_stock_id_seq');
                                    SELECT setval('current_stock_id_seq', COALESCE((SELECT MAX(id) FROM current_stock), 1), true);
                                """)
                                conn.commit()
                                self.logger.info("✅ Fixed 'id' column - now has auto-increment default")
                                # Re-fetch column defaults after fix
                                cursor.execute("""
                                    SELECT column_name, column_default
                                    FROM information_schema.columns 
                                    WHERE table_name = 'current_stock' 
                                    AND table_schema = 'public'
                                    AND column_name = 'id'
                                """)
                                new_default = cursor.fetchone()
                                if new_default and new_default[1]:
                                    column_defaults['id'] = new_default[1]
                                    problematic_columns.remove('id')
                                    excluded_auto_columns.append('id')
                                    self.logger.info("   'id' column now excluded from INSERT (auto-generated)")
                            else:
                                self.logger.info(f"   'id' column already has default: {id_default}")
                    except Exception as fix_error:
                        self.logger.error(f"   Failed to fix 'id' column: {fix_error}")
                        conn.rollback()
                        self.logger.error(f"   Please run this SQL manually to fix the schema:")
                        self.logger.error(f"   CREATE SEQUENCE IF NOT EXISTS current_stock_id_seq;")
                        self.logger.error(f"   ALTER TABLE current_stock ALTER COLUMN id SET DEFAULT nextval('current_stock_id_seq');")
                
                if problematic_columns:
                    raise ValueError(f"Cannot insert: columns {problematic_columns} are NOT NULL with no default. Fix the database schema first.")
            
            if not valid_columns:
                raise ValueError("No valid columns found matching table schema")
            
            # Log final column selection
            self.logger.info(f"✅ Will insert into columns: {valid_columns}")
            
            # Build insert statement with only valid columns
            column_names = ', '.join([f'"{col}"' for col in valid_columns])
            placeholders = ', '.join(['%s'] * len(valid_columns))
            
            insert_sql = f"""
                INSERT INTO {target_table} ({column_names}) 
                VALUES ({placeholders})
            """
            
            # Use COPY FROM for maximum performance (fastest bulk insert method)
            # This is 10-100x faster than executemany for large datasets (243k records in seconds, not hours)
            import io
            import csv
            
            # Prepare data as CSV string in memory
            output = io.StringIO()
            writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
            
            for record in stock_data:
                values = [record.get(col) for col in valid_columns]
                # Handle None, empty strings, and NaN
                values = [
                    None if v == '' or (isinstance(v, float) and (v != v)) else v 
                    for v in values
                ]
                writer.writerow(values)
            
            output.seek(0)
            
            # Use COPY FROM for bulk insert (fastest method - can insert 200k+ records in seconds)
            copy_sql = f'COPY {target_table} ({column_names}) FROM STDIN WITH (FORMAT csv)'
            
            try:
                cursor.copy_expert(copy_sql, output)
                count = cursor.rowcount
                
                # If using staging table, atomically swap it with main table
                if replace_all and target_table == "current_stock_staging":
                    # Atomic swap: staging -> main (transaction ensures atomicity)
                    self.logger.info(f"🔄 Swapping staging table to main (atomic operation)...")
                    cursor.execute("TRUNCATE TABLE current_stock")
                    cursor.execute("INSERT INTO current_stock SELECT * FROM current_stock_staging")
                    swap_count = cursor.rowcount
                    self.logger.info(f"✅ Atomically swapped {swap_count:,} records from staging to main table")
                
                conn.commit()
                self.logger.info(f"✅ Inserted {count:,} stock records using COPY (fastest method)")
                return count
            except Exception as copy_error:
                # If COPY fails, fall back to executemany
                conn.rollback()
                self.logger.warning(f"⚠️ COPY failed for current_stock, trying executemany: {copy_error}")
                
                # Prepare all values for batch insert
                all_values = []
                for record in stock_data:
                    values = [record.get(col) for col in valid_columns]
                    values = [None if v == '' or (isinstance(v, float) and (v != v)) else v for v in values]
                    all_values.append(values)
                
                # Use executemany in large chunks (10k at a time for better performance)
                chunk_size = 10000
                count = 0
                failed_count = 0
                
                for chunk_start in range(0, len(all_values), chunk_size):
                    chunk_end = min(chunk_start + chunk_size, len(all_values))
                    chunk = all_values[chunk_start:chunk_end]
                    
                    try:
                        cursor.executemany(insert_sql, chunk)
                        count += len(chunk)
                        if chunk_start % 50000 == 0:
                            self.logger.info(f"  Inserted {count:,} records...")
                    except Exception as chunk_error:
                        self.logger.warning(f"⚠️ Chunk {chunk_start}-{chunk_end} failed: {chunk_error}")
                        # Try individual inserts for this chunk
                        for idx, values in enumerate(chunk):
                            try:
                                cursor.execute(insert_sql, values)
                                count += 1
                            except Exception as record_error:
                                failed_count += 1
                                if failed_count <= 3:
                                    self.logger.debug(f"Failed to insert stock record {chunk_start + idx}: {record_error}")
                
                # If using staging table, atomically swap it with main table
                if replace_all and target_table == "current_stock_staging":
                    # Atomic swap: staging -> main (transaction ensures atomicity)
                    self.logger.info(f"🔄 Swapping staging table to main (atomic operation)...")
                    cursor.execute("TRUNCATE TABLE current_stock")
                    cursor.execute("INSERT INTO current_stock SELECT * FROM current_stock_staging")
                    swap_count = cursor.rowcount
                    self.logger.info(f"✅ Atomically swapped {swap_count:,} records from staging to main table")
                
                conn.commit()
                if failed_count > 0:
                    self.logger.warning(f"⚠️ Inserted {count:,} records into {target_table}, {failed_count} failed")
                else:
                    self.logger.info(f"✅ Inserted {count:,} records into {target_table}")
                return count
            
        except Exception as e:
            self.logger.error(f"❌ Failed to insert current_stock: {e}")
            if conn:
                conn.rollback()
            return 0
        finally:
            if conn:
                cursor.close()
                self.put_connection(conn)
    
    def insert_purchase_orders(self, order_data: List[Dict]) -> int:
        """Insert purchase orders"""
        return self._insert_data("purchase_orders", order_data, replace=False)
    
    def insert_branch_orders(self, order_data: List[Dict]) -> int:
        """Insert branch orders"""
        return self._insert_data("branch_orders", order_data, replace=False)
    
    def insert_supplier_invoices(self, invoice_data: List[Dict]) -> int:
        """Insert supplier invoices"""
        return self._insert_data("supplier_invoices", invoice_data, replace=False)
    
    def insert_goods_received_notes(self, grn_data: List[Dict]) -> int:
        """Insert goods received notes (GRNs)"""
        return self._insert_data("grns", grn_data, replace=False)
    
    def _insert_data(self, table_name: str, data: List[Dict], replace: bool = False) -> int:
        """
        Generic method to insert data into any table using COPY for maximum performance
        COPY is 10-100x faster than executemany for bulk inserts
        """
        if not data:
            return 0
        
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # First, get the actual table schema to ensure we're inserting the right columns
            # Check which columns are auto-generated (PRIMARY KEY, SERIAL, or have defaults)
            cursor.execute("""
                SELECT 
                    c.column_name, 
                    c.data_type,
                    c.column_default,
                    c.is_nullable,
                    CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END as is_primary_key
                FROM information_schema.columns c
                LEFT JOIN (
                    SELECT ku.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage ku
                        ON tc.constraint_name = ku.constraint_name
                    WHERE tc.table_name = %s
                        AND tc.table_schema = 'public'
                        AND tc.constraint_type = 'PRIMARY KEY'
                ) pk ON c.column_name = pk.column_name
                WHERE c.table_name = %s 
                AND c.table_schema = 'public'
                ORDER BY c.ordinal_position
            """, (table_name, table_name))
            
            schema_info = cursor.fetchall()
            schema_columns = {row[0]: row[1] for row in schema_info}
            column_defaults = {row[0]: row[2] for row in schema_info}
            column_nullable = {row[0]: row[3] for row in schema_info}
            column_is_pk = {row[0]: row[4] for row in schema_info}
            
            if not schema_columns:
                raise ValueError(f"{table_name} table does not exist or has no columns")
            
            # Get columns from first record
            data_columns = list(data[0].keys())
            
            # Filter to only include columns that exist in the table AND are not auto-generated
            # Exclude columns that:
            # 1. Are PRIMARY KEY (like id) - always auto-generated
            # 2. Are SERIAL/BIGSERIAL types - always auto-increment
            # 3. Have defaults (auto-generated)
            # 4. Are NOT in data AND are NOT NULL with no default (problematic)
            valid_columns = []
            excluded_auto_columns = []
            
            # First, identify all auto-generated columns (PK, SERIAL, or have defaults)
            for col in schema_columns.keys():
                data_type = schema_columns.get(col, '').upper()
                default = column_defaults.get(col)
                is_pk = column_is_pk.get(col, False)
                nullable = column_nullable.get(col, 'NO')
                
                # Always exclude if:
                # - Is PRIMARY KEY (like id)
                # - Is SERIAL/BIGSERIAL type
                # - Has a default value
                if is_pk or 'SERIAL' in data_type or default is not None:
                    excluded_auto_columns.append(col)
                    self.logger.debug(f"Excluding auto-generated column {col} (type={data_type}, default={default}, pk={is_pk})")
                elif col not in data_columns and nullable == 'NO' and default is None:
                    # NOT NULL, no default, not in data - this is a problem!
                    self.logger.warning(f"⚠️ Column {col} is NOT NULL with no default but not in data - will try to exclude")
                    excluded_auto_columns.append(col)
            
            # Now include only columns that are:
            # 1. In the data
            # 2. In the table schema
            # 3. NOT in excluded_auto_columns
            for col in data_columns:
                if col in schema_columns and col not in excluded_auto_columns:
                    valid_columns.append(col)
            
            if not valid_columns:
                raise ValueError(f"No valid columns found for {table_name} after filtering")
            
            if excluded_auto_columns:
                self.logger.info(f"ℹ️ Excluding auto-generated columns from {table_name}: {excluded_auto_columns}")
            
            # Log detailed schema info for debugging
            self.logger.info(f"📋 {table_name} schema check:")
            self.logger.info(f"   Table columns: {list(schema_columns.keys())}")
            self.logger.info(f"   Data columns: {data_columns}")
            self.logger.info(f"   Excluded (auto-gen): {excluded_auto_columns}")
            self.logger.info(f"   Valid (will insert): {valid_columns}")
            
            # Use only valid columns (excluding auto-generated ones)
            columns = valid_columns
            column_names = ', '.join([f'"{col}"' for col in columns])
            
            # Use COPY FROM for maximum performance (fastest bulk insert method)
            # This is much faster than executemany - can insert 100k+ records in seconds
            import io
            import csv
            
            # Prepare data as CSV string in memory
            output = io.StringIO()
            writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
            
            for record in data:
                values = [record.get(col) for col in columns]
                # Handle None, empty strings, and NaN
                values = [
                    None if v == '' or (isinstance(v, float) and (v != v)) else v 
                    for v in values
                ]
                writer.writerow(values)
            
            output.seek(0)
            
            # Use COPY FROM for bulk insert (fastest method)
            copy_sql = f'COPY "{table_name}" ({column_names}) FROM STDIN WITH (FORMAT csv)'
            
            try:
                cursor.copy_expert(copy_sql, output)
                total_inserted = cursor.rowcount
                conn.commit()
                self.logger.info(f"✅ Inserted {total_inserted:,} records into {table_name} using COPY")
                return total_inserted
            except Exception as copy_error:
                # If COPY fails, use execute_values with ON CONFLICT (more reliable than temp table)
                conn.rollback()
                self.logger.warning(f"⚠️ COPY failed for {table_name}, using execute_values: {copy_error}")
                
                # Get unique constraints for ON CONFLICT handling
                cursor.execute("""
                    SELECT 
                        kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu 
                        ON tc.constraint_name = kcu.constraint_name
                    WHERE tc.table_name = %s 
                        AND tc.table_schema = 'public'
                        AND tc.constraint_type IN ('UNIQUE', 'PRIMARY KEY')
                    ORDER BY kcu.ordinal_position
                """, (table_name,))
                
                unique_cols = [row[0] for row in cursor.fetchall()]
                # Only use unique columns that are in our insert columns (not excluded like 'id')
                conflict_cols = [col for col in unique_cols if col in columns]
                
                # Prepare all values
                all_values = []
                for record in data:
                    values = [record.get(col) for col in columns]
                    # Handle None, empty strings, and NaN
                    values = [
                        None if v == '' or (isinstance(v, float) and (v != v)) else v 
                        for v in values
                    ]
                    all_values.append(tuple(values))
                
                # Build INSERT statement with ON CONFLICT if we have unique constraints
                # execute_values uses %s as placeholder for VALUES
                if conflict_cols:
                    conflict_cols_str = ', '.join([f'"{col}"' for col in conflict_cols])
                    insert_template = f"""
                        INSERT INTO "{table_name}" ({column_names}) 
                        VALUES %s
                        ON CONFLICT ({conflict_cols_str}) DO NOTHING
                    """
                else:
                    insert_template = f'INSERT INTO "{table_name}" ({column_names}) VALUES %s'
                
                # Use execute_values for bulk insert (faster than executemany, more reliable than COPY)
                # Insert in chunks to avoid memory issues
                chunk_size = 5000  # Smaller chunks for better reliability
                total_inserted = 0
                failed_count = 0
                
                for chunk_start in range(0, len(all_values), chunk_size):
                    chunk_end = min(chunk_start + chunk_size, len(all_values))
                    chunk = all_values[chunk_start:chunk_end]
                    
                    try:
                        execute_values(cursor, insert_template, chunk, page_size=chunk_size)
                        total_inserted += len(chunk)
                        if chunk_start % 50000 == 0 or chunk_end >= len(all_values):
                            self.logger.info(f"  Inserted {total_inserted:,}/{len(all_values):,} records into {table_name}...")
                    except Exception as chunk_error:
                        self.logger.warning(f"⚠️ Chunk {chunk_start}-{chunk_end} failed: {chunk_error}")
                        # Try individual inserts for this chunk to identify problematic records
                        placeholders = ', '.join(['%s'] * len(columns))
                        single_insert_sql = insert_template.replace('VALUES %s', f'VALUES ({placeholders})')
                        for idx, values in enumerate(chunk):
                            try:
                                cursor.execute(single_insert_sql, values)
                                total_inserted += 1
                            except Exception as record_error:
                                failed_count += 1
                                if failed_count <= 5:  # Only log first few failures
                                    self.logger.debug(f"Failed to insert record {chunk_start + idx}: {record_error}")
                
                conn.commit()
                if failed_count > 0:
                    self.logger.warning(f"⚠️ Inserted {total_inserted:,} records into {table_name}, {failed_count} skipped")
                else:
                    self.logger.info(f"✅ Inserted {total_inserted:,} records into {table_name} using execute_values")
                return total_inserted
            
        except Exception as e:
            self.logger.error(f"❌ Failed to insert data into {table_name}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            return 0
        finally:
            if conn:
                try:
                    cursor.close()
                except:
                    pass
                try:
                    self.put_connection(conn)
                except:
                    pass
    
    def _get_unique_columns(self, table_name: str) -> List[str]:
        """Get unique constraint columns for a table"""
        # Common unique constraints
        unique_constraints = {
            'current_stock': ['branch', 'item_code', 'company'],
            'purchase_orders': ['company', 'branch', 'document_number', 'item_code'],
            'branch_orders': ['company', 'source_branch', 'document_number', 'item_code'],
            'supplier_invoices': ['company', 'branch', 'document_number', 'item_code'],
            'grns': ['company', 'branch', 'document_number', 'item_code'],
        }
        return unique_constraints.get(table_name, [])
    
    def is_document_processed(self, script_name: str, company: str, document_type: str,
                             document_number: str, document_date: str) -> bool:
        """
        Check if a document is already processed in the database
        
        Args:
            script_name: Name of the script/fetcher (not used, kept for compatibility)
            company: Company name
            document_type: Type of document (GRN, PURCHASE, BRANCH, SUPPLIER_INVOICE)
            document_number: Document number
            document_date: Document date (YYYY-MM-DD format)
        
        Returns:
            True if document exists, False otherwise
        """
        # Map document types to table names
        table_mapping = {
            'GRN': 'grns',
            'PURCHASE': 'purchase_orders',
            'BRANCH': 'branch_orders',
            'SUPPLIER_INVOICE': 'supplier_invoices',
        }
        
        table_name = table_mapping.get(document_type.upper())
        if not table_name:
            self.logger.warning(f"⚠️ Unknown document type: {document_type}")
            return False
        
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Check if document exists based on table structure
            if table_name == 'grns':
                # GRNs table: check by company, document_number, and document_date
                query = """
                    SELECT 1 FROM grns 
                    WHERE company = %s AND document_number = %s AND document_date = %s 
                    LIMIT 1
                """
            elif table_name == 'purchase_orders':
                # Purchase orders: check by company, document_number, and document_date
                query = """
                    SELECT 1 FROM purchase_orders 
                    WHERE company = %s AND document_number = %s AND document_date = %s 
                    LIMIT 1
                """
            elif table_name == 'branch_orders':
                # Branch orders: check by company, document_number, and document_date
                query = """
                    SELECT 1 FROM branch_orders 
                    WHERE company = %s AND document_number = %s AND document_date = %s 
                    LIMIT 1
                """
            elif table_name == 'supplier_invoices':
                # Supplier invoices: check by company, document_number, and document_date
                query = """
                    SELECT 1 FROM supplier_invoices 
                    WHERE company = %s AND document_number = %s AND document_date = %s 
                    LIMIT 1
                """
            else:
                return False
            
            cursor.execute(query, (company, document_number, document_date))
            result = cursor.fetchone()
            return result is not None
            
        except Exception as e:
            # If table doesn't exist or query fails, assume document is not processed
            self.logger.debug(f"Error checking if document is processed: {e}")
            return False
        finally:
            if conn:
                cursor.close()
                self.put_connection(conn)
    
    def mark_document_processed(self, script_name: str, company: str, document_type: str,
                               document_number: str, document_date: str) -> bool:
        """
        Mark a document as processed (compatibility method)
        
        Note: With PostgreSQL, we don't need a separate tracking table since
        we check if documents exist directly in the data tables. This method
        is kept for compatibility but is essentially a no-op.
        
        Args:
            script_name: Name of the script/fetcher (not used, kept for compatibility)
            company: Company name
            document_type: Type of document (GRN, PURCHASE, BRANCH, SUPPLIER_INVOICE)
            document_number: Document number
            document_date: Document date (YYYY-MM-DD format)
        
        Returns:
            True (always succeeds since documents are tracked in data tables)
        """
        # No-op: Documents are automatically tracked by their presence in data tables
        # The is_document_processed method checks the actual data tables
        return True
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """Execute a SELECT query and return results as list of dicts"""
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            results = cursor.fetchall()
            return [dict(row) for row in results]
            
        except Exception as e:
            self.logger.error(f"❌ Query failed: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.put_connection(conn)
    
    def execute_update(self, query: str, params: tuple = None) -> int:
        """Execute an UPDATE/INSERT/DELETE query and return affected rows"""
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            conn.commit()
            return cursor.rowcount
            
        except Exception as e:
            self.logger.error(f"❌ Update failed: {e}")
            if conn:
                conn.rollback()
            return 0
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.put_connection(conn)
    
    def get_database_info(self) -> Dict:
        """Get database information (compatibility method)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM current_stock")
            stock_count = cursor.fetchone()[0]
            cursor.close()
            self.put_connection(conn)
            
            return {
                "exists": True,
                "type": "Supabase PostgreSQL",
                "stock_records": stock_count,
                "path": "Supabase Cloud Database"
            }
        except Exception as e:
            self.logger.error(f"Error getting database info: {e}")
            return {
                "exists": False,
                "error": str(e)
            }
    
    def get_branches(self, company: Optional[str] = None) -> List[Dict]:
        """Get list of branches from inventory_analysis or current_stock table"""
        branches = {}
        conn = None
        cursor = None
        
        # First try inventory_analysis table (has branch info)
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Check if inventory_analysis_new table exists first (then try inventory_analysis)
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('inventory_analysis_new', 'inventory_analysis')
                )
            """)
            table_exists = cursor.fetchone()[0]
            
            # Determine which table name to use
            table_name = None
            if table_exists:
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('inventory_analysis_new', 'inventory_analysis')
                    ORDER BY CASE WHEN table_name = 'inventory_analysis_new' THEN 1 ELSE 2 END
                    LIMIT 1
                """)
                result = cursor.fetchone()
                if result:
                    table_name = result[0]
            
            if table_name:
                try:
                    # Try to get column names to determine if it's new or old format
                    # Table name is validated, safe to use in query
                    cursor.execute(f"""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_schema = 'public' 
                        AND table_name = '{table_name}'
                        AND column_name IN ('company_name', 'branch_name', 'company', 'branch')
                    """)
                    columns = [row[0] for row in cursor.fetchall()]
                    
                    # Use appropriate column names based on table structure
                    if 'company_name' in columns and 'branch_name' in columns:
                        # New format (inventory_analysis_new) - has company_name and branch_name
                        self.logger.info(f"Using inventory_analysis_new format (company_name, branch_name)")
                        if company:
                            query = f'SELECT DISTINCT company_name as company, branch_name as branch_name FROM "{table_name}" WHERE company_name = %s ORDER BY company_name, branch_name'
                            self.logger.info(f"Executing query: {query} with params: ({company},)")
                            cursor.execute(query, (company,))
                        else:
                            query = f'SELECT DISTINCT company_name as company, branch_name as branch_name FROM "{table_name}" ORDER BY company_name, branch_name'
                            self.logger.info(f"Executing query: {query}")
                            cursor.execute(query)
                        
                        results = cursor.fetchall()
                        self.logger.info(f"Query returned {len(results)} rows")
                        if results:
                            self.logger.info(f"Sample result: {results[0] if results else 'None'}")
                        
                        for row in results:
                            key = f"{row['branch_name']}|{row['company']}"
                            if key not in branches:
                                branches[key] = {
                                    'branch_name': row['branch_name'],
                                    'company': row['company'],
                                    'branch': row['branch_name']  # For backward compatibility
                                }
                                self.logger.debug(f"Added branch: {row['branch_name']} ({row['company']})")
                        
                        if branches:
                            self.logger.info(f"Found {len(branches)} unique branches from {table_name}")
                            if cursor:
                                cursor.close()
                            if conn:
                                self.put_connection(conn)
                            return list(branches.values())
                    elif 'company' in columns and 'branch' in columns:
                        # Old format (inventory_analysis) - has company and branch
                        self.logger.info(f"Using inventory_analysis format (company, branch)")
                        if company:
                            query = f'SELECT DISTINCT company, branch as branch_name FROM "{table_name}" WHERE company = %s ORDER BY company, branch'
                            cursor.execute(query, (company,))
                        else:
                            query = f'SELECT DISTINCT company, branch as branch_name FROM "{table_name}" ORDER BY company, branch'
                            cursor.execute(query)
                    
                    results = cursor.fetchall()
                    for row in results:
                        key = f"{row['branch_name']}|{row['company']}"
                        branches[key] = {
                            'branch_name': row['branch_name'],
                            'company': row['company'],
                            'branch': row['branch_name']
                        }
                    
                    if branches:
                        self.logger.info(f"Found {len(branches)} branches from {table_name}")
                        if cursor:
                            cursor.close()
                        if conn:
                            self.put_connection(conn)
                        return list(branches.values())
                except Exception as e:
                    self.logger.warning(f"Could not query {table_name}: {e}")
                    if cursor:
                        cursor.close()
                    if conn:
                        self.put_connection(conn)
                    conn = None
                    cursor = None
            else:
                self.logger.info("inventory_analysis_new/inventory_analysis table does not exist, using current_stock")
                if cursor:
                    cursor.close()
                if conn:
                    self.put_connection(conn)
                conn = None
                cursor = None
        except Exception as e:
            self.logger.warning(f"Error checking inventory_analysis tables: {e}")
            if conn:
                try:
                    if cursor:
                        cursor.close()
                    self.put_connection(conn)
                except:
                    pass
            conn = None
            cursor = None
        
        # Fallback to current_stock if inventory_analysis is empty or doesn't exist
        try:
            if not conn:
                conn = self.get_connection()
            if not cursor:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            if company:
                cursor.execute("""
                    SELECT DISTINCT company, branch as branch_name
                    FROM current_stock
                    WHERE company = %s
                    ORDER BY company, branch
                """, (company,))
            else:
                cursor.execute("""
                    SELECT DISTINCT company, branch as branch_name
                    FROM current_stock
                    ORDER BY company, branch
                """)
            
            results = cursor.fetchall()
            for row in results:
                key = f"{row['branch_name']}|{row['company']}"
                if key not in branches:
                    branches[key] = {
                        'branch_name': row['branch_name'],
                        'company': row['company'],
                        'branch': row['branch_name']
                    }
            
            if cursor:
                cursor.close()
            if conn:
                self.put_connection(conn)
            
            if branches:
                self.logger.info(f"Found {len(branches)} branches from current_stock")
            
            result = list(branches.values())
            self.logger.info(f"Returning {len(result)} branches" + (f" for {company}" if company else ""))
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting branches from current_stock: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            if conn:
                try:
                    if cursor:
                        cursor.close()
                    self.put_connection(conn)
                except:
                    pass
            return []
        finally:
            # Ensure connection is always returned
            if conn:
                try:
                    if cursor:
                        cursor.close()
                    self.put_connection(conn)
                except:
                    pass
    
    @property
    def db_path(self) -> str:
        """Return database path (for compatibility with SQLite interface)"""
        # Return the internal value
        return getattr(self, '_db_path_value', "Supabase PostgreSQL")
    
    @db_path.setter
    def db_path(self, value: str):
        """Setter for db_path property"""
        self._db_path_value = value
    
    def __getattr__(self, name: str):
        """Fallback for attribute access - ensures db_path is always accessible"""
        if name == 'db_path':
            return "Supabase PostgreSQL"
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
    
    def close(self):
        """Close all connections in pool"""
        if hasattr(self, 'pool'):
            self.pool.closeall()
            logger.info("✅ PostgreSQL connection pool closed")
    
    def test_table_schema(self, table_name: str) -> Dict:
        """
        Test and verify table schema - useful for debugging
        Returns detailed information about the table structure
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Get detailed schema information
            cursor.execute("""
                SELECT 
                    c.column_name, 
                    c.data_type,
                    c.column_default,
                    c.is_nullable,
                    CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END as is_primary_key
                FROM information_schema.columns c
                LEFT JOIN (
                    SELECT ku.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage ku
                        ON tc.constraint_name = ku.constraint_name
                    WHERE tc.table_name = %s
                        AND tc.table_schema = 'public'
                        AND tc.constraint_type = 'PRIMARY KEY'
                ) pk ON c.column_name = pk.column_name
                WHERE c.table_name = %s 
                AND c.table_schema = 'public'
                ORDER BY c.ordinal_position
            """, (table_name, table_name))
            
            columns = []
            for row in cursor.fetchall():
                columns.append({
                    'name': row[0],
                    'type': row[1],
                    'default': row[2],
                    'nullable': row[3],
                    'is_primary_key': row[4],
                    'is_auto_generated': row[4] or 'SERIAL' in row[1].upper() or row[2] is not None
                })
            
            # Get row count
            cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
            row_count = cursor.fetchone()[0]
            
            return {
                'table_name': table_name,
                'columns': columns,
                'row_count': row_count,
                'status': 'ok'
            }
            
        except Exception as e:
            self.logger.error(f"Error testing table {table_name}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return {
                'table_name': table_name,
                'error': str(e),
                'status': 'error'
            }
        finally:
            if conn:
                try:
                    cursor.close()
                except:
                    pass
                try:
                    self.put_connection(conn)
                except:
                    pass

