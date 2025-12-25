"""
Credential Manager for Supabase
Manages API credentials in PostgreSQL instead of local files
"""
import logging
import requests
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import threading
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

class CredentialManagerSupabase:
    """Manages credentials for API access using Supabase PostgreSQL"""
    
    def __init__(self, db_manager):
        """Initialize with database manager"""
        self.db_manager = db_manager
        self._token_cache = {}
        self._token_lock = threading.Lock()
        self._session_cache = {}
        self._session_lock = threading.Lock()
        self._ensure_credentials_table()
    
    def _ensure_credentials_table(self):
        """Ensure credentials table exists"""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'app_credentials'
                )
            """)
            exists = cursor.fetchone()[0]
            cursor.close()
            self.db_manager.put_connection(conn)
            
            if not exists:
                logger.warning("⚠️ app_credentials table does not exist. Run create_supabase_tables.py script first.")
        except Exception as e:
            logger.error(f"Error checking credentials table: {e}")
    
    def save_credentials(self, company: str, username: str, password: str, base_url: str = None) -> Dict:
        """Save credentials to Supabase"""
        conn = None
        cursor = None
        try:
            if not base_url:
                base_url = 'https://corebasebackendnila.co.ke:5019'
            
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            # Upsert credentials
            cursor.execute("""
                INSERT INTO app_credentials (company_name, username, password, base_url, is_enabled, updated_at)
                VALUES (%s, %s, %s, %s, TRUE, %s)
                ON CONFLICT (company_name) 
                DO UPDATE SET 
                    username = EXCLUDED.username,
                    password = EXCLUDED.password,
                    base_url = EXCLUDED.base_url,
                    is_enabled = TRUE,
                    updated_at = EXCLUDED.updated_at
            """, (company, username, password, base_url, datetime.now()))
            
            conn.commit()
            cursor.close()
            self.db_manager.put_connection(conn)
            
            # Clear cached tokens
            self.clear_tokens(company)
            
            logger.info(f"✅ Saved credentials for {company}")
            return {'success': True, 'message': f'Credentials saved for {company}'}
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error saving credentials: {e}")
            if cursor:
                try:
                    cursor.close()
                except:
                    pass
            if conn:
                try:
                    self.db_manager.put_connection(conn)
                except:
                    pass
            return {'success': False, 'message': f'Failed to save credentials: {str(e)}'}
    
    def get_credentials(self, company: str) -> Optional[Dict]:
        """Get credentials for a company"""
        conn = None
        cursor = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT username, password, base_url, is_enabled
                FROM app_credentials
                WHERE company_name = %s AND is_enabled = TRUE
            """, (company,))
            
            result = cursor.fetchone()
            cursor.close()
            self.db_manager.put_connection(conn)
            
            if result and result.get('username'):
                return {
                    'username': result['username'],
                    'password': result['password'],
                    'base_url': result.get('base_url', 'https://corebasebackendnila.co.ke:5019'),
                    'enabled': bool(result.get('is_enabled', True))
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting credentials: {e}")
            if cursor:
                try:
                    cursor.close()
                except:
                    pass
            if conn:
                try:
                    self.db_manager.put_connection(conn)
                except:
                    pass
            return None
    
    def get_all_credentials(self) -> Dict[str, Dict]:
        """Get credentials for all enabled companies"""
        companies = ['NILA', 'DAIMA']
        credentials = {}
        
        for company in companies:
            creds = self.get_credentials(company)
            if creds:
                credentials[company] = creds
        
        return credentials
    
    def get_enabled_companies(self) -> List[str]:
        """Get list of companies that have credentials and are enabled"""
        enabled = []
        all_creds = self.get_all_credentials()
        
        for company, creds in all_creds.items():
            if creds and creds.get('enabled', False) and creds.get('username'):
                enabled.append(company)
        
        return enabled
    
    def get_valid_token(self, company: str) -> Optional[str]:
        """Get valid authentication token for company"""
        with self._token_lock:
            # Check cache first
            if company in self._token_cache:
                token_data = self._token_cache[company]
                # Check if token is still valid (not expired)
                if token_data.get('expires_at') and datetime.now() < token_data['expires_at']:
                    return token_data['token']
            
            # Get credentials
            creds = self.get_credentials(company)
            if not creds:
                return None
            
            # Authenticate and get token
            try:
                session = requests.Session()
                auth_url = f"{creds['base_url']}/api/auth/login"
                response = session.post(auth_url, json={
                    'username': creds['username'],
                    'password': creds['password']
                }, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    token = data.get('access_token') or data.get('token')
                    
                    if token:
                        # Cache token (assume 8 hour expiry)
                        expires_at = datetime.now().replace(microsecond=0) + timedelta(hours=8)
                        self._token_cache[company] = {
                            'token': token,
                            'expires_at': expires_at
                        }
                        logger.info(f"✅ Obtained token for {company}")
                        return token
                
                logger.error(f"Failed to get token for {company}: {response.status_code}")
                return None
                
            except Exception as e:
                logger.error(f"Error getting token for {company}: {e}")
                return None
    
    def get_session(self, company: str) -> Optional[requests.Session]:
        """Get authenticated session for company"""
        with self._session_lock:
            if company in self._session_cache:
                return self._session_cache[company]
            
            session = requests.Session()
            
            # Configure retries
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504]
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            self._session_cache[company] = session
            return session
    
    def clear_tokens(self, company: str = None):
        """Clear cached tokens"""
        with self._token_lock:
            if company:
                self._token_cache.pop(company, None)
            else:
                self._token_cache.clear()
    
    def test_credentials(self, company: str, username: str, password: str, base_url: str) -> Dict:
        """Test credentials"""
        try:
            session = requests.Session()
            auth_url = f"{base_url}/api/auth/login"
            response = session.post(auth_url, json={
                'username': username,
                'password': password
            }, timeout=10)
            
            success = response.status_code == 200
            
            # Update last_tested in database
            conn = None
            cursor = None
            try:
                conn = self.db_manager.get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE app_credentials
                    SET last_tested = %s, last_test_success = %s
                    WHERE company_name = %s
                """, (datetime.now(), success, company))
                conn.commit()
                cursor.close()
                self.db_manager.put_connection(conn)
            except Exception as e:
                logger.warning(f"Could not update test status: {e}")
            
            return {
                'success': success,
                'message': 'Credentials valid' if success else f'Authentication failed: {response.status_code}',
                'token_obtained': success
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error testing credentials: {str(e)}',
                'token_obtained': False
            }

