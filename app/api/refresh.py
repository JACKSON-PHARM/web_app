"""
Data Refresh API Routes
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body
from pydantic import BaseModel
from typing import Optional, List
import asyncio
import logging
from datetime import datetime
from app.dependencies import get_current_user, get_db_manager
from app.dependencies import get_credential_manager
from app.services.fetcher_manager import FetcherManager
from app.services.scheduler import RefreshScheduler
from app.services.refresh_status import RefreshStatusService
from app.config import settings
import os

router = APIRouter()
logger = logging.getLogger(__name__)

class RefreshRequest(BaseModel):
    nila_username: Optional[str] = None
    nila_password: Optional[str] = None
    daima_username: Optional[str] = None
    daima_password: Optional[str] = None

class RefreshStatus(BaseModel):
    status: str
    message: str
    last_refresh: Optional[str] = None

# Global scheduler instance (will be initialized in main.py)
_scheduler: Optional[RefreshScheduler] = None

def set_scheduler(scheduler: RefreshScheduler):
    """Set the global scheduler instance"""
    global _scheduler
    _scheduler = scheduler

async def run_refresh_task():
    """Background task to run refresh and upload"""
    RefreshStatusService.set_refreshing(True, "Starting data refresh...")
    
    try:
        db_manager = get_db_manager()
        
        # Initialize credential manager (credentials already saved or provided)
        cred_manager = get_credential_manager()
        
        # Use refresh service
        from app.services.refresh_service import RefreshService
        # Get actual app root directory (parent of app directory, contains both app/ and scripts/)
        # __file__ is app/api/refresh.py, so we need to go up 2 levels to get to the root
        app_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        refresh_service = RefreshService(db_manager, app_root, cred_manager)
        
        # Run refresh - fetch new data from APIs and save to Supabase/PostgreSQL
        logger.info("🔄 Fetching new data from APIs and saving to database...")
        logger.info(f"   This is a long-running task that may take 10-30 minutes")
        logger.info(f"   Progress will be logged here and available via /api/refresh/status")
        RefreshStatusService.update_progress(0.1, "Connecting to Supabase database...")
        result = refresh_service.refresh_all_data()
        logger.info(f"   Refresh service returned: success={result.get('success')}")
        
        if result.get('success'):
            # Data refresh complete - Supabase automatically persists all changes
            logger.info("✅ Data refresh complete - all changes saved to database")
            RefreshStatusService.update_progress(1.0, "Refresh complete!")
            RefreshStatusService.set_refresh_complete(True, "Data refreshed successfully")
            return {
                "success": True,
                "message": "Data refreshed successfully - all changes saved to database",
                "details": result
            }
        else:
            logger.error(f"❌ Refresh failed: {result.get('error', 'Unknown error')}")
            RefreshStatusService.set_refresh_complete(False, result.get('error', 'Unknown error'))
            return {
                "success": False,
                "message": result.get('error', 'Unknown error'),
                "details": result
            }
            
    except Exception as e:
        logger.error(f"❌ Error in refresh task: {e}")
        import traceback
        logger.error(traceback.format_exc())
        RefreshStatusService.set_refresh_complete(False, str(e))
        return {"success": False, "message": str(e)}

@router.post("/all", response_model=RefreshStatus)
async def refresh_all_data(
    request: RefreshRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Trigger full data refresh - uses saved credentials if available, otherwise uses provided credentials"""
    
    # Get database and credential managers
    db_manager = get_db_manager()
    cred_manager = get_credential_manager()
    
    # Check if credentials are saved
    nila_creds = cred_manager.get_credentials("NILA")
    daima_creds = cred_manager.get_credentials("DAIMA")
    
    # Use provided credentials if given, otherwise use saved ones
    has_nila = (request.nila_username and request.nila_password) or (nila_creds and nila_creds.get('username') and nila_creds.get('password'))
    has_daima = (request.daima_username and request.daima_password) or (daima_creds and daima_creds.get('username') and daima_creds.get('password'))
    
    # Validate that at least one set of credentials is available
    if not has_nila and not has_daima:
        raise HTTPException(
            status_code=400,
            detail="No credentials available. Please configure credentials in Settings first or provide them in the request."
        )
    
    # Save user credentials if provided (will overwrite saved ones)
    if request.nila_username and request.nila_password:
        cred_manager.save_credentials(
            "NILA",
            request.nila_username,
            request.nila_password,
            settings.NILA_API_URL
        )
    
    if request.daima_username and request.daima_password:
        cred_manager.save_credentials(
            "DAIMA",
            request.daima_username,
            request.daima_password,
            settings.DAIMA_API_URL
        )
    
    # Run refresh in background
    background_tasks.add_task(run_refresh_task)
    
    return {
        "status": "started",
        "message": "Data refresh started. Database will be updated when complete.",
        "last_refresh": None
    }

