"""
Run script for PharmaStock Web Application
Compatible with Render deployment (uses PORT env var)
"""
import uvicorn
import os
from app.config import settings

if __name__ == "__main__":
    # Render provides PORT environment variable - use it if available
    port = int(os.environ.get("PORT", settings.PORT))
    host = os.environ.get("HOST", settings.HOST)
    
    # Disable reload in production (Render sets DEBUG=False)
    reload = settings.DEBUG and os.environ.get("ENVIRONMENT") != "production"
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )

