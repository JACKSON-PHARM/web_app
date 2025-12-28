"""
Run script for PharmaStock Web Application
Compatible with Render deployment (uses PORT env var)
"""
import sys
import os

# Add scripts directory to Python path to fix import issues
# Add parent directory (web_app) so 'from scripts.xxx' imports work
app_root = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.join(app_root, 'scripts')
if os.path.exists(scripts_dir) and app_root not in sys.path:
    sys.path.insert(0, app_root)

import uvicorn
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