@router.get("/status")
async def get_refresh_status(current_user: dict = Depends(get_current_user)):
    """Get refresh status including data freshness"""
    status = RefreshStatusService.get_status()
    data_age = RefreshStatusService.get_data_age()
    
    # Get scheduler status with more details
    scheduler_status = {}
    if _scheduler:
        try:
            scheduler_status = _scheduler.get_status()
            scheduler_status["enabled"] = getattr(_scheduler, 'enabled', True)
            scheduler_status["is_running"] = getattr(_scheduler, 'is_running', False)
            scheduler_status["last_refresh"] = _scheduler.last_refresh.isoformat() if _scheduler.last_refresh else None
            scheduler_status["next_refresh"] = _scheduler.next_refresh.isoformat() if _scheduler.next_refresh else None
        except Exception as e:
            logger.error(f"Error getting scheduler status: {e}")
            scheduler_status = {
                "enabled": False,
                "is_running": False,
                "message": f"Scheduler error: {str(e)}"
            }
    else:
        scheduler_status = {
            "enabled": False,
            "is_running": False,
            "message": "Scheduler not initialized"
        }
    
    return {
        "is_refreshing": status.get("is_refreshing", False),
        "last_refresh": status.get("last_refresh"),
        "refresh_started": status.get("refresh_started"),
        "refresh_progress": status.get("refresh_progress"),
        "refresh_message": status.get("refresh_message"),
        "data_age": data_age,
        "scheduler": scheduler_status
    }

class TriggerRefreshRequest(BaseModel):
    """Request model for trigger refresh endpoint"""
    fetchers: Optional[List[str]] = None  # List of fetcher names: ['stock', 'grn', 'orders', 'supplier_invoices'] or None for all
    nila_username: Optional[str] = None
    nila_password: Optional[str] = None
    daima_username: Optional[str] = None
    daima_password: Optional[str] = None

