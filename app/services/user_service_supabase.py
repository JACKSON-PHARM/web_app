"""
User Management Service for Supabase
Manages users with username/password authentication and subscriptions in PostgreSQL
"""
import hashlib
from typing import List, Optional, Tuple, Dict
from datetime import datetime, timedelta
import logging
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

class UserServiceSupabase:
    """Manages users with username/password and subscriptions using Supabase PostgreSQL"""
    
    def __init__(self, db_manager):
        """Initialize with database manager"""
        self.db_manager = db_manager
        self._ensure_users_table()
    
    def _ensure_users_table(self):
        """Ensure users table exists (should be created by migration script)"""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'app_users'
                )
            """)
            exists = cursor.fetchone()[0]
            cursor.close()
            self.db_manager.put_connection(conn)
            
            if not exists:
                logger.warning("⚠️ app_users table does not exist. Run create_supabase_tables.py script first.")
        except Exception as e:
            logger.error(f"Error checking users table: {e}")
    
    def _hash_password(self, password: str) -> str:
        """Hash password using SHA256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate user with username and password"""
        conn = None
        cursor = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            username_lower = username.lower().strip()
            password_hash = self._hash_password(password)
            
            cursor.execute("""
                SELECT username, password_hash, is_admin, active, subscription_expires, subscription_days
                FROM app_users
                WHERE LOWER(username) = %s AND password_hash = %s
            """, (username_lower, password_hash))
            
            user = cursor.fetchone()
            cursor.close()
            self.db_manager.put_connection(conn)
            
            if not user:
                return None
            
            # Check if user is active
            if not user.get('active', True):
                return None
            
            # Check subscription
            expires_str = user.get('subscription_expires')
            if expires_str:
                try:
                    expires = expires_str if isinstance(expires_str, datetime) else datetime.fromisoformat(str(expires_str))
                    if datetime.now() >= expires:
                        return None
                except:
                    pass
            
            # Return user info (without password hash)
            return {
                'username': user['username'],
                'is_admin': user.get('is_admin', False),
                'subscription_expires': expires_str.isoformat() if expires_str and isinstance(expires_str, datetime) else str(expires_str),
                'subscription_days': user.get('subscription_days', 0)
            }
            
        except Exception as e:
            logger.error(f"Error authenticating user: {e}")
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
    
    def get_user_info(self, username: str) -> Optional[Dict]:
        """Get user information"""
        conn = None
        cursor = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            username_lower = username.lower().strip()
            
            cursor.execute("""
                SELECT username, is_admin, active, subscription_expires, subscription_days, created_at
                FROM app_users
                WHERE LOWER(username) = %s
            """, (username_lower,))
            
            user = cursor.fetchone()
            cursor.close()
            self.db_manager.put_connection(conn)
            
            if not user:
                return None
            
            expires_str = user.get('subscription_expires')
            expires_date = None
            days_remaining = 0
            
            if expires_str:
                try:
                    expires_date = expires_str if isinstance(expires_str, datetime) else datetime.fromisoformat(str(expires_str))
                    days_remaining = max(0, (expires_date - datetime.now()).days)
                except:
                    pass
            
            return {
                'username': user['username'],
                'is_admin': user.get('is_admin', False),
                'active': user.get('active', True),
                'subscription_days': user.get('subscription_days', 0),
                'subscription_expires': expires_str.isoformat() if expires_date else str(expires_str) if expires_str else None,
                'days_remaining': days_remaining,
                'created_at': user.get('created_at')
            }
            
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
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
    
    def is_admin(self, username: str) -> bool:
        """Check if user is admin"""
        user_info = self.get_user_info(username)
        return user_info and user_info.get('is_admin', False)
    
    def create_user(self, username: str, password: str, subscription_days: int, created_by: str, is_admin: bool = False) -> Tuple[bool, str]:
        """Create a new user (admin only)"""
        if not self.is_admin(created_by):
            return False, "Only admins can create users"
        
        conn = None
        cursor = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            username_lower = username.lower().strip()
            
            # Check if username already exists
            cursor.execute("SELECT id FROM app_users WHERE LOWER(username) = %s", (username_lower,))
            if cursor.fetchone():
                cursor.close()
                self.db_manager.put_connection(conn)
                return False, f"Username '{username}' already exists"
            
            # Create new user
            expires_date = datetime.now() + timedelta(days=subscription_days)
            password_hash = self._hash_password(password)
            
            cursor.execute("""
                INSERT INTO app_users (username, password_hash, is_admin, subscription_days, subscription_expires, 
                                     active, created_by, created_at, last_updated, last_updated_by)
                VALUES (%s, %s, %s, %s, %s, TRUE, %s, %s, %s, %s)
            """, (username, password_hash, is_admin, subscription_days, expires_date, 
                  created_by, datetime.now(), datetime.now(), created_by))
            
            conn.commit()
            cursor.close()
            self.db_manager.put_connection(conn)
            
            logger.info(f"✅ Created user: {username} (subscription: {subscription_days} days)")
            return True, f"User '{username}' created successfully with {subscription_days} days subscription"
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error creating user: {e}")
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
            return False, f"Error creating user: {str(e)}"
    
    def get_all_users(self) -> List[Dict]:
        """Get all users (admin only)"""
        conn = None
        cursor = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT username, is_admin, active, subscription_days, subscription_expires, 
                       created_at, created_by, last_updated, last_updated_by
                FROM app_users
                ORDER BY created_at DESC
            """)
            
            users = cursor.fetchall()
            cursor.close()
            self.db_manager.put_connection(conn)
            
            result = []
            for user in users:
                expires_str = user.get('subscription_expires')
                days_remaining = 0
                if expires_str:
                    try:
                        expires_date = expires_str if isinstance(expires_str, datetime) else datetime.fromisoformat(str(expires_str))
                        days_remaining = max(0, (expires_date - datetime.now()).days)
                    except:
                        pass
                
                result.append({
                    'username': user['username'],
                    'is_admin': user.get('is_admin', False),
                    'active': user.get('active', True),
                    'subscription_days': user.get('subscription_days', 0),
                    'days_remaining': days_remaining,
                    'created_at': user.get('created_at'),
                    'created_by': user.get('created_by')
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
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
            return []

