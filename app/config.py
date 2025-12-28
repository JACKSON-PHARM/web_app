"""
Application Configuration
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """Application settings"""
    
    # Database Configuration - Supabase PostgreSQL ONLY
    DATABASE_URL: Optional[str] = None  # Supabase connection string (REQUIRED - set via environment variable)
    
    # Local cache directory (for user files, NOT database)
    LOCAL_CACHE_DIR: str = os.path.join(os.path.dirname(__file__), "..", "cache")
    
    # Application
    SECRET_KEY: str = "pharmastock-secret-key-change-in-production-2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours
    
    # License Management
    LICENSE_DB_PATH: str = "./license_db.json"  # Store licensed emails
    
    # API Base URLs
    NILA_API_URL: str = "https://corebasebackendnila.co.ke:5019"
    DAIMA_API_URL: str = "https://corebasebackendnila.co.ke:5019"
    
    # Refresh Configuration
    AUTO_REFRESH_INTERVAL_MINUTES: int = 60  # Auto-refresh every hour
    AUTO_REFRESH_ENABLED: bool = True
    
    # Server Configuration
    HOST: str = "127.0.0.1"  # Use 127.0.0.1 for local development (0.0.0.0 for production)
    PORT: int = 8001  # Changed to 8001 to avoid port conflict
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"  # Allow extra fields from environment variables

settings = Settings()

# Ensure cache directory exists (for user files, credentials, NOT database)
os.makedirs(settings.LOCAL_CACHE_DIR, exist_ok=True)

# Log database configuration
if settings.DATABASE_URL:
    logger.info("✅ Using Supabase PostgreSQL database")
else:
    logger.warning("⚠️ DATABASE_URL not set - application requires Supabase PostgreSQL connection")

