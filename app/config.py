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
    
    # Database Configuration - Supabase PostgreSQL
    DATABASE_URL: Optional[str] = None  # Supabase connection string (set via environment variable)
    # Fallback to SQLite if DATABASE_URL not set (for local development)
    DB_FILENAME: str = "pharma_stock.db"
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
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"  # Allow extra fields from environment variables

settings = Settings()

# Ensure cache directory exists (for SQLite fallback)
os.makedirs(settings.LOCAL_CACHE_DIR, exist_ok=True)

# Log database configuration
if settings.DATABASE_URL:
    logger.info("✅ Using Supabase PostgreSQL database")
else:
    logger.info("ℹ️ Using SQLite database (set DATABASE_URL to use Supabase)")