@router.post("/trigger")
async def trigger_manual_refresh(
    request: TriggerRefreshRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Trigger manual refresh - can run specific fetchers or all fetchers
    Runs in background and updates database with fresh data
    If empty body {} is sent, all fields will be None and all fetchers will run
    """
    try:
        # Log immediately with clear markers for Render logs
        logger.info("=" * 80)
        logger.info("🔄 REFRESH TRIGGER ENDPOINT CALLED")
        logger.info(f"   Timestamp: {datetime.now().isoformat()}")
        logger.info(f"   User: {current_user.get('username', 'unknown') if current_user else 'unknown'}")
        logger.info(f"   Request: fetchers={request.fetchers}, has_nila_creds={bool(request.nila_username)}, has_daima_creds={bool(request.daima_username)}")
        logger.info("=" * 80)
        
        # Get database and credential managers
        db_manager = get_db_manager()
        cred_manager = get_credential_manager()
        logger.info("✅ Database and credential managers initialized")
        
        # Check if credentials are saved
        nila_creds = cred_manager.get_credentials("NILA")
        daima_creds = cred_manager.get_credentials("DAIMA")
        
        # Use provided credentials if given, otherwise use saved ones
        has_nila = (request.nila_username and request.nila_password) or (nila_creds and nila_creds.get('username') and nila_creds.get('password'))
        has_daima = (request.daima_username and request.daima_password) or (daima_creds and daima_creds.get('username') and daima_creds.get('password'))
        
        # Validate that at least one set of credentials is available
        if not has_nila and not has_daima:
            logger.error("❌ No credentials available for refresh")
            raise HTTPException(
                status_code=400,
                detail="No credentials available. Please configure credentials in Settings first or provide them in the request."
            )
        
        # Save user credentials if provided (will overwrite saved ones)
        if request.nila_username and request.nila_password:
            cred_manager.save_credentials(
                "NILA",
                request.nila_username,
                request.nila_password,
                settings.NILA_API_URL
            )
            logger.info("✅ Saved NILA credentials from request")
        
        if request.daima_username and request.daima_password:
            cred_manager.save_credentials(
                "DAIMA",
                request.daima_username,
                request.daima_password,
                settings.DAIMA_API_URL
            )
            logger.info("✅ Saved DAIMA credentials from request")
        
        # Determine which fetchers to run
        fetchers_to_run = request.fetchers if request.fetchers else None  # None means all fetchers
        fetcher_list = request.fetchers if request.fetchers else "all"
        
        logger.info(f"🔄 Triggering manual refresh for fetchers: {fetcher_list}")
        logger.info(f"   Using saved credentials: NILA={bool(nila_creds)}, DAIMA={bool(daima_creds)}")
        
        # Run refresh in background with fetcher selection
        logger.info(f"🚀 Adding background task for fetchers: {fetcher_list}")
        logger.info(f"   Task will run asynchronously - check logs for progress")
        background_tasks.add_task(run_refresh_task_with_fetchers, fetchers_to_run)
        logger.info("✅ Background task added successfully - refresh will start shortly")
        logger.info(f"   Monitor progress via /api/refresh/status endpoint")
        
        response_data = {
            "status": "started",
            "success": True,
            "message": f"Data refresh started for fetchers: {fetcher_list}. Database will be updated when complete.",
            "fetchers": fetcher_list,
            "last_refresh": None
        }
        logger.info(f"✅ Returning response: {response_data}")
        return response_data
    except HTTPException:
        # Re-raise HTTP exceptions (like 400 for missing credentials)
        raise
    except Exception as e:
        logger.error(f"❌ Error in trigger_manual_refresh: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger refresh: {str(e)}"
        )

async def run_refresh_task_with_fetchers(fetchers: Optional[List[str]] = None):
    """Background task to run refresh with optional fetcher selection"""
    fetcher_list = fetchers if fetchers else "all"
    
    # Log immediately to ensure visibility in Render logs
    logger.info("=" * 80)
    logger.info("🔄 REFRESH TASK STARTED")
    logger.info(f"   Fetchers: {fetcher_list}")
    logger.info(f"   Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 80)
    
    RefreshStatusService.set_refreshing(True, f"Starting data refresh for fetchers: {fetcher_list}...")
    
    try:
        logger.info(f"🔄 Starting refresh task for fetchers: {fetcher_list}")
        logger.info(f"   Getting database and credential managers...")
        db_manager = get_db_manager()
        cred_manager = get_credential_manager()
        logger.info(f"   ✅ Database and credential managers obtained")
        
        # Use refresh service
        from app.services.refresh_service import RefreshService
        # Get actual app root directory (parent of app directory, contains both app/ and scripts/)
        # __file__ is app/api/refresh.py, so we need to go up 2 levels to get to the root
        app_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        refresh_service = RefreshService(db_manager, app_root, cred_manager)
        
        # Run refresh with fetcher selection
        logger.info(f"🔄 Fetching data from APIs for fetchers: {fetcher_list}...")
        logger.info("   This will download current stock, orders, and supplier invoices incrementally")
        RefreshStatusService.update_progress(0.1, f"Connecting to database and starting fetchers: {fetcher_list}...")
        
        if fetchers:
            # Run specific fetchers
            logger.info(f"📋 Running selected fetchers: {fetchers}")
            result = refresh_service.refresh_selected_data(fetchers)
        else:
            # Run all fetchers (incremental - only fetches new data)
            logger.info("📋 Running all fetchers (incremental mode - only new data will be fetched)")
            result = refresh_service.refresh_all_data()
        
        if result.get('success'):
            summary = result.get('summary', {})
            messages = result.get('messages', [])
            
            logger.info("=" * 80)
            logger.info("✅ REFRESH TASK COMPLETED SUCCESSFULLY")
            logger.info(f"   Timestamp: {datetime.now().isoformat()}")
            logger.info(f"   Fetchers: {fetcher_list}")
            logger.info(f"   Summary: {summary}")
            logger.info(f"   Messages: {messages}")
            logger.info("=" * 80)
            RefreshStatusService.update_progress(1.0, "Refresh complete!")
            RefreshStatusService.set_refresh_complete(True, "Data refreshed successfully")
            
            return {
                "success": True,
                "message": "Data refreshed successfully - all changes saved to database",
                "details": result,
                "fetchers": fetcher_list,
                "summary": summary,
                "messages": messages
            }
        else:
            error_msg = result.get('error', result.get('message', 'Unknown error'))
            logger.error(f"❌ Refresh failed: {error_msg}")
            RefreshStatusService.set_refresh_complete(False, error_msg)
            return {
                "success": False,
                "message": error_msg,
                "details": result,
                "fetchers": fetcher_list
            }
            
    except Exception as e:
        logger.error("=" * 80)
        logger.error("❌ REFRESH TASK FAILED")
        logger.error(f"   Timestamp: {datetime.now().isoformat()}")
        logger.error(f"   Fetchers: {fetcher_list}")
        logger.error(f"   Error: {e}")
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"   Traceback:\n{error_traceback}")
        logger.error("=" * 80)
        RefreshStatusService.set_refresh_complete(False, str(e))
        return {
            "success": False, 
            "message": str(e),
            "fetchers": fetcher_list,
            "traceback": error_traceback
        }

