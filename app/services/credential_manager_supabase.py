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


class AccountLockedException(Exception):
    """Exception raised when an account is locked due to failed login attempts"""
    def __init__(self, company: str, message: str):
        self.company = company
        self.message = message
        super().__init__(self.message)


class InvalidCredentialsException(Exception):
    """Exception raised when credentials are invalid"""
    def __init__(self, company: str, message: str):
        self.company = company
        self.message = message
        super().__init__(self.message)

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
        """Get valid authentication token for company - uses /Auth endpoint like standalone scripts"""
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
                logger.warning(f"No credentials found for {company}")
                return None
            
            # Log credential info (without password) for debugging
            logger.info(f"🔐 Authenticating {company} with username: {creds.get('username', 'N/A')}, base_url: {creds.get('base_url', 'N/A')}")
            
            # Authenticate and get token using /Auth endpoint with correct payload format
            # IMPORTANT: Use ONLY the correct payload format to avoid wasting authentication attempts
            # The API allows only 3 attempts before locking the account
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                
                session = requests.Session()
                base_url = creds['base_url'].rstrip('/')
                auth_url = f"{base_url}/Auth"
                logger.info(f"🔗 Auth URL: {auth_url}")
                
                # Use the correct payload format (as specified by user)
                # DO NOT try multiple formats - this wastes authentication attempts!
                payload = {
                    "userName": creds['username'],
                    "password": creds['password'],
                    "machineCookie": "",
                    "clientPin": 0,
                    "latt": "",
                    "long": "",
                    "ipLocation": ""
                }
                
                headers = {
                    "Content-Type": "application/json",
                    "Origin": "https://phamacoreonline.co.ke:5100",
                    "Referer": "https://phamacoreonline.co.ke:5100/",
                    "Accept": "application/json"
                }
                
                logger.info(f"🔐 Attempting authentication for {company}")
                response = session.post(
                    auth_url,
                    json=payload,
                    headers=headers,
                    verify=False,
                    timeout=15
                )
                
                if response.status_code == 200:
                    data = response.json()
                    token = data.get('token') or data.get('access_token')
                    
                    if token:
                        # Cache token (assume 8 hour expiry)
                        expires_at = datetime.now().replace(microsecond=0) + timedelta(hours=8)
                        self._token_cache[company] = {
                            'token': token,
                            'expires_at': expires_at
                        }
                        logger.info(f"✅ Obtained token for {company}")
                        return token
                    else:
                        logger.error(f"❌ No token in response for {company}: {data}")
                        return None
                else:
                    # Log the error response for debugging
                    try:
                        error_data = response.json()
                        error_message = error_data.get('message', str(error_data))
                        logger.error(f"❌ Auth returned {response.status_code} for {company}: {error_message}")
                        
                        # Check for account lockout - raise special exception to inform user
                        username = creds.get('username', 'Unknown')
                        if 'locked' in error_message.lower() or 'lock' in error_message.lower():
                            logger.error(f"🚫 Account is locked for {company} - Username: {username}")
                            # Raise a custom exception that can be caught by API endpoints
                            raise AccountLockedException(
                                company=company,
                                message=f"Your {company} account (username: {username}) is locked due to failed login attempts. "
                                       f"Please unlock your account from Pharmacore first, then update your credentials in Settings."
                            )
                        elif 'invalid credentials' in error_message.lower():
                            logger.error(f"🚫 Invalid credentials for {company} - Username: {username}. Check username/password in Settings.")
                            raise InvalidCredentialsException(
                                company=company,
                                message=f"Invalid credentials for {company} (username: {username}). Please check your username and password in Settings."
                            )
                        
                        return None
                    except:
                        error_text = response.text[:500] if response.text else "No response body"
                        logger.error(f"❌ Auth returned {response.status_code} for {company}: {error_text}")
                        return None
                                
            except AccountLockedException:
                # Re-raise account locked exceptions so API endpoints can handle them
                raise
            except InvalidCredentialsException:
                # Re-raise invalid credentials exceptions so API endpoints can handle them
                raise
            except requests.exceptions.HTTPError as e:
                # This catches response.raise_for_status() if called
                error_detail = str(e)
                try:
                    if hasattr(e, 'response') and e.response is not None:
                        error_detail = f"{e.response.status_code}: {e.response.text[:500]}"
                except:
                    pass
                logger.error(f"❌ HTTP error for {company}: {error_detail}")
                return None
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ Request error for {company}: {e}")
                return None
            except Exception as e:
                logger.error(f"❌ Unexpected error getting token for {company}: {e}")
                import traceback
                logger.error(traceback.format_exc())
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
    
    def delete_credentials(self, company: str) -> Dict:
        """Delete credentials for a company"""
        conn = None
        cursor = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            # Delete credentials by setting is_enabled to FALSE (soft delete)
            # Or completely remove the record
            cursor.execute("""
                DELETE FROM app_credentials
                WHERE company_name = %s
            """, (company,))
            
            conn.commit()
            cursor.close()
            self.db_manager.put_connection(conn)
            
            # Clear cached tokens
            self.clear_tokens(company)
            
            logger.info(f"✅ Deleted credentials for {company}")
            return {'success': True, 'message': f'Credentials deleted for {company}'}
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error deleting credentials: {e}")
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
            return {'success': False, 'message': f'Failed to delete credentials: {str(e)}'}
    
    def test_credentials(self, company: str, username: str, password: str, base_url: str) -> Dict:
        """Test credentials using the same endpoint and format as get_valid_token"""
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            session = requests.Session()
            base_url_clean = base_url.rstrip('/')
            auth_url = f"{base_url_clean}/Auth"
            
            # Use the same payload format as get_valid_token
            payload = {
                "userName": username,
                "password": password,
                "machineCookie": "",
                "clientPin": 0,
                "latt": "",
                "long": "",
                "ipLocation": ""
            }
            
            headers = {
                "Content-Type": "application/json",
                "Origin": "https://phamacoreonline.co.ke:5100",
                "Referer": "https://phamacoreonline.co.ke:5100/",
                "Accept": "application/json"
            }
            
            response = session.post(
                auth_url,
                json=payload,
                headers=headers,
                verify=False,
                timeout=15
            )
            
            # Check if authentication was successful
            if response.status_code == 200:
                data = response.json()
                token = data.get('token') or data.get('access_token')
                success = token is not None
                
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
                
                if success:
                    return {
                        'success': True,
                        'message': 'Credentials valid',
                        'token_obtained': True
                    }
                else:
                    return {
                        'success': False,
                        'message': 'Authentication failed: No token in response',
                        'token_obtained': False
                    }
            else:
                # Get error message from response
                error_message = f'Authentication failed: {response.status_code}'
                try:
                    error_data = response.json()
                    api_message = error_data.get('message', str(error_data))
                    error_message = api_message
                    
                    # Check for account lockout - include username in message
                    if 'locked' in api_message.lower() or 'lock' in api_message.lower():
                        error_message = (
                            f'Your {company} account (username: {username}) is locked due to failed login attempts. '
                            'Please unlock your account from Pharmacore first, then update your credentials in Settings.'
                        )
                        logger.error(f"🚫 Account locked for {company} - Username: {username}")
                    elif 'invalid credentials' in api_message.lower():
                        # Extract attempts remaining if available
                        if 'attempts remaining' in api_message.lower():
                            error_message = (
                                f'{api_message} (username: {username}) '
                                'Please check your username and password. '
                                'If your account gets locked, unlock it from Pharmacore first, then update credentials here.'
                            )
                            logger.warning(f"⚠️ Invalid credentials for {company} - Username: {username} - {api_message}")
                        else:
                            error_message = f'Invalid credentials for {company} (username: {username}). Please check your username and password in Settings.'
                            logger.warning(f"⚠️ Invalid credentials for {company} - Username: {username}")
                except:
                    error_text = response.text[:200] if response.text else "Unknown error"
                    error_message = f'Authentication failed: {error_text}'
                
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
                    """, (datetime.now(), False, company))
                    conn.commit()
                    cursor.close()
                    self.db_manager.put_connection(conn)
                except Exception as e:
                    logger.warning(f"Could not update test status: {e}")
                
                return {
                    'success': False,
                    'message': error_message,
                    'token_obtained': False
                }
            
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'message': f'Error testing credentials: {str(e)}',
                'token_obtained': False
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error testing credentials: {str(e)}',
                'token_obtained': False
            }

