"""
Credentials API Routes
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from app.dependencies import get_current_user
from app.services.credential_manager import CredentialManager
from app.config import settings

router = APIRouter()

class SaveCredentialsRequest(BaseModel):
    company: str  # "NILA" or "DAIMA"
    username: str
    password: str
    base_url: Optional[str] = None

class TestCredentialsRequest(BaseModel):
    company: str
    username: str
    password: str
    base_url: Optional[str] = None

@router.post("/save")
async def save_credentials(
    request: SaveCredentialsRequest,
    current_user: dict = Depends(get_current_user)
):
    """Save credentials for a company"""
    if request.company not in ["NILA", "DAIMA"]:
        return {"success": False, "message": "Company must be NILA or DAIMA"}
    
    cred_manager = CredentialManager(app_root=settings.LOCAL_CACHE_DIR)
    
    base_url = request.base_url
    if not base_url:
        if request.company == "NILA":
            base_url = settings.NILA_API_URL
        else:
            base_url = settings.DAIMA_API_URL
    
    result = cred_manager.save_credentials(
        request.company,
        request.username,
        request.password,
        base_url
    )
    
    return result

@router.post("/test")
async def test_credentials(
    request: TestCredentialsRequest,
    current_user: dict = Depends(get_current_user)
):
    """Test credentials for a company"""
    if request.company not in ["NILA", "DAIMA"]:
        return {"success": False, "message": "Company must be NILA or DAIMA"}
    
    cred_manager = CredentialManager(app_root=settings.LOCAL_CACHE_DIR)
    
    base_url = request.base_url
    if not base_url:
        if request.company == "NILA":
            base_url = settings.NILA_API_URL
        else:
            base_url = settings.DAIMA_API_URL
    
    result = cred_manager.test_credentials(
        request.company,
        request.username,
        request.password,
        base_url
    )
    
    return result

@router.get("/status")
async def get_credentials_status(current_user: dict = Depends(get_current_user)):
    """Get credentials status for all companies"""
    cred_manager = CredentialManager(app_root=settings.LOCAL_CACHE_DIR)
    
    status = {}
    for company in ["NILA", "DAIMA"]:
        creds = cred_manager.get_credentials(company)
        status[company] = {
            "configured": creds is not None and bool(creds.get('username')),
            "username": creds.get('username', '') if creds else '',
            "has_password": bool(creds.get('password', '')) if creds else False,
            "base_url": creds.get('base_url', '') if creds else '',
            "enabled": creds.get('enabled', False) if creds else False
        }
    
    return {
        "success": True,
        "credentials": status
    }

