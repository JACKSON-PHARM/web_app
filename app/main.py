"""
FastAPI Main Application
PharmaStock Web Application Entry Point
"""
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging
import os
import sys

from app.config import settings
from app.services.google_drive import GoogleDriveManager
from app.services.license_service import LicenseService
from app.services.database_manager import DatabaseManager
from app.services.scheduler import RefreshScheduler
from app.api import auth, dashboard, stock_view, refresh, credentials, admin, procurement, suppliers
from app.dependencies import get_drive_manager, get_db_manager, get_current_user

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: RefreshScheduler = None

async def refresh_callback():
    """Callback for scheduled refresh"""
    try:
        from app.api.refresh import run_refresh_task
        result = await run_refresh_task()
        logger.info(f"✅ Scheduled refresh completed: {result}")
    except Exception as e:
        logger.error(f"❌ Scheduled refresh failed: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global scheduler
    
    # Startup - make it very resilient
    logger.info("🚀 Starting PharmaStock Web Application")
    
    # Initialize database manager first (most critical)
    try:
        db_manager = get_db_manager()
        logger.info("✅ Database manager initialized")
    except Exception as e:
        logger.error(f"❌ Database manager initialization failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        logger.warning("⚠️ App will continue but database features may not work")
    
    # Initialize Google Drive manager (optional)
    try:
        drive_manager = get_drive_manager()
        
        # Check if authenticated (don't block startup if not)
        try:
            if drive_manager.is_authenticated():
                # Ensure Google Drive folder exists
                folder_id = drive_manager.ensure_folder_exists()
                settings.GOOGLE_DRIVE_FOLDER_ID = folder_id
                logger.info(f"✅ Google Drive folder: {folder_id}")
                
                # Download database on startup
                local_db_path = os.path.join(settings.LOCAL_CACHE_DIR, settings.DB_FILENAME)
                logger.info(f"📥 Downloading database from Google Drive...")
                downloaded = drive_manager.download_database(local_db_path)
                
                if downloaded:
                    logger.info("✅ Database downloaded successfully")
                else:
                    logger.info("ℹ️ No existing database found, will create new one on first refresh")
            else:
                logger.warning("⚠️ Google Drive not authenticated - authorization required")
                logger.info("ℹ️ Use /api/admin/drive/authorize endpoint to get authorization URL")
                logger.info("ℹ️ App will work, but Google Drive features require authorization")
        except Exception as e:
            logger.warning(f"⚠️ Google Drive initialization error (non-blocking): {e}")
            logger.info("ℹ️ App will continue without Google Drive features")
    except Exception as e:
        logger.warning(f"⚠️ Google Drive manager creation failed (non-blocking): {e}")
        logger.info("ℹ️ App will continue without Google Drive features")
    
    # Initialize scheduler (optional)
    try:
        scheduler = RefreshScheduler(refresh_callback)
        refresh.set_scheduler(scheduler)
        
        if settings.AUTO_REFRESH_ENABLED:
            await scheduler.start()
            logger.info(f"✅ Auto-refresh scheduler started (every 60 minutes between 8:00 AM and 6:00 PM)")
        else:
            logger.info("ℹ️ Auto-refresh is disabled")
    except Exception as e:
        logger.warning(f"⚠️ Scheduler initialization failed (non-blocking): {e}")
        logger.info("ℹ️ App will continue without scheduled refresh")
    
    logger.info("✅ Application startup complete - app is ready to serve requests")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down PharmaStock Web Application")
    if scheduler:
        await scheduler.stop()

# Create FastAPI app
app = FastAPI(
    title="PharmaStock Web Application",
    description="Pharmaceutical Inventory Management System - Web Edition",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    logger.info(f"✅ Static files mounted from: {static_dir}")
else:
    logger.warning(f"⚠️ Static directory not found: {static_dir}")

# Templates
templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=templates_dir)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(stock_view.router, prefix="/api/stock", tags=["Stock View"])
app.include_router(refresh.router, prefix="/api/refresh", tags=["Data Refresh"])
app.include_router(credentials.router, prefix="/api/credentials", tags=["Credentials"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(procurement.router, prefix="/api/procurement", tags=["Procurement"])
app.include_router(suppliers.router, prefix="/api/suppliers", tags=["Suppliers"])

@app.get("/health")
async def health_check():
    """Health check endpoint for Render"""
    try:
        # Test database connection
        db_manager = get_db_manager()
        db_info = db_manager.get_database_info()
        return {
            "status": "ok", 
            "message": "PharmaStock Web App is running",
            "database": {
                "exists": db_info.get("exists", False),
                "path": db_info.get("path", "unknown")
            }
        }
    except Exception as e:
        return {
            "status": "degraded",
            "message": "PharmaStock Web App is running but some services may be unavailable",
            "error": str(e)
        }

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root endpoint - redirect to login"""
    # No authentication required for login page
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Dashboard page - authentication handled client-side"""
    # Don't require authentication at route level - let frontend handle it
    # This allows the page to load and then redirect if needed
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "current_user": None  # Will be loaded client-side
    })

@app.get("/stock-view", response_class=HTMLResponse)
async def stock_view_page(request: Request):
    """Stock view page - authentication handled client-side"""
    return templates.TemplateResponse("stock_view.html", {
        "request": request,
        "current_user": None
    })

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings page - authentication handled client-side"""
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "current_user": None
    })

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Admin page - authentication handled client-side"""
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "current_user": None
    })

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        db_manager = get_db_manager()
        db_info = db_manager.get_database_info()
        
        drive_manager = get_drive_manager()
        drive_info = drive_manager.get_database_info()
        
        scheduler_status = scheduler.get_status() if scheduler else {"enabled": False}
        
        return {
            "status": "healthy",
            "version": "2.0.0",
            "database": {
                "local_exists": db_info.get("exists", False),
                "size_mb": db_info.get("size_mb", 0)
            },
            "google_drive": {
                "exists": drive_info.get("exists", False),
                "size_mb": drive_info.get("size_mb", 0),
                "modified": drive_info.get("modified")
            },
            "scheduler": scheduler_status
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e)
        }

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )

