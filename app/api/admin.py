"""
Admin API Routes
"""
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from typing import List, Optional
import os
from app.dependencies import get_current_admin, get_drive_manager
from app.services.user_service import UserService

router = APIRouter()
user_service = UserService()

# Templates for OAuth callback
templates_dir = os.path.join(os.path.dirname(__file__), "..", "..", "templates")
templates = Jinja2Templates(directory=templates_dir)

class CreateUserRequest(BaseModel):
    username: str
    password: str
    subscription_days: int
    is_admin: bool = False

class UpdateSubscriptionRequest(BaseModel):
    username: str
    subscription_days: int

@router.post("/users/create")
async def create_user(
    request: CreateUserRequest,
    current_user: dict = Depends(get_current_admin)
):
    """Create a new user (admin only)"""
    success, message = user_service.create_user(
        request.username,
        request.password,
        request.subscription_days,
        current_user["username"],
        request.is_admin
    )
    
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=400, detail=message)

@router.post("/users/update-subscription")
async def update_subscription(
    request: UpdateSubscriptionRequest,
    current_user: dict = Depends(get_current_admin)
):
    """Update user subscription (admin only)"""
    success, message = user_service.update_user_subscription(
        request.username,
        request.subscription_days,
        current_user["username"]
    )
    
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=400, detail=message)

class DeactivateUserRequest(BaseModel):
    username: str

class DeleteUserRequest(BaseModel):
    username: str

@router.post("/users/deactivate")
async def deactivate_user(
    request: DeactivateUserRequest,
    current_user: dict = Depends(get_current_admin)
):
    """Deactivate a user (admin only)"""
    success, message = user_service.deactivate_user(request.username, current_user["username"])
    
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=400, detail=message)

@router.post("/users/activate")
async def activate_user(
    request: DeactivateUserRequest,
    current_user: dict = Depends(get_current_admin)
):
    """Activate a user (admin only)"""
    success, message = user_service.activate_user(request.username, current_user["username"])
    
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=400, detail=message)

@router.post("/users/delete")
async def delete_user(
    request: DeleteUserRequest,
    current_user: dict = Depends(get_current_admin)
):
    """Delete a user (admin only)"""
    if request.username == current_user["username"]:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    success, message = user_service.delete_user(request.username, current_user["username"])
    
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=400, detail=message)

@router.get("/users/list")
async def list_users(current_user: dict = Depends(get_current_admin)):
    """List all users (admin only)"""
    users = user_service.list_users()
    
    return {
        "success": True,
        "users": users
    }

@router.get("/drive/info")
async def get_drive_info(
    current_user: dict = Depends(get_current_admin),
    drive_manager = Depends(get_drive_manager)
):
    """Get Google Drive database info (admin only)"""
    import logging
    from app.config import settings
    logger = logging.getLogger(__name__)
    
    # Force authentication check before getting info
    logger.info(f"🔍 Checking authentication status...")
    is_auth = drive_manager.is_authenticated()
    logger.info(f"🔍 Authentication status: {is_auth}")
    logger.info(f"🔍 Service is None: {drive_manager.service is None}")
    
    info = drive_manager.get_database_info()
    logger.info(f"🔍 Database info result: {info.get('error', 'No error')}")
    
    # Add callback URL to the response
    info['callback_url'] = settings.GOOGLE_OAUTH_CALLBACK_URL
    
    return {
        "success": True,
        "database_info": info
    }

