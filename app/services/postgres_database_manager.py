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
            self.pool = ThreadedConnectionPool(1, 5, connection_string)
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
    
    def insert_current_stock(self, stock_data: List[Dict], replace_all: bool = True) -> int:
        """
        Insert current stock data - replaces ALL existing stock on each refresh
        
        Args:
            stock_data: List of stock records
            replace_all: If True, delete all existing records first
        """
        if not stock_data:
            return 0
        
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if replace_all:
                # Clear all existing stock data first
                cursor.execute("DELETE FROM current_stock")
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    self.logger.info(f"🗑️ Cleared {deleted_count} existing stock records")
            
            # Insert new data
            columns = list(stock_data[0].keys())
            placeholders = ', '.join(['%s'] * len(columns))
            column_names = ', '.join([f'"{col}"' for col in columns])
            
            insert_sql = f"""
                INSERT INTO current_stock ({column_names}) 
                VALUES ({placeholders})
                ON CONFLICT (branch, item_code, company) 
                DO UPDATE SET {', '.join([f'"{col}" = EXCLUDED."{col}"' for col in columns if col not in ['branch', 'item_code', 'company']])}
            """
            
            count = 0
            for record in stock_data:
                try:
                    values = [record.get(col) for col in columns]
                    cursor.execute(insert_sql, values)
                    count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to insert stock record: {e}")
                    continue
            
            conn.commit()
            self.logger.info(f"✅ Inserted {count} records into current_stock")
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
    
    def _insert_data(self, table_name: str, data: List[Dict], replace: bool = False) -> int:
        """Generic method to insert data into any table"""
        if not data:
            return 0
        
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            columns = list(data[0].keys())
            column_names = ', '.join([f'"{col}"' for col in columns])
            placeholders = ', '.join(['%s'] * len(columns))
            
            # Build INSERT statement
            if replace:
                # Use ON CONFLICT DO UPDATE
                conflict_cols = self._get_unique_columns(table_name)
                if conflict_cols:
                    update_cols = [f'"{col}" = EXCLUDED."{col}"' for col in columns if col not in conflict_cols]
                    insert_sql = f"""
                        INSERT INTO "{table_name}" ({column_names}) 
                        VALUES ({placeholders})
                        ON CONFLICT ({', '.join([f'"{col}"' for col in conflict_cols])})
                        DO UPDATE SET {', '.join(update_cols)}
                    """
                else:
                    insert_sql = f'INSERT INTO "{table_name}" ({column_names}) VALUES ({placeholders})'
            else:
                # Use INSERT ... ON CONFLICT DO NOTHING
                insert_sql = f'INSERT INTO "{table_name}" ({column_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'
            
            count = 0
            for record in data:
                try:
                    values = [record.get(col) for col in columns]
                    cursor.execute(insert_sql, values)
                    count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to insert record in {table_name}: {e}")
                    continue
            
            conn.commit()
            self.logger.info(f"✅ Inserted {count} records into {table_name}")
            return count
            
        except Exception as e:
            self.logger.error(f"❌ Failed to insert data into {table_name}: {e}")
            if conn:
                conn.rollback()
            return 0
        finally:
            if conn:
                cursor.close()
                self.put_connection(conn)
    
    def _get_unique_columns(self, table_name: str) -> List[str]:
        """Get unique constraint columns for a table"""
        # Common unique constraints
        unique_constraints = {
            'current_stock': ['branch', 'item_code', 'company'],
            'purchase_orders': ['company', 'branch', 'document_number', 'item_code'],
            'branch_orders': ['company', 'source_branch', 'document_number', 'item_code'],
            'supplier_invoices': ['company', 'branch', 'document_number', 'item_code'],
        }
        return unique_constraints.get(table_name, [])
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """Execute a SELECT query and return results as list of dicts"""
        conn = None
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
            if conn:
                cursor.close()
                self.put_connection(conn)
    
    def execute_update(self, query: str, params: tuple = None) -> int:
        """Execute an UPDATE/INSERT/DELETE query and return affected rows"""
        conn = None
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
            if conn:
                cursor.close()
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
                    cursor.execute(f"""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_schema = 'public' 
                        AND table_name = %s
                        AND column_name IN ('company_name', 'branch_name', 'company', 'branch')
                    """, (table_name,))
                    columns = [row[0] for row in cursor.fetchall()]
                    
                    # Use appropriate column names based on table structure
                    if 'company_name' in columns and 'branch_name' in columns:
                        # New format (inventory_analysis_new)
                        if company:
                            cursor.execute(f"""
                                SELECT DISTINCT company_name as company, branch_name as branch_name
                                FROM {table_name}
                                WHERE company_name = %s
                                ORDER BY company_name, branch_name
                            """, (company,))
                        else:
                            cursor.execute(f"""
                                SELECT DISTINCT company_name as company, branch_name as branch_name
                                FROM {table_name}
                                ORDER BY company_name, branch_name
                            """)
                    elif 'company' in columns and 'branch' in columns:
                        # Old format (inventory_analysis)
                        if company:
                            cursor.execute(f"""
                                SELECT DISTINCT company, branch as branch_name
                                FROM {table_name}
                                WHERE company = %s
                                ORDER BY company, branch
                            """, (company,))
                        else:
                            cursor.execute(f"""
                                SELECT DISTINCT company, branch as branch_name
                                FROM {table_name}
                                ORDER BY company, branch
                            """)
                    
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
                        cursor.close()
                        self.put_connection(conn)
                        return list(branches.values())
                except Exception as e:
                    self.logger.warning(f"Could not query {table_name}: {e}")
                    cursor.close()
                    self.put_connection(conn)
            else:
                self.logger.info("inventory_analysis_new/inventory_analysis table does not exist, using current_stock")
                cursor.close()
                self.put_connection(conn)
        except Exception as e:
            self.logger.warning(f"Error checking inventory_analysis tables: {e}")
            if conn:
                try:
                    cursor.close()
                    self.put_connection(conn)
                except:
                    pass
        
        # Fallback to current_stock if inventory_analysis is empty or doesn't exist
        try:
            conn = self.get_connection()
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
            
            cursor.close()
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
                    cursor.close()
                    self.put_connection(conn)
                except:
                    pass
            return []
    
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

