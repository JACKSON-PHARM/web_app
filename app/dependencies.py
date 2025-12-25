"""
FastAPI Dependencies
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from typing import Optional
from app.config import settings
from app.services.license_service import LicenseService
from app.services.postgres_database_manager import PostgresDatabaseManager
import os
import logging

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
license_service = LicenseService()

# Global instances
_db_manager: Optional[PostgresDatabaseManager] = None

def reset_db_manager():
    """Reset the database manager singleton"""
    global _db_manager
    _db_manager = None

def get_db_manager():
    """Get database manager instance - ONLY Supabase PostgreSQL (no SQLite fallback)"""
    global _db_manager
    if _db_manager is None:
        # REQUIRE Supabase PostgreSQL - no fallback
        if not settings.DATABASE_URL:
            error_msg = "DATABASE_URL environment variable is required. All data is stored in Supabase PostgreSQL."
            logger.error(f"❌ {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_msg
            )
        
        try:
            _db_manager = PostgresDatabaseManager(settings.DATABASE_URL)
            logger.info("✅ Using Supabase PostgreSQL database")
        except Exception as e:
            error_msg = f"Failed to connect to Supabase PostgreSQL: {e}. Please check your DATABASE_URL environment variable."
            logger.error(f"❌ {error_msg}")
            import traceback
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_msg
            )
    
    # Verify connection is still valid
    try:
        if not hasattr(_db_manager, 'pool') or _db_manager.pool is None:
            logger.warning("⚠️ Database pool is None, reinitializing...")
            _db_manager = PostgresDatabaseManager(settings.DATABASE_URL)
    except Exception as e:
        logger.error(f"❌ Error verifying database connection: {e}")
        # Don't raise here - let the endpoint handle it
    
    return _db_manager

# Global user service instance (singleton)
_user_service = None

def get_user_service():
    """Get or create user service instance - uses Supabase"""
    global _user_service
    if _user_service is None:
        # Use Supabase-based user service
        from app.services.user_service_supabase import UserServiceSupabase
        db_manager = get_db_manager()
        _user_service = UserServiceSupabase(db_manager)
        logger.info("✅ Using Supabase-based UserService")
    return _user_service

# Global credential manager instance (singleton)
_credential_manager = None

def get_credential_manager():
    """Get or create credential manager instance - uses Supabase"""
    global _credential_manager
    if _credential_manager is None:
        from app.services.credential_manager_supabase import CredentialManagerSupabase
        db_manager = get_db_manager()
        _credential_manager = CredentialManagerSupabase(db_manager)
        logger.info("✅ Using Supabase-based CredentialManager")
    return _credential_manager

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Get current authenticated user from JWT token"""
    user_service = get_user_service()
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        is_admin: bool = payload.get("is_admin", False)
        
        if username is None:
            raise credentials_exception
        
        # For admin user 9542, skip expensive checks
        if username.lower() == '9542':
            return {
                "username": username,
                "is_admin": True
            }
        
        # Verify user still exists and is valid (only for non-admin)
        user_info = user_service.get_user_info(username)
        if not user_info or not user_info.get('active', True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive or deleted"
            )
        
        # Check subscription
        expires_str = user_info.get('subscription_expires')
        if expires_str:
            try:
                from datetime import datetime
                expires = datetime.fromisoformat(expires_str)
                if datetime.now() >= expires:
                    days_remaining = user_info.get('days_remaining', 0)
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Subscription expired. {days_remaining} days remaining."
                    )
            except Exception:
                pass
        
    except JWTError:
        raise credentials_exception
    
    return {
        "username": username,
        "is_admin": is_admin
    }

async def get_current_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Get current user, ensuring they are admin"""
    user_service = get_user_service()
    
    username = current_user.get("username")
    if not username or not user_service.is_admin(username):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

