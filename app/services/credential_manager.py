"""
Credential Manager - Ported for Web Application
Manages user credentials for NILA and DAIMA APIs
"""
import json
import sqlite3
import os
import logging
import requests
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import threading

logger = logging.getLogger(__name__)

class CredentialManager:
    """Manages credentials for API access - web version"""
    
    def __init__(self, app_root: str = None):
        if app_root:
            self.app_root = app_root
        else:
            # Default to cache directory
            from app.config import settings
            self.app_root = settings.LOCAL_CACHE_DIR
        
        # Use cache/config directory for credentials
        self.config_dir = os.path.join(self.app_root, "config")
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Credentials file for persistence
        self.credentials_file = os.path.join(self.config_dir, "credentials.json")
        
        # Use in-memory storage with file persistence
        self._credentials = self._load_credentials()
        self._token_cache = {}
        self._token_lock = threading.Lock()
        self._session_cache = {}
        self._session_lock = threading.Lock()
        
        self.logger = logging.getLogger(__name__)
    
    def _load_credentials(self) -> Dict:
        """Load credentials from file"""
        if os.path.exists(self.credentials_file):
            try:
                with open(self.credentials_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load credentials: {e}")
        return {}
    
    def _save_credentials(self):
        """Save credentials to file"""
        try:
            with open(self.credentials_file, 'w') as f:
                json.dump(self._credentials, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save credentials: {e}")
    
    def save_credentials(self, company: str, username: str, password: str, base_url: str = None) -> Dict:
        """Save credentials for a company"""
        try:
            if not base_url:
                base_url = 'https://corebasebackendnila.co.ke:5019'
            
            # Test credentials first
            test_result = self.test_credentials(company, username, password, base_url)
            
            if test_result['success']:
                self._credentials[company] = {
                    'username': username,
                    'password': password,
                    'base_url': base_url,
                    'enabled': True,
                    'last_tested': datetime.now().isoformat(),
                    'test_status': 'valid'
                }
                
                # Clear any cached tokens for this company
                self.clear_tokens(company)
                
                # Persist credentials
                self._save_credentials()
                
                self.logger.info(f"✅ Credentials saved and validated for {company}")
            
            return test_result
            
        except Exception as e:
            self.logger.error(f"Failed to save credentials for {company}: {e}")
            return {'success': False, 'message': f"Save failed: {str(e)}"}
    
    def test_credentials(self, company: str, username: str, password: str, base_url: str) -> Dict:
        """Test if credentials work with the API"""
        success, token, message = self.authenticate_company(company, username, password, base_url)
        
        return {
            'success': success,
            'message': message,
            'token_obtained': success
        }
    
    def get_credentials(self, company: str) -> Optional[Dict]:
        """Get credentials for a company"""
        return self._credentials.get(company)
    
    def authenticate_company(self, company: str, username: str = None, password: str = None, 
                           base_url: str = None) -> Tuple[bool, Optional[str], str]:
        """
        Authenticate with company API and return token
        
        Returns: (success, token, message)
        """
        try:
            # Use provided credentials or get from storage
            if username is None or password is None:
                creds = self.get_credentials(company)
                if not creds:
                    return False, None, f"No credentials found for {company}"
                username = creds['username']
                password = creds['password']
                base_url = base_url or creds['base_url']
            
            session = self.get_session(company)
            
            payload = {
                "userName": username,
                "password": password,
                "machineCookie": "",
                "clientPin": 0,
                "latt": "",
                "long": "",
                "ipLocation": ""
            }
            
            response = session.post(
                f"{base_url}/Auth",
                json=payload,
                headers={"Content-Type": "application/json"},
                verify=False,
                timeout=30
            )
            
            if response.status_code == 200:
                token_data = response.json()
                token = token_data.get("token")
                
                if token:
                    # Cache the token (expires in 1 hour as per API)
                    expires_at = datetime.now() + timedelta(hours=1)
                    self._cache_token(company, token, expires_at)
                    
                    return True, token, "Authentication successful"
                else:
                    return False, None, "No token received from API"
            
            elif response.status_code == 401:
                return False, None, "Invalid username or password"
            else:
                return False, None, f"HTTP {response.status_code}: {response.text}"
                
        except requests.exceptions.Timeout:
            return False, None, "Connection timeout - server not responding"
            
        except requests.exceptions.ConnectionError:
            return False, None, "Connection error - cannot reach server"
            
        except Exception as e:
            return False, None, f"Unexpected error: {str(e)}"
    
    def get_valid_token(self, company: str) -> Optional[str]:
        """Get a valid token for the company"""
        with self._token_lock:
            if company in self._token_cache:
                token_data = self._token_cache[company]
                if datetime.now() < token_data['expires_at']:
                    return token_data['token']
                else:
                    del self._token_cache[company]
        
        # Need to re-authenticate
        creds = self.get_credentials(company)
        if creds:
            success, token, message = self.authenticate_company(
                company, creds['username'], creds['password'], creds['base_url']
            )
            if success:
                return token
        
        return None
    
    def get_session(self, company: str) -> requests.Session:
        """Get or create a session for a company"""
        with self._session_lock:
            if company not in self._session_cache:
                session = requests.Session()
                
                retry_strategy = Retry(
                    total=3,
                    backoff_factor=1,
                    status_forcelist=[429, 500, 502, 503, 504],
                )
                adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
                session.mount("http://", adapter)
                session.mount("https://", adapter)
                
                session.verify = False
                session.timeout = 30
                
                self._session_cache[company] = session
            
            return self._session_cache[company]
    
    def _cache_token(self, company: str, token: str, expires_at: datetime):
        """Cache token in memory"""
        with self._token_lock:
            self._token_cache[company] = {
                'token': token,
                'expires_at': expires_at
            }
    
    def clear_tokens(self, company: str = None):
        """Clear cached tokens"""
        with self._token_lock:
            if company:
                if company in self._token_cache:
                    del self._token_cache[company]
            else:
                self._token_cache.clear()
    
    def get_enabled_companies(self) -> List[str]:
        """Get list of companies that have credentials"""
        return [company for company, creds in self._credentials.items() 
                if creds.get('enabled', False)]

