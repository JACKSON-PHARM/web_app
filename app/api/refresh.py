"""
Data Refresh API Routes
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
import asyncio
import logging
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
        refresh_service = RefreshService(db_manager, settings.LOCAL_CACHE_DIR, cred_manager)
        
        # Run refresh - fetch new data from APIs and save to Supabase/PostgreSQL
        logger.info("🔄 Fetching new data from APIs and saving to database...")
        RefreshStatusService.update_progress(0.1, "Connecting to Supabase database...")
        result = refresh_service.refresh_all_data()
        
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
    
    return {
        "is_refreshing": status.get("is_refreshing", False),
        "last_refresh": status.get("last_refresh"),
        "refresh_started": status.get("refresh_started"),
        "refresh_progress": status.get("refresh_progress"),
        "refresh_message": status.get("refresh_message"),
        "data_age": data_age,
        "scheduler": _scheduler.get_status() if _scheduler else {
            "enabled": False,
            "is_running": False,
            "message": "Scheduler not initialized"
        }
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
    Runs in background and refreshes materialized views after completion
    """
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
    
    # Run refresh in background with fetcher selection
    background_tasks.add_task(run_refresh_task_with_fetchers, request.fetchers)
    
    fetcher_list = request.fetchers if request.fetchers else "all"
    return {
        "status": "started",
        "message": f"Data refresh started for fetchers: {fetcher_list}. Database will be updated when complete.",
        "fetchers": fetcher_list,
        "last_refresh": None
    }

async def run_refresh_task_with_fetchers(fetchers: Optional[List[str]] = None):
    """Background task to run refresh with optional fetcher selection"""
    RefreshStatusService.set_refreshing(True, f"Starting data refresh for fetchers: {fetchers or 'all'}...")
    
    try:
        db_manager = get_db_manager()
        cred_manager = get_credential_manager()
        
        # Use refresh service
        from app.services.refresh_service import RefreshService
        refresh_service = RefreshService(db_manager, settings.LOCAL_CACHE_DIR, cred_manager)
        
        # Run refresh with fetcher selection
        logger.info(f"🔄 Fetching data from APIs for fetchers: {fetchers or 'all'}...")
        RefreshStatusService.update_progress(0.1, f"Connecting to database and starting fetchers: {fetchers or 'all'}...")
        
        if fetchers:
            # Run specific fetchers
            result = refresh_service.refresh_selected_data(fetchers)
        else:
            # Run all fetchers
            result = refresh_service.refresh_all_data()
        
        if result.get('success'):
            logger.info("✅ Data refresh complete - all changes saved to database")
            RefreshStatusService.update_progress(1.0, "Refresh complete!")
            RefreshStatusService.set_refresh_complete(True, "Data refreshed successfully")
            return {
                "success": True,
                "message": "Data refreshed successfully - all changes saved to database",
                "details": result,
                "fetchers": fetchers or "all"
            }
        else:
            logger.error(f"❌ Refresh failed: {result.get('error', 'Unknown error')}")
            RefreshStatusService.set_refresh_complete(False, result.get('error', 'Unknown error'))
            return {
                "success": False,
                "message": result.get('error', 'Unknown error'),
                "details": result,
                "fetchers": fetchers or "all"
            }
            
    except Exception as e:
        logger.error(f"❌ Error in refresh task: {e}")
        import traceback
        logger.error(traceback.format_exc())
        RefreshStatusService.set_refresh_complete(False, str(e))
        return {"success": False, "message": str(e), "fetchers": fetchers or "all"}

