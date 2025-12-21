"""
Admin API Routes
"""
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import json
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
    import os
    logger = logging.getLogger(__name__)
    
    # Force authentication check before getting info
    logger.info(f"🔍 Checking authentication status...")
    is_auth = drive_manager.is_authenticated()
    logger.info(f"🔍 Authentication status: {is_auth}")
    logger.info(f"🔍 Service is None: {drive_manager.service is None}")
    
    info = drive_manager.get_database_info()
    logger.info(f"🔍 Database info result: {info.get('error', 'No error')}")
    
    # Add local database info for comparison
    local_db_path = os.path.join(settings.LOCAL_CACHE_DIR, settings.DB_FILENAME)
    local_db_exists = os.path.exists(local_db_path)
    info['local_database'] = {
        'exists': local_db_exists,
        'path': local_db_path,
        'size_mb': round(os.path.getsize(local_db_path) / (1024 * 1024), 2) if local_db_exists else 0,
        'modified': os.path.getmtime(local_db_path) if local_db_exists else None
    }
    
    # Check sync status
    if is_auth and info.get('exists') and local_db_exists:
        drive_timestamp = drive_manager.get_drive_database_timestamp()
        if drive_timestamp:
            from datetime import datetime
            local_mtime = datetime.fromtimestamp(os.path.getmtime(local_db_path))
            drive_mtime = datetime.fromisoformat(drive_timestamp.replace('Z', '+00:00'))
            info['sync_status'] = {
                'is_synced': drive_mtime <= local_mtime,
                'drive_newer': drive_mtime > local_mtime,
                'drive_timestamp': drive_timestamp,
                'local_timestamp': local_mtime.isoformat()
            }
    
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
    import os
    try:
        auth_url = drive_manager.get_authorization_url()
        return {
            "success": True,
            "authorization_url": auth_url,
            "callback_url": settings.GOOGLE_OAUTH_CALLBACK_URL,
            "message": "Visit this URL to authorize Google Drive access. After authorization, you'll be redirected back.",
            "instructions": "1. Copy the authorization_url\n2. Visit it in your browser\n3. Sign in with 2\n4. Authorize the app\n5. You'll be redirected back automatically"
        }
    except FileNotFoundError as e:
        # Provide helpful error message for missing credentials
        creds_path = settings.GOOGLE_CREDENTIALS_FILE
        error_msg = str(e)
        if "google_credentials.json" in error_msg.lower():
            error_msg = (
                f"Google credentials file not found.\n\n"
                f"To fix this:\n"
                f"1. Download your OAuth 2.0 credentials from Google Cloud Console\n"
                f"2. Name the file 'google_credentials.json'\n"
                f"3. Upload it via the admin panel (upload feature) OR\n"
                f"4. Set GOOGLE_CREDENTIALS_JSON environment variable in Render with the file contents\n\n"
                f"Expected location: {creds_path}"
            )
        raise HTTPException(status_code=404, detail=error_msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/drive/files")
async def list_database_files(
    current_user: dict = Depends(get_current_admin),
    drive_manager = Depends(get_drive_manager)
):
    """List all database files in Google Drive (admin only)"""
    if not drive_manager.is_authenticated():
        return {
            "success": False,
            "message": "Google Drive not authenticated",
            "files": []
        }
    
    files = drive_manager.list_all_database_files()
    return {
        "success": True,
        "files": files,
        "count": len(files)
    }

@router.delete("/drive/files/{file_id}")
async def delete_database_file(
    file_id: str,
    current_user: dict = Depends(get_current_admin),
    drive_manager = Depends(get_drive_manager)
):
    """Delete a specific database file from Google Drive (admin only)"""
    if not drive_manager.is_authenticated():
        return {
            "success": False,
            "message": "Google Drive not authenticated"
        }
    
    success = drive_manager.delete_database_file(file_id)
    if success:
        return {
            "success": True,
            "message": f"Database file deleted successfully"
        }
    else:
        return {
            "success": False,
            "message": "Failed to delete database file"
        }

@router.post("/drive/cleanup")
async def cleanup_old_database_files(
    request: Request,
    current_user: dict = Depends(get_current_admin),
    drive_manager = Depends(get_drive_manager)
):
    """Clean up old database files, keeping only the most recent N files (admin only)"""
    if not drive_manager.is_authenticated():
        return {
            "success": False,
            "message": "Google Drive not authenticated"
        }
    
    try:
        body = await request.json()
        keep_count = body.get('keep_count', 2)
    except:
        keep_count = 2
    
    if keep_count < 1:
        keep_count = 1
    if keep_count > 5:
        keep_count = 5  # Safety limit
    
    result = drive_manager.cleanup_old_database_files(keep_count=keep_count)
    return result

@router.post("/drive/upload-credentials")
async def upload_credentials(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_admin)
):
    """Upload Google credentials file (admin only)"""
    from app.config import settings
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Validate file name
        if file.filename != "google_credentials.json":
            raise HTTPException(
                status_code=400, 
                detail="File must be named 'google_credentials.json'"
            )
        
        # Read file contents
        contents = await file.read()
        
        # Validate JSON
        try:
            creds_data = json.loads(contents)
            # Validate it has required fields
            if "web" not in creds_data and "installed" not in creds_data:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid credentials file. Must contain 'web' or 'installed' section."
                )
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Invalid JSON file"
            )
        
        # Save to credentials file location
        creds_path = settings.GOOGLE_CREDENTIALS_FILE
        os.makedirs(os.path.dirname(creds_path), exist_ok=True)
        
        with open(creds_path, 'wb') as f:
            f.write(contents)
        
        logger.info(f"✅ Credentials file uploaded successfully to: {creds_path}")
        
        return {
            "success": True,
            "message": "Credentials file uploaded successfully. You can now use 'Get Authorization URL' to authorize Google Drive access.",
            "path": creds_path
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading credentials: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error uploading credentials: {str(e)}")

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
        return {
            "success": False, 
            "message": (
                "Database not found in Google Drive.\n\n"
                "To fix this:\n"
                "1. Go to Settings and configure API credentials (NILA/DAIMA)\n"
                "2. Click 'Refresh Now' to fetch data from APIs (this creates a database)\n"
                "3. Then click 'Upload to Drive' to upload the database\n"
                "4. After that, you can download it anytime"
            )
        }

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

