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
import logging
from app.dependencies import get_current_admin
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

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
    current_user: dict = Depends(get_current_admin)
):
    """Get database info (admin only) - All data is in Supabase PostgreSQL"""
    # ALL data is in Supabase PostgreSQL - no Google Drive or local database
    info = {
        'exists': True,
        'message': 'All data is stored in Supabase PostgreSQL',
        'database_type': 'Supabase PostgreSQL'
    }
    
    # Add local database info
    info['local_database'] = {
        "exists": False,
        "path": None,
        "message": "All data is stored in Supabase PostgreSQL"
    }
    
    # Setup status - all complete since we use Supabase
    setup_status = {
        "database_found": True,
        "database_type": "Supabase PostgreSQL",
        "setup_complete": True,
        "needs_setup": False
    }
    
    # Setup steps - all complete
    setup_steps = [{
        "step": 1,
        "title": "Database Setup",
        "description": "✅ Using Supabase PostgreSQL - All data stored in cloud",
        "completed": True
    }]
    
    return {
        "success": True,
        "database_info": info,
        "setup_status": setup_status,
        "setup_steps": setup_steps
    }

@router.get("/drive/authorize")
async def get_authorization_url(
    current_user: dict = Depends(get_current_admin)
):
    """Google Drive is no longer used - app now uses Supabase PostgreSQL"""
    return {
        "success": False,
        "message": "Google Drive integration has been removed. App now uses Supabase PostgreSQL for data storage."
    }

@router.get("/drive/files")
async def list_database_files(
    current_user: dict = Depends(get_current_admin)
):
    """Google Drive is no longer used - app now uses Supabase PostgreSQL"""
    return {
        "success": False,
        "message": "Google Drive integration has been removed. App now uses Supabase PostgreSQL.",
        "files": []
    }

@router.delete("/drive/files/{file_id}")
async def delete_database_file(
    file_id: str,
    current_user: dict = Depends(get_current_admin)
):
    """Google Drive is no longer used - app now uses Supabase PostgreSQL"""
    return {
        "success": False,
        "message": "Google Drive integration has been removed. App now uses Supabase PostgreSQL."
    }

@router.post("/drive/cleanup")
async def cleanup_old_database_files(
    request: Request,
    current_user: dict = Depends(get_current_admin)
):
    """Google Drive is no longer used - app now uses Supabase PostgreSQL"""
    return {
        "success": False,
        "message": "Google Drive integration has been removed. App now uses Supabase PostgreSQL."
    }

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
    error: Optional[str] = None
):
    """Google Drive OAuth callback - no longer used"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(
        url="/admin?message=Google+Drive+integration+removed+-+using+Supabase+now",
        status_code=303
    )

@router.post("/drive/sync")
async def sync_database(
    current_user: dict = Depends(get_current_admin)
):
    """Google Drive sync - no longer used - app now uses Supabase PostgreSQL"""
    return {
        "success": False,
        "message": "Google Drive integration has been removed. App now uses Supabase PostgreSQL - data is automatically synced."
    }

@router.post("/drive/upload")
async def upload_database(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_admin)
):
    """Google Drive upload - no longer used - app now uses Supabase PostgreSQL"""
    return {
        "success": False,
        "message": "Google Drive integration has been removed. App now uses Supabase PostgreSQL - data is automatically saved."
    }

@router.get("/drive/upload-status")
async def get_upload_status(
    current_user: dict = Depends(get_current_admin)
):
    """Get current upload status"""
    from app.services.refresh_status import RefreshStatusService
    status = RefreshStatusService.get_status()
    
    return {
        "is_uploading": status.get("is_uploading", False),
        "upload_progress": status.get("upload_progress"),
        "upload_message": status.get("upload_message"),
        "upload_size_mb": status.get("upload_size_mb")
    }

