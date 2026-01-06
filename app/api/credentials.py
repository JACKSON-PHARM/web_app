"""
Credentials API Routes
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.dependencies import get_current_user, get_current_admin
from app.dependencies import get_credential_manager
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
    
    cred_manager = get_credential_manager()
    
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
    
    cred_manager = get_credential_manager()
    
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
    cred_manager = get_credential_manager()
    
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

class DeleteCredentialsRequest(BaseModel):
    company: str  # "NILA" or "DAIMA"

@router.delete("/delete")
async def delete_credentials(
    company: str,
    current_user: dict = Depends(get_current_admin)  # Only admins can delete
):
    """Delete credentials for a company (Admin only)"""
    if company not in ["NILA", "DAIMA"]:
        raise HTTPException(
            status_code=400,
            detail="Company must be NILA or DAIMA"
        )
    
    cred_manager = get_credential_manager()
    result = cred_manager.delete_credentials(company)
    
    if not result.get('success'):
        raise HTTPException(
            status_code=500,
            detail=result.get('message', 'Failed to delete credentials')
        )
    
    return result

