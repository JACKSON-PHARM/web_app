"""
User Management Service
Manages users with username/password authentication and subscriptions
"""
import json
import os
import hashlib
from typing import List, Optional, Tuple, Dict
from datetime import datetime, timedelta
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class UserService:
    """Manages users with username/password and subscriptions"""
    
    def __init__(self):
        self.users_db_path = os.path.join(settings.LOCAL_CACHE_DIR, "users_db.json")
        self._ensure_users_db()
    
    def _ensure_users_db(self):
        """Ensure users database exists with default admin"""
        if not os.path.exists(self.users_db_path):
            # Create default admin user: username="9542", password="9542"
            default_admin = {
                'username': '9542',
                'password_hash': self._hash_password('9542'),
                'is_admin': True,
                'created_at': datetime.now().isoformat(),
                'subscription_days': 36500,  # 100 years (essentially permanent)
                'subscription_expires': (datetime.now() + timedelta(days=36500)).isoformat(),
                'active': True
            }
            
            self._save_users({
                'users': [default_admin],
                'created_at': datetime.now().isoformat()
            })
            logger.info("✅ Created users database with default admin (username: 9542)")
    
    def _hash_password(self, password: str) -> str:
        """Hash password using SHA256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def _load_users(self) -> dict:
        """Load users database"""
        try:
            with open(self.users_db_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading users: {e}")
            return {'users': []}
    
    def _save_users(self, data: dict):
        """Save users database"""
        try:
            os.makedirs(os.path.dirname(self.users_db_path), exist_ok=True)
            with open(self.users_db_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving users: {e}")
            raise
    
    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate user with username and password"""
        users = self._load_users()
        username_lower = username.lower().strip()
        password_hash = self._hash_password(password)
        
        for user in users.get('users', []):
            if user['username'].lower() == username_lower and user['password_hash'] == password_hash:
                # Check if user is active
                if not user.get('active', True):
                    return None
                
                # Check subscription
                if not self._is_subscription_valid(user):
                    return None
                
                # Return user info (without password hash)
                return {
                    'username': user['username'],
                    'is_admin': user.get('is_admin', False),
                    'subscription_expires': user.get('subscription_expires'),
                    'subscription_days': user.get('subscription_days', 0)
                }
        
        return None
    
    def _is_subscription_valid(self, user: dict) -> bool:
        """Check if user's subscription is still valid"""
        expires_str = user.get('subscription_expires')
        if not expires_str:
            return False
        
        try:
            expires = datetime.fromisoformat(expires_str)
            return datetime.now() < expires
        except Exception as e:
            logger.error(f"Error checking subscription: {e}")
            return False
    
    def create_user(self, username: str, password: str, subscription_days: int, created_by: str, is_admin: bool = False) -> Tuple[bool, str]:
        """Create a new user (admin only)"""
        if not self.is_admin(created_by):
            return False, "Only admins can create users"
        
        users = self._load_users()
        username_lower = username.lower().strip()
        
        # Check if username already exists
        for user in users.get('users', []):
            if user['username'].lower() == username_lower:
                return False, f"Username '{username}' already exists"
        
        # Create new user
        expires_date = datetime.now() + timedelta(days=subscription_days)
        new_user = {
            'username': username,
            'password_hash': self._hash_password(password),
            'is_admin': is_admin,
            'created_at': datetime.now().isoformat(),
            'created_by': created_by,
            'subscription_days': subscription_days,
            'subscription_expires': expires_date.isoformat(),
            'active': True
        }
        
        users['users'].append(new_user)
        users['last_updated'] = datetime.now().isoformat()
        users['last_updated_by'] = created_by
        self._save_users(users)
        
        logger.info(f"✅ Created user: {username} (subscription: {subscription_days} days)")
        return True, f"User '{username}' created successfully with {subscription_days} days subscription"
    
    def update_user_subscription(self, username: str, subscription_days: int, updated_by: str) -> Tuple[bool, str]:
        """Update user's subscription (admin only)"""
        if not self.is_admin(updated_by):
            return False, "Only admins can update subscriptions"
        
        users = self._load_users()
        username_lower = username.lower().strip()
        
        for user in users.get('users', []):
            if user['username'].lower() == username_lower:
                # Don't allow updating admin user
                if user.get('is_admin', False) and username_lower != '9542':
                    return False, "Cannot update admin user subscription"
                
                # Calculate new expiration
                current_expires = datetime.fromisoformat(user.get('subscription_expires', datetime.now().isoformat()))
                if datetime.now() < current_expires:
                    # Extend from current expiration
                    new_expires = current_expires + timedelta(days=subscription_days)
                else:
                    # Start from now
                    new_expires = datetime.now() + timedelta(days=subscription_days)
                
                user['subscription_days'] = subscription_days
                user['subscription_expires'] = new_expires.isoformat()
                user['last_updated'] = datetime.now().isoformat()
                user['last_updated_by'] = updated_by
                
                users['last_updated'] = datetime.now().isoformat()
                users['last_updated_by'] = updated_by
                self._save_users(users)
                
                logger.info(f"✅ Updated subscription for {username}: {subscription_days} days")
                return True, f"Subscription updated for '{username}'"
        
        return False, f"User '{username}' not found"
    
    def deactivate_user(self, username: str, deactivated_by: str) -> Tuple[bool, str]:
        """Deactivate a user (admin only)"""
        if not self.is_admin(deactivated_by):
            return False, "Only admins can deactivate users"
        
        users = self._load_users()
        username_lower = username.lower().strip()
        
        for user in users.get('users', []):
            if user['username'].lower() == username_lower:
                if user.get('is_admin', False):
                    return False, "Cannot deactivate admin user"
                
                user['active'] = False
                user['deactivated_at'] = datetime.now().isoformat()
                user['deactivated_by'] = deactivated_by
                
                users['last_updated'] = datetime.now().isoformat()
                users['last_updated_by'] = deactivated_by
                self._save_users(users)
                
                logger.info(f"❌ Deactivated user: {username}")
                return True, f"User '{username}' deactivated"
        
        return False, f"User '{username}' not found"
    
    def activate_user(self, username: str, activated_by: str) -> Tuple[bool, str]:
        """Activate a user (admin only)"""
        if not self.is_admin(activated_by):
            return False, "Only admins can activate users"
        
        users = self._load_users()
        username_lower = username.lower().strip()
        
        for user in users.get('users', []):
            if user['username'].lower() == username_lower:
                user['active'] = True
                if 'deactivated_at' in user:
                    del user['deactivated_at']
                if 'deactivated_by' in user:
                    del user['deactivated_by']
                
                users['last_updated'] = datetime.now().isoformat()
                users['last_updated_by'] = activated_by
                self._save_users(users)
                
                logger.info(f"✅ Activated user: {username}")
                return True, f"User '{username}' activated"
        
        return False, f"User '{username}' not found"
    
    def is_admin(self, username: str) -> bool:
        """Check if user is admin"""
        users = self._load_users()
        username_lower = username.lower().strip()
        
        for user in users.get('users', []):
            if user['username'].lower() == username_lower:
                return user.get('is_admin', False)
        
        return False
    
    def get_user_info(self, username: str) -> Optional[Dict]:
        """Get user information"""
        users = self._load_users()
        username_lower = username.lower().strip()
        
        for user in users.get('users', []):
            if user['username'].lower() == username_lower:
                expires_str = user.get('subscription_expires', '')
                expires_date = None
                days_remaining = 0
                
                if expires_str:
                    try:
                        expires_date = datetime.fromisoformat(expires_str)
                        days_remaining = max(0, (expires_date - datetime.now()).days)
                    except:
                        pass
                
                return {
                    'username': user['username'],
                    'is_admin': user.get('is_admin', False),
                    'active': user.get('active', True),
                    'subscription_days': user.get('subscription_days', 0),
                    'subscription_expires': expires_str,
                    'days_remaining': days_remaining,
                    'created_at': user.get('created_at')
                }
        
        return None
    
    def list_users(self) -> List[Dict]:
        """List all users (admin only)"""
        users = self._load_users()
        result = []
        
        for user in users.get('users', []):
            expires_str = user.get('subscription_expires', '')
            expires_date = None
            days_remaining = 0
            is_valid = False
            
            if expires_str:
                try:
                    expires_date = datetime.fromisoformat(expires_str)
                    days_remaining = max(0, (expires_date - datetime.now()).days)
                    is_valid = datetime.now() < expires_date
                except:
                    pass
            
            result.append({
                'username': user['username'],
                'is_admin': user.get('is_admin', False),
                'active': user.get('active', True),
                'subscription_days': user.get('subscription_days', 0),
                'subscription_expires': expires_str,
                'days_remaining': days_remaining,
                'subscription_valid': is_valid and user.get('active', True),
                'created_at': user.get('created_at')
            })
        
        return result
    
    def delete_user(self, username: str, deleted_by: str) -> Tuple[bool, str]:
        """Delete a user permanently (admin only)"""
        if not self.is_admin(deleted_by):
            return False, "Only admins can delete users"
        
        users = self._load_users()
        username_lower = username.lower().strip()
        
        # Don't allow deleting admin user
        for user in users.get('users', []):
            if user['username'].lower() == username_lower:
                if user.get('is_admin', False):
                    return False, "Cannot delete admin user"
        
        # Remove user from list
        original_count = len(users.get('users', []))
        users['users'] = [u for u in users.get('users', []) if u['username'].lower() != username_lower]
        
        if len(users['users']) == original_count:
            return False, f"User '{username}' not found"
        
        users['last_updated'] = datetime.now().isoformat()
        users['last_updated_by'] = deleted_by
        self._save_users(users)
        
        logger.info(f"🗑️ Deleted user: {username}")
        return True, f"User '{username}' deleted successfully"

