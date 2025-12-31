"""
Database-Backed Base Fetcher
Handles authentication via credential_manager and data persistence via database_manager
All database fetchers should inherit from this class
"""
import os
import sys
import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import requests

# Add the app root to Python path
app_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, app_root)

# Try to import from web app services first (for Render deployment)
try:
    from app.services.credential_manager import CredentialManager
    from app.services.database_manager import DatabaseManager as WebDatabaseManager
    # Use the underlying database manager from the web app wrapper
    # The web app's DatabaseManager wraps the original, so we need to access it
    USE_WEB_APP_SERVICES = True
except ImportError:
    # Fallback to original imports (for local development with full codebase)
    try:
        from credential_manager import CredentialManager
        from database_manager import DatabaseManager
        USE_WEB_APP_SERVICES = False
    except ImportError as e:
        print(f"❌ Required modules not found: {e}")
        print("Please ensure credential_manager.py and database_manager.py are in your Python path.")
        raise


class DatabaseBaseFetcher:
    """
    Base class for all database-backed data fetchers
    Handles:
    - Authentication via CredentialManager
    - Data persistence via DatabaseManager
    - Document tracking for incremental loading
    - Logging and error handling
    """
    
    def __init__(self, script_name: str, app_root: str = None, credential_manager=None):
        self.script_name = script_name
        self.app_root = app_root or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Setup logging first so we can use logger later
        self.setup_logging()
        
        # Use provided credential manager or try to create one (will be overridden by refresh_service)
        if credential_manager:
            self.cred_manager = credential_manager
        else:
            # Try to create credential manager - will fail gracefully if not available
            try:
                # For web app, try to get from dependencies
                if USE_WEB_APP_SERVICES:
                    try:
                        from app.dependencies import get_credential_manager
                        self.cred_manager = get_credential_manager()
                    except Exception as e:
                        # Fallback: create a dummy that will be overridden
                        self.logger.warning(f"Could not get credential manager from dependencies: {e}, will be set by refresh_service")
                        self.cred_manager = None
                else:
                    self.cred_manager = CredentialManager(self.app_root)
            except Exception as e:
                # Will be set by refresh_service
                self.logger.warning(f"Could not create credential manager: {e}, will be set by refresh_service")
                self.cred_manager = None
        
        # Initialize database manager - use Supabase if available, otherwise SQLite
        if USE_WEB_APP_SERVICES:
            # For web app, check if Supabase is configured
            try:
                from app.config import settings
                if settings.DATABASE_URL:
                    # Use Supabase PostgreSQL
                    from app.services.postgres_database_manager import PostgresDatabaseManager
                    self.db_manager = PostgresDatabaseManager(settings.DATABASE_URL)
                    self.logger.info("✅ Using Supabase PostgreSQL database")
                else:
                    # Use SQLite fallback
                    db_path = os.path.join(settings.LOCAL_CACHE_DIR, "pharma_stock.db")
                    self.db_manager = WebDatabaseManager(db_path)
                    # If web app's manager wraps the original, try to get underlying manager
                    if hasattr(self.db_manager, '_db_manager'):
                        self.db_manager = self.db_manager._db_manager
                    self.logger.info(f"📁 Using SQLite database: {db_path}")
            except Exception as e:
                self.logger.warning(f"⚠️ Could not use web app services: {e}")
                # Fallback to original database manager
                self.db_manager = DatabaseManager(os.path.join(self.app_root, "database", "pharma_data.db"))
        else:
            # Use original database manager
            self.db_manager = DatabaseManager(os.path.join(self.app_root, "database", "pharma_data.db"))
        
    def setup_logging(self):
        """Setup logging for the script"""
        log_dir = os.path.join(self.app_root, "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format=f'%(asctime)s - {self.script_name} - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, f'{self.script_name}.log'), encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(self.script_name)

    def get_authenticated_session(self, company: str) -> Optional[requests.Session]:
        """
        Get authenticated session using credential manager
        """
        if not self.cred_manager:
            self.logger.error(f"❌ Credential manager not initialized")
            return None
            
        try:
            session = self.cred_manager.get_session(company)
            token = self.cred_manager.get_valid_token(company)
            if not token:
                self.logger.error(f"❌ Could not get valid token for {company}")
                return None
            
            session.headers.update({
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            })
            
            self.logger.info(f"✅ Authenticated session created for {company}")
            return session
            
        except Exception as e:
            self.logger.error(f"❌ Failed to create authenticated session for {company}: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return None

    def get_enabled_companies(self) -> List[str]:
        """Get list of enabled companies from credential manager"""
        if not self.cred_manager:
            self.logger.warning("Credential manager not initialized, returning empty list")
            return []
        return self.cred_manager.get_enabled_companies()
    
    def get_company_base_url(self, company: str) -> str:
        """Return base URL for a company (falls back to default)"""
        if not self.cred_manager:
            return "https://corebasebackendnila.co.ke:5019"
        creds = self.cred_manager.get_credentials(company)
        if creds and creds.get("base_url"):
            return creds["base_url"].rstrip("/")
        return "https://corebasebackendnila.co.ke:5019"

    def get_existing_document_numbers(self, company: str, document_type: str) -> set:
        """
        Get all existing document numbers for a company and document type.
        Uses document_number ONLY (not date) for comparison.
        This is the preferred method for bulk checks before fetching details.
        
        Args:
            company: Company name
            document_type: Type of document (GRN, PURCHASE, BRANCH, SUPPLIER_INVOICE)
        
        Returns:
            Set of existing document numbers (as strings)
        """
        if hasattr(self.db_manager, 'get_existing_document_numbers'):
            return self.db_manager.get_existing_document_numbers(company, document_type)
        else:
            # Fallback: return empty set if method not available
            self.logger.warning(f"get_existing_document_numbers not available, returning empty set")
            return set()
    
    def is_document_processed(self, company: str, document_type: str, 
                            document_number: str, document_date: str) -> bool:
        """
        Check if a document is already processed.
        NOTE: For bulk checks, prefer get_existing_document_numbers() for better performance.
        """
        return self.db_manager.is_document_processed(
            self.script_name, company, document_type, document_number, document_date
        )

    def mark_document_processed(self, company: str, document_type: str,
                               document_number: str, document_date: str) -> bool:
        """Mark a document as processed (compatibility method - no-op for PostgreSQL)"""
        return self.db_manager.mark_document_processed(
            self.script_name, company, document_type, document_number, document_date
        )

    def safe_date_parse(self, date_str, default_date=None):
        """Safely parse date string"""
        if not date_str:
            return default_date or datetime.now().date()
        
        for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%Y-%m-%dT%H:%M:%S', '%d/%m/%Y %H:%M:%S']:
            try:
                return datetime.strptime(str(date_str).strip(), fmt).date()
            except:
                continue
        
        return default_date or datetime.now().date()

    def format_date_for_api(self, date_obj) -> str:
        """Format date for API (DD/MM/YYYY)"""
        if hasattr(date_obj, 'strftime'):
            return date_obj.strftime("%d/%m/%Y")
        return str(date_obj)

    def format_date_for_db(self, date_obj) -> str:
        """Format date for database (YYYY-MM-DD)"""
        if hasattr(date_obj, 'strftime'):
            return date_obj.strftime("%Y-%m-%d")
        elif isinstance(date_obj, str):
            parsed = self.safe_date_parse(date_obj)
            return parsed.strftime("%Y-%m-%d")
        return str(date_obj)
    
    def get_retention_date_range(self, days: int = 30):
        """
        Get date range for data retention (last N days)
        
        Args:
            days: Number of days to retain (default 30)
            
        Returns:
            tuple: (start_date, end_date) as date objects
        """
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        return start_date, end_date
    
    def get_full_year_date_range(self, start_year: int = 2025):
        """
        Get date range from start of year to today (like standalone scripts)
        
        Args:
            start_year: Year to start from (default 2025)
            
        Returns:
            tuple: (start_date, end_date) as date objects
        """
        today = datetime.now().date()
        year_start = datetime(start_year, 1, 1).date()
        return year_start, today

    def api_request(self, session: requests.Session, url: str, params=None, 
                   headers=None, max_retries: int = 3) -> Optional[dict]:
        """Make API request with retry logic"""
        import time
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        for attempt in range(max_retries):
            try:
                response = session.get(url, params=params, headers=headers, 
                                      verify=False, timeout=30)
                
                # Log response details for debugging
                if attempt == 0:  # Only log on first attempt to avoid spam
                    self.logger.debug(f"API Request: {url} | Status: {response.status_code} | Params: {params}")
                
                if response.status_code == 400:
                    self.logger.warning(f"API returned 400 Bad Request for {url} with params {params}")
                    return None
                elif response.status_code >= 500:
                    if attempt < max_retries - 1:
                        time.sleep(0.5)
                        continue
                    self.logger.error(f"API returned {response.status_code} for {url}")
                
                response.raise_for_status()
                
                # Parse JSON response
                if response.content:
                    try:
                        result = response.json()
                        
                        # Log response type for debugging
                        if attempt == 0:  # Only log on first attempt
                            self.logger.debug(f"API Response type: {type(result)}, length: {len(result) if isinstance(result, (list, dict)) else 'N/A'}")
                            if isinstance(result, list) and len(result) > 0:
                                self.logger.debug(f"Sample response item keys: {list(result[0].keys()) if isinstance(result[0], dict) else 'N/A'}")
                        
                        # Handle both list and dict responses
                        if isinstance(result, list):
                            return result
                        elif isinstance(result, dict):
                            # Some APIs return data in a 'data' key
                            if 'data' in result:
                                return result['data']
                            # Some APIs return error messages in dict
                            if 'error' in result or 'message' in result:
                                self.logger.warning(f"API returned error/message: {result}")
                                return None
                            return result
                        return result
                    except ValueError as e:
                        self.logger.error(f"Failed to parse JSON response: {e} | Content: {response.text[:200]}")
                        return None
                else:
                    self.logger.debug(f"Empty response content for {url}")
                    return []
                
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                    continue
                self.logger.error(f"❌ API request failed after {max_retries} attempts: {e}")
                import traceback
                self.logger.debug(traceback.format_exc())
        
        return None

    def log_script_start(self):
        """Log script start with credential status"""
        enabled_companies = self.get_enabled_companies()
        self.logger.info(f"🚀 Starting {self.script_name}")
        self.logger.info(f"📊 Enabled companies: {enabled_companies}")
        
        for company in ['NILA', 'DAIMA']:
            creds = self.cred_manager.get_credentials(company)
            status = "✅ Configured" if creds else "❌ Not configured"
            self.logger.info(f"   {company}: {status}")

    def validate_prerequisites(self) -> bool:
        """Validate that we have at least one company configured"""
        enabled_companies = self.get_enabled_companies()
        if not enabled_companies:
            self.logger.error("❌ No companies configured. Please setup credentials first.")
            return False
        return True

    def cleanup_old_records(self, table_name: str, date_column: str, retention_days: int = 90) -> int:
        """
        Delete old records from a table
        
        Args:
            table_name: Name of the table to clean
            date_column: Name of the date column to check
            retention_days: Number of days to retain (default 90)
            
        Returns:
            Number of records deleted
        """
        try:
            from datetime import datetime, timedelta
            
            cutoff_date = (datetime.now() - timedelta(days=retention_days)).date()
            cutoff_date_str = cutoff_date.strftime('%Y-%m-%d')
            
            self.logger.info(f"🧹 Cleaning {table_name}: deleting records older than {cutoff_date_str} ({retention_days} days)")
            
            # Check if using PostgreSQL or SQLite
            if hasattr(self.db_manager, 'get_connection'):
                conn = self.db_manager.get_connection()
                cursor = conn.cursor()
                
                try:
                    # Check if table exists and get date column type
                    if hasattr(self.db_manager, 'pool') or 'PostgresDatabaseManager' in str(type(self.db_manager)):
                        # PostgreSQL
                        cursor.execute(f"""
                            DELETE FROM {table_name} 
                            WHERE {date_column} < %s
                        """, (cutoff_date_str,))
                    else:
                        # SQLite
                        cursor.execute(f"""
                            DELETE FROM {table_name} 
                            WHERE {date_column} < ?
                        """, (cutoff_date_str,))
                    
                    deleted_count = cursor.rowcount
                    conn.commit()
                    cursor.close()
                    self.db_manager.put_connection(conn)
                    
                    if deleted_count > 0:
                        self.logger.info(f"✅ Deleted {deleted_count:,} old records from {table_name}")
                    else:
                        self.logger.info(f"ℹ️ No old records to delete from {table_name}")
                    
                    return deleted_count
                    
                except Exception as e:
                    conn.rollback()
                    cursor.close()
                    self.db_manager.put_connection(conn)
                    self.logger.warning(f"⚠️ Error cleaning {table_name}: {e}")
                    return 0
            else:
                self.logger.warning(f"⚠️ Database manager does not support cleanup operations")
                return 0
                
        except Exception as e:
            self.logger.warning(f"⚠️ Error in cleanup_old_records for {table_name}: {e}")
            return 0

