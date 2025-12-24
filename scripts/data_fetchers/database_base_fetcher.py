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
    
    def __init__(self, script_name: str, app_root: str = None):
        self.script_name = script_name
        self.app_root = app_root or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.cred_manager = CredentialManager(self.app_root)
        
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
        
        self.setup_logging()
        
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
            return None

    def get_enabled_companies(self) -> List[str]:
        """Get list of enabled companies from credential manager"""
        return self.cred_manager.get_enabled_companies()
    
    def get_company_base_url(self, company: str) -> str:
        """Return base URL for a company (falls back to default)"""
        creds = self.cred_manager.get_credentials(company)
        if creds and creds.get("base_url"):
            return creds["base_url"].rstrip("/")
        return "https://corebasebackendnila.co.ke:5019"

    def is_document_processed(self, company: str, document_type: str, 
                            document_number: str, document_date: str) -> bool:
        """Check if a document is already processed"""
        return self.db_manager.is_document_processed(
            self.script_name, company, document_type, document_number, document_date
        )

    def mark_document_processed(self, company: str, document_type: str,
                               document_number: str, document_date: str) -> bool:
        """Mark a document as processed"""
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

