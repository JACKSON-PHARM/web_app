"""
Application Configuration
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    """Application settings"""
    
    # Google Drive Configuration
    GOOGLE_DRIVE_EMAIL: str = "controleddrugsalesdaimamerudda@gmail.com"
    GOOGLE_DRIVE_FOLDER_ID: str = ""  # Will be created/configured
    GOOGLE_CREDENTIALS_FILE: str = os.path.join(os.path.dirname(__file__), "..", "google_credentials.json")
    GOOGLE_TOKEN_FILE: str = os.path.join(os.path.dirname(__file__), "..", "google_token.json")
    GOOGLE_OAUTH_CALLBACK_URL: Optional[str] = None  # Will be set dynamically
    
    # Database Configuration
    DB_FILENAME: str = "pharma_stock.db"
    # On Render free tier (no persistent disk), use temp directory
    # Data will be synced from/to Google Drive on startup/shutdown
    LOCAL_CACHE_DIR: str = os.getenv("RENDER_DISK_PATH", os.path.join(os.path.dirname(__file__), "..", "cache"))
    
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

settings = Settings()

# Detect Render environment and set callback URL dynamically
if not settings.GOOGLE_OAUTH_CALLBACK_URL:
    # Check if we're on Render (RENDER environment variable is set)
    render_url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("RENDER_URL")
    if render_url:
        # On Render - use the Render URL
        settings.GOOGLE_OAUTH_CALLBACK_URL = f"{render_url}/api/admin/drive/callback"
        print(f"🌐 Detected Render environment. Using callback URL: {settings.GOOGLE_OAUTH_CALLBACK_URL}")
    else:
        # Local development - use localhost
        settings.GOOGLE_OAUTH_CALLBACK_URL = "http://localhost:8000/api/admin/drive/callback"
        print(f"💻 Local development mode. Using callback URL: {settings.GOOGLE_OAUTH_CALLBACK_URL}")

# Ensure cache directory exists
os.makedirs(settings.LOCAL_CACHE_DIR, exist_ok=True)