@router.get("/drive/authorize")
async def get_authorization_url(
    current_user: dict = Depends(get_current_admin),
    drive_manager = Depends(get_drive_manager)
):
    """Get Google Drive authorization URL (admin only)"""
    from app.config import settings
    try:
        auth_url = drive_manager.get_authorization_url()
        return {
            "success": True,
            "authorization_url": auth_url,
            "callback_url": settings.GOOGLE_OAUTH_CALLBACK_URL,
            "message": "Visit this URL to authorize Google Drive access. After authorization, you'll be redirected back.",
            "instructions": "1. Copy the authorization_url\n2. Visit it in your browser\n3. Sign in with 2\n4. Authorize the app\n5. You'll be redirected back automatically"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/drive/callback")
async def oauth_callback(
    request: Request,
    code: Optional[str] = None,
    error: Optional[str] = None,
    drive_manager = Depends(get_drive_manager)
):
    """Handle OAuth callback from Google"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Check for errors from Google
    if error:
        logger.error(f"OAuth error from Google: {error}")
        return templates.TemplateResponse("oauth_error.html", {
            "request": request,
            "message": f"Authorization was denied or cancelled. Error: {error}"
        })
    
    if not code:
        logger.error("No authorization code received from Google")
        return templates.TemplateResponse("oauth_error.html", {
            "request": request,
            "message": "No authorization code received. Please try again."
        })
    
    try:
        logger.info(f"🔵 Callback received - Code: {code[:20] if code else 'None'}...")
        logger.info(f"🔵 Callback URL: {request.url}")
        logger.info(f"🔵 Query params: {dict(request.query_params)}")
        
        success = drive_manager.complete_authorization(code)
        if success:
            logger.info("✅ Authorization completed successfully")
            # Redirect back to admin page with success message
            from fastapi.responses import RedirectResponse
            return RedirectResponse(
                url="/admin?authorized=true",
                status_code=303
            )
        else:
            logger.error("❌ Authorization failed - complete_authorization returned False")
            return templates.TemplateResponse("oauth_error.html", {
                "request": request,
                "message": "Authorization failed. Please try again. Check server logs for details."
            })
    except Exception as e:
        logger.error(f"❌ Exception during authorization: {e}")
        import traceback
        error_trace = traceback.format_exc()
        logger.error(error_trace)
        return templates.TemplateResponse("oauth_error.html", {
            "request": request,
            "message": f"Error: {str(e)}\n\nCheck server terminal/console for detailed error logs."
        })

@router.post("/drive/sync")
async def sync_database(
    current_user: dict = Depends(get_current_admin),
    drive_manager = Depends(get_drive_manager)
):
    """Sync database from Google Drive (download) - admin only"""
    if not drive_manager.is_authenticated():
        return {
            "success": False,
            "message": "Google Drive not authenticated. Please authorize first using /api/admin/drive/authorize"
        }
    
    from app.config import settings
    import os
    
    local_db_path = os.path.join(settings.LOCAL_CACHE_DIR, settings.DB_FILENAME)
    success = drive_manager.download_database(local_db_path)
    
    if success:
        return {"success": True, "message": "Database synced from Google Drive"}
    else:
        return {"success": False, "message": "Failed to sync database. Database may not exist in Drive yet - try uploading first."}

@router.post("/drive/upload")
async def upload_database(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_admin),
    drive_manager = Depends(get_drive_manager)
):
    """Upload database to Google Drive (admin only) - runs in background for large files"""
    if not drive_manager.is_authenticated():
        return {
            "success": False,
            "message": "Google Drive not authenticated. Please authorize first using /api/admin/drive/authorize"
        }
    
    from app.config import settings
    import os
    
    local_db_path = os.path.join(settings.LOCAL_CACHE_DIR, settings.DB_FILENAME)
    
    if not os.path.exists(local_db_path):
        return {
            "success": False,
            "message": f"Local database not found at {local_db_path}. Please refresh data first or copy database to cache folder."
        }
    
    db_size_mb = round(os.path.getsize(local_db_path) / (1024 * 1024), 2)
    
    # For large files (>100MB), run in background
    if db_size_mb > 100:
        # Run upload in background
        background_tasks.add_task(drive_manager.upload_database, local_db_path)
        return {
            "success": True,
            "message": f"Upload started in background ({db_size_mb} MB). This may take several minutes. Check server logs for progress.",
            "in_background": True
        }
    else:
        # Small files can be synchronous
        success = drive_manager.upload_database(local_db_path)
        
        if success:
            return {
                "success": True,
                "message": f"Database uploaded to Google Drive successfully ({db_size_mb} MB)"
            }
        else:
            return {"success": False, "message": "Failed to upload database to Google Drive"}

