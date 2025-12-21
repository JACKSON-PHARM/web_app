"""
Database Manager - Ported for Web Application
Manages SQLite database operations
"""
import sqlite3
import logging
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)

# Try to import the original database manager, but make it optional
_OriginalDatabaseManager = None
try:
    import sys
    parent_path = os.path.join(os.path.dirname(__file__), '..', '..', '..')
    if os.path.exists(parent_path):
        sys.path.insert(0, parent_path)
        from database_manager import DatabaseManager as _OriginalDatabaseManager
        logger.info("✅ Imported original DatabaseManager")
except ImportError as e:
    logger.warning(f"⚠️ Could not import original DatabaseManager: {e}")
    logger.info("ℹ️ Will use standalone database initialization")

class DatabaseManager:
    """Database manager for web application - wraps original with web-specific features"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = logging.getLogger("DatabaseManager")
        
        # Ensure directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        
        # Initialize using original database manager if available, otherwise use standalone
        if _OriginalDatabaseManager:
            try:
                self._db_manager = _OriginalDatabaseManager(db_path)
                # Ensure the wrapped manager has db_path attribute
                if not hasattr(self._db_manager, 'db_path'):
                    self._db_manager.db_path = db_path
                self.logger.info(f"✅ Database manager initialized with original: {db_path}")
            except Exception as e:
                self.logger.warning(f"⚠️ Failed to initialize original DatabaseManager: {e}")
                self.logger.info("ℹ️ Using standalone database initialization")
                self._init_standalone_database()
        else:
            self._init_standalone_database()
    
    def _init_standalone_database(self):
        """Initialize database schema standalone (when original manager not available)"""
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()
            
            # Create basic tables if they don't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS current_stock (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    branch TEXT NOT NULL,
                    item_code TEXT NOT NULL,
                    item_name TEXT,
                    stock_pieces REAL NOT NULL,
                    company TEXT NOT NULL,
                    pack_size REAL DEFAULT 1,
                    unit_price REAL DEFAULT 0.0,
                    stock_value REAL DEFAULT 0.0,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(branch, item_code, company)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company TEXT NOT NULL,
                    branch TEXT NOT NULL,
                    sale_date DATE NOT NULL,
                    invoice_number TEXT NOT NULL,
                    item_code TEXT NOT NULL,
                    item_name TEXT,
                    quantity_sold REAL NOT NULL,
                    selling_price REAL NOT NULL,
                    total_amount REAL NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            conn.close()
            self.logger.info(f"✅ Standalone database initialized: {self.db_path}")
            self._db_manager = None  # No wrapper needed
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize standalone database: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            raise
    
    def get_db_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path, check_same_thread=False)
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """Execute query and return results as list of dicts"""
        conn = self.get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            results = cursor.fetchall()
            return [dict(row) for row in results]
        finally:
            conn.close()
    
    def execute_update(self, query: str, params: tuple = None) -> int:
        """Execute update/insert/delete and return affected rows"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
    
    def get_table_count(self, table_name: str) -> int:
        """Get row count for a table"""
        try:
            result = self.execute_query(f"SELECT COUNT(*) as count FROM {table_name}")
            return result[0]['count'] if result else 0
        except Exception as e:
            self.logger.error(f"Error getting count for {table_name}: {e}")
            return 0
    
    def get_branches(self, company: Optional[str] = None) -> List[Dict]:
        """Get list of branches from database, with fallback to branch config"""
        branches = {}
        
        try:
            # Try to get branches from current_stock table
            try:
                if company:
                    query = "SELECT DISTINCT branch as branch_name, company FROM current_stock WHERE company = ? ORDER BY branch"
                    results = self.execute_query(query, (company,))
                else:
                    query = "SELECT DISTINCT branch as branch_name, company FROM current_stock ORDER BY company, branch"
                    results = self.execute_query(query)
                
                for r in results:
                    key = f"{r['branch_name']}|{r['company']}"
                    branches[key] = r
            except Exception as e:
                self.logger.warning(f"Could not query current_stock: {e}")
            
            # Try stock_data table
            try:
                if company:
                    query2 = "SELECT DISTINCT branch_name, company_name as company FROM stock_data WHERE company_name = ? ORDER BY branch_name"
                    results2 = self.execute_query(query2, (company,))
                else:
                    query2 = "SELECT DISTINCT branch_name, company_name as company FROM stock_data ORDER BY company_name, branch_name"
                    results2 = self.execute_query(query2)
                
                for r in results2:
                    key = f"{r['branch_name']}|{r['company']}"
                    if key not in branches:
                        branches[key] = r
            except Exception as e:
                self.logger.warning(f"Could not query stock_data: {e}")
            
            # If no branches found in database, use branch config as fallback
            if not branches:
                self.logger.info("No branches found in database, using branch config fallback")
                try:
                    from scripts.data_fetchers.branch_config import ALL_BRANCHES
                    for branch_info in ALL_BRANCHES:
                        if not company or branch_info.get('company', '').upper() == company.upper():
                            key = f"{branch_info['branch_name']}|{branch_info['company']}"
                            branches[key] = {
                                'branch_name': branch_info['branch_name'],
                                'company': branch_info['company'],
                                'branch': branch_info['branch_name']  # Add branch alias
                            }
                except ImportError:
                    self.logger.warning("Could not import branch_config, using hardcoded branches")
                    # Hardcoded fallback
                    fallback_branches = [
                        {'branch_name': 'BABA DOGO HQ', 'company': 'NILA', 'branch': 'BABA DOGO HQ'},
                        {'branch_name': 'DAIMA MERU WHOLESALE', 'company': 'DAIMA', 'branch': 'DAIMA MERU WHOLESALE'},
                        {'branch_name': 'DAIMA MERU RETAIL', 'company': 'DAIMA', 'branch': 'DAIMA MERU RETAIL'},
                    ]
                    for branch_info in fallback_branches:
                        if not company or branch_info['company'].upper() == company.upper():
                            key = f"{branch_info['branch_name']}|{branch_info['company']}"
                            branches[key] = branch_info
            
            result = list(branches.values())
            self.logger.info(f"Found {len(result)} branches" + (f" for {company}" if company else ""))
            return result
        except Exception as e:
            self.logger.error(f"Error getting branches: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            # Return fallback branches even on error
            try:
                from scripts.data_fetchers.branch_config import ALL_BRANCHES
                fallback = []
                for branch_info in ALL_BRANCHES:
                    if not company or branch_info.get('company', '').upper() == company.upper():
                        fallback.append({
                            'branch_name': branch_info['branch_name'],
                            'company': branch_info['company'],
                            'branch': branch_info['branch_name']
                        })
                return fallback
            except:
                # Last resort hardcoded
                return [
                    {'branch_name': 'BABA DOGO HQ', 'company': 'NILA', 'branch': 'BABA DOGO HQ'},
                    {'branch_name': 'DAIMA MERU WHOLESALE', 'company': 'DAIMA', 'branch': 'DAIMA MERU WHOLESALE'},
                ]
    
    def get_database_info(self) -> Dict:
        """Get database information"""
        try:
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            return {
                'path': self.db_path,
                'exists': os.path.exists(self.db_path),
                'size': db_size,
                'size_mb': round(db_size / (1024 * 1024), 2),
                'tables': self._get_table_list()
            }
        except Exception as e:
            self.logger.error(f"Error getting database info: {e}")
            return {'exists': False}
    
    def _get_table_list(self) -> List[str]:
        """Get list of tables in database"""
        try:
            query = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            results = self.execute_query(query)
            return [row['name'] for row in results]
        except:
            return []

