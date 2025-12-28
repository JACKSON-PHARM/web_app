"""
FastAPI Main Application
PharmaStock Web Application Entry Point
"""
import os
import sys

# Add scripts directory to Python path BEFORE any other imports
# This ensures scripts module can be imported by app.services modules
app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
scripts_dir = os.path.join(app_root, 'scripts')
if os.path.exists(scripts_dir):
    if app_root not in sys.path:
        sys.path.insert(0, app_root)

from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging

from app.config import settings
from app.services.license_service import LicenseService
from app.services.scheduler import RefreshScheduler
from app.api import auth, dashboard, stock_view, refresh, credentials, admin, procurement, suppliers, diagnostics, materialized_views
from app.dependencies import get_db_manager, get_current_user

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
    
    # Initialize database manager (Supabase PostgreSQL ONLY)
    try:
        db_manager = get_db_manager()
        logger.info("✅ Database manager initialized")
        
        # Verify database connection (PostgreSQL/Supabase)
        if hasattr(db_manager, 'pool'):
            logger.info("📊 Connected to Supabase PostgreSQL database")
            try:
                conn = db_manager.get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM current_stock")
                stock_count = cursor.fetchone()[0]
                logger.info(f"📋 Found {stock_count:,} stock records in database")
                cursor.close()
                db_manager.put_connection(conn)
            except Exception as e:
                logger.warning(f"⚠️ Could not verify database contents: {e}")
    except Exception as e:
        logger.error(f"❌ Database manager initialization failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        logger.warning("⚠️ App will continue but database features may not work")
    
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
app.include_router(diagnostics.router, prefix="/api/diagnostics", tags=["Diagnostics"])
app.include_router(materialized_views.router, prefix="/api/materialized-views", tags=["Materialized Views"])

@app.get("/health")
async def health_check():
    """Health check endpoint for Render - checks database, materialized views, and scheduler"""
    health_status = {
        "status": "ok",
        "message": "PharmaStock Web App is running",
        "timestamp": None,
        "database": {
            "type": "Supabase PostgreSQL",
            "connected": False,
            "error": None
        },
        "materialized_views": {
            "stock_view_materialized": False,
            "priority_items_materialized": False
        },
        "scheduler": {
            "enabled": settings.AUTO_REFRESH_ENABLED,
            "running": False
        }
    }
    
    from datetime import datetime
    health_status["timestamp"] = datetime.now().isoformat()
    
    # Check database connection
    try:
        db_manager = get_db_manager()
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        db_manager.put_connection(conn)
        health_status["database"]["connected"] = True
        
        # Check materialized views
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT matviewname 
                FROM pg_matviews 
                WHERE schemaname = 'public' 
                AND matviewname IN ('stock_view_materialized', 'priority_items_materialized')
            """)
            views = [row[0] for row in cursor.fetchall()]
            health_status["materialized_views"]["stock_view_materialized"] = "stock_view_materialized" in views
            health_status["materialized_views"]["priority_items_materialized"] = "priority_items_materialized" in views
            cursor.close()
            db_manager.put_connection(conn)
        except Exception as mv_error:
            logger.warning(f"Could not check materialized views: {mv_error}")
        
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["database"]["error"] = str(e)
        health_status["message"] = "Database connection failed - some features may be unavailable"
        logger.error(f"Health check database error: {e}")
    
    # Check scheduler status
    try:
        global scheduler
        if scheduler:
            health_status["scheduler"]["running"] = scheduler.is_running() if hasattr(scheduler, 'is_running') else True
    except Exception as sched_error:
        logger.warning(f"Could not check scheduler status: {sched_error}")
    
    # Return appropriate status code
    status_code = 200 if health_status["status"] == "ok" else 503
    return JSONResponse(content=health_status, status_code=status_code)

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

# Duplicate health endpoint removed - using the one above

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )

