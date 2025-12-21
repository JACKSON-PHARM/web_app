"""
FastAPI Dependencies
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from typing import Optional
from app.config import settings
from app.services.license_service import LicenseService
from app.services.database_manager import DatabaseManager
from app.services.google_drive import GoogleDriveManager
import os
import logging

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
license_service = LicenseService()

# Global instances
_drive_manager: Optional[GoogleDriveManager] = None
_db_manager: Optional[DatabaseManager] = None

def get_drive_manager() -> GoogleDriveManager:
    """Get Google Drive manager instance"""
    global _drive_manager
    if _drive_manager is None:
        _drive_manager = GoogleDriveManager()
    return _drive_manager

def get_db_manager() -> DatabaseManager:
    """Get database manager instance"""
    global _db_manager
    if _db_manager is None:
        # Get local database path - ensure it's absolute
        # On Render free tier (no persistent disk), use temp directory
        if os.getenv("RENDER"):
            # On Render, use /tmp if no persistent disk is mounted
            cache_dir = os.getenv("RENDER_DISK_PATH", "/tmp/pharmastock_cache")
            logger.info(f"🌐 Render environment detected - using cache dir: {cache_dir}")
        elif os.path.isabs(settings.LOCAL_CACHE_DIR):
            cache_dir = settings.LOCAL_CACHE_DIR
        else:
            # Relative to web_app/app directory
            web_app_dir = os.path.dirname(os.path.dirname(__file__))
            cache_dir = os.path.join(web_app_dir, settings.LOCAL_CACHE_DIR.lstrip("./"))
        
        local_db_path = os.path.join(cache_dir, settings.DB_FILENAME)
        # Ensure directory exists
        os.makedirs(cache_dir, exist_ok=True)
        logger.info(f"Database path: {local_db_path}")
        logger.info(f"Database exists: {os.path.exists(local_db_path)}")
        if os.path.exists(local_db_path):
            logger.info(f"Database size: {os.path.getsize(local_db_path) / (1024*1024):.2f} MB")
        else:
            logger.info("ℹ️ Database will be created on first use or downloaded from Google Drive")
        _db_manager = DatabaseManager(local_db_path)
    return _db_manager

# Global user service instance (singleton)
_user_service = None

def get_user_service():
    """Get or create user service instance"""
    global _user_service
    if _user_service is None:
        from app.services.user_service import UserService
        _user_service = UserService()
    return _user_service

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

