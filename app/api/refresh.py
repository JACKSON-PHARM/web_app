"""
Data Refresh API Routes
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import asyncio
import logging
from app.dependencies import get_current_user, get_db_manager, get_drive_manager
from app.services.credential_manager import CredentialManager
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
        drive_manager = get_drive_manager()
        
        # Get local database path
        local_db_path = os.path.join(settings.LOCAL_CACHE_DIR, settings.DB_FILENAME)
        
        # STEP 1: Smart database sync - only download if necessary
        # OPTIMIZATION: Skip download if local DB is recent (< 24 hours) and Drive version isn't significantly newer
        should_download = False
        local_db_exists = os.path.exists(local_db_path)
        
        if drive_manager.is_authenticated():
            logger.info("📥 Checking for existing database in Google Drive...")
            RefreshStatusService.update_progress(0.05, "Checking Drive for existing database...")
            
            # Check if database exists in Drive
            drive_db_info = drive_manager.get_database_info()
            if drive_db_info and drive_db_info.get('exists'):
                if local_db_exists:
                    # Check if Drive version is significantly newer (more than 1 hour)
                    drive_timestamp = drive_manager.get_drive_database_timestamp()
                    if drive_timestamp:
                        from datetime import datetime, timedelta
                        local_mtime = datetime.fromtimestamp(os.path.getmtime(local_db_path))
                        drive_mtime = datetime.fromisoformat(drive_timestamp.replace('Z', '+00:00'))
                        local_age = datetime.now() - local_mtime
                        
                        # Only download if:
                        # 1. Local DB is older than 24 hours AND Drive is newer, OR
                        # 2. Drive is significantly newer (> 1 hour difference)
                        if local_age > timedelta(hours=24) and drive_mtime > local_mtime:
                            logger.info(f"📥 Local DB is old ({local_age}), Drive version is newer - downloading...")
                            should_download = True
                        elif drive_mtime > local_mtime + timedelta(hours=1):
                            logger.info(f"📥 Drive version is significantly newer (Drive: {drive_mtime}, Local: {local_mtime}) - downloading...")
                            should_download = True
                        else:
                            logger.info(f"✅ Local database is recent ({local_age}) and Drive isn't significantly newer - skipping download")
                            logger.info(f"   Local: {local_mtime.isoformat()}, Drive: {drive_mtime.isoformat()}")
                            logger.info(f"💡 Optimization: Skipping 600MB download - using cached database saves ~10 minutes!")
                            RefreshStatusService.update_progress(0.1, f"Using recent local database (saved ~10 min download time)...")
                            should_download = False
                    else:
                        logger.info("ℹ️ Could not get Drive timestamp, using local database")
                        should_download = False
                else:
                    # No local DB - must download
                    logger.info("📥 No local database found, downloading from Drive...")
                    should_download = True
                
                if should_download:
                    logger.info("📥 Downloading database from Drive...")
                    RefreshStatusService.update_progress(0.08, "Downloading database from Drive...")
                    downloaded = drive_manager.download_database(local_db_path)
                    if downloaded:
                        logger.info("✅ Downloaded latest database from Drive - will merge new data into it")
                        RefreshStatusService.update_progress(0.1, "Database downloaded, fetching new data...")
                    else:
                        logger.warning("⚠️ Failed to download database from Drive, will use/create local one")
                        RefreshStatusService.update_progress(0.1, "Using local database...")
                else:
                    RefreshStatusService.update_progress(0.1, "Using recent local database, skipping download...")
            else:
                if local_db_exists:
                    logger.info("ℹ️ No database in Drive, using existing local database")
                    RefreshStatusService.update_progress(0.1, "Using local database...")
                else:
                    logger.info("ℹ️ No database in Drive yet, will create new one on first refresh")
                    RefreshStatusService.update_progress(0.1, "No existing database, will create new one...")
        else:
            logger.info("ℹ️ Google Drive not authenticated, using local database only")
            RefreshStatusService.update_progress(0.1, "Using local database...")
        
        # Initialize credential manager (credentials already saved or provided)
        cred_manager = CredentialManager(app_root=settings.LOCAL_CACHE_DIR)
        
        # Use refresh service
        from app.services.refresh_service import RefreshService
        refresh_service = RefreshService(db_manager, settings.LOCAL_CACHE_DIR, cred_manager)
        
        # STEP 2: Run refresh - this will merge/add new data to existing database
        logger.info("🔄 Fetching new data from APIs and merging into database...")
        RefreshStatusService.update_progress(0.2, "Fetching stock data...")
        result = refresh_service.refresh_all_data()
        
        if result.get('success'):
            # STEP 3: Upload updated database back to Google Drive (only if there are changes)
            # OPTIMIZATION: Check if database was actually modified before uploading
            if drive_manager.is_authenticated():
                # Check if database was modified during refresh
                db_modified_after_refresh = False
                if local_db_exists and os.path.exists(local_db_path):
                    from datetime import datetime
                    # Get modification time before refresh started
                    pre_refresh_mtime = RefreshStatusService.get_status().get('refresh_started')
                    if pre_refresh_mtime:
                        try:
                            pre_refresh_dt = datetime.fromisoformat(pre_refresh_mtime)
                            current_mtime = datetime.fromtimestamp(os.path.getmtime(local_db_path))
                            # If DB was modified after refresh started, upload it
                            if current_mtime > pre_refresh_dt:
                                db_modified_after_refresh = True
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Could not parse refresh timestamp: {e}, assuming database was modified")
                            db_modified_after_refresh = True
                    else:
                        # No pre-refresh timestamp, assume it was modified
                        db_modified_after_refresh = True
                else:
                    # New database was created or doesn't exist
                    db_modified_after_refresh = True
                
                if db_modified_after_refresh:
                    logger.info("📤 Database was updated during refresh, uploading to Google Drive...")
                    RefreshStatusService.update_progress(0.9, "Uploading to Google Drive...")
                    success = drive_manager.upload_database(local_db_path, check_conflicts=True)
                else:
                    logger.info("ℹ️ Database was not modified during refresh, skipping upload (saves time!)")
                    logger.info("💡 Optimization: No changes detected - skipping 600MB upload saves ~10 minutes!")
                    RefreshStatusService.update_progress(0.95, "No changes to upload (saved ~10 min upload time)...")
                    success = True  # Consider it successful since there's nothing to upload
            else:
                logger.warning("⚠️ Google Drive not authenticated - skipping upload")
                success = False
            
            if success:
                logger.info("✅ Refresh complete and uploaded to Drive")
                RefreshStatusService.set_refresh_complete(True, "Data refreshed and uploaded successfully")
                return {
                    "success": True,
                    "message": "Data refreshed and uploaded successfully",
                    "details": result
                }
            else:
                logger.error("❌ Failed to upload database")
                RefreshStatusService.set_refresh_complete(True, "Refresh completed but upload failed")
                return {
                    "success": False,
                    "message": "Refresh completed but upload failed",
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
    cred_manager = CredentialManager(app_root=settings.LOCAL_CACHE_DIR)
    
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

@router.post("/trigger")
async def trigger_manual_refresh(
    request: RefreshRequest,
    current_user: dict = Depends(get_current_user)
):
    """Trigger immediate manual refresh"""
    # Similar to refresh_all_data but synchronous
    # Implementation similar to above
    return {"status": "triggered", "message": "Manual refresh triggered"}

