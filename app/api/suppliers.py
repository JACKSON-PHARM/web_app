"""
Suppliers API Routes
"""
from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import get_current_user, get_credential_manager
from app.config import settings
import requests
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/list")
async def get_suppliers(
    branch_code: int,
    sup_code: str = "",
    numberofSuppliers: int = 10,
    isActive: bool = True,
    catcode: int = 0,
    dataBaseName: str = "P0757DB",
    current_user: dict = Depends(get_current_user)
):
    """Get list of suppliers for a branch"""
    try:
        # Get credential manager
        cred_manager = get_credential_manager()
        
        # Determine company from branch_code (you may need to adjust this logic)
        # For now, try both companies
        suppliers = []
        
        for company in ["NILA", "DAIMA"]:
            try:
                # Get authentication token
                token = cred_manager.get_valid_token(company)
                if not token:
                    continue
                
                # Get base URL
                base_url = cred_manager.get_credentials(company).get("base_url", "https://corebasebackendnila.co.ke:5019")
                base_url = base_url.rstrip("/")
                
                # Make API request
                url = f"{base_url}/Suppliers"
                params = {
                    "bcode": branch_code,
                    "supCode": sup_code,
                    "numberofSuppliers": numberofSuppliers,
                    "isActive": str(isActive).lower(),
                    "catcode": catcode,
                    "dataBaseName": dataBaseName
                }
                
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Origin": "https://phamacoreonline.co.ke:5100",
                    "Referer": "https://phamacoreonline.co.ke:5100/"
                }
                
                response = requests.get(url, params=params, headers=headers, verify=False, timeout=30)
                response.raise_for_status()
                
                company_suppliers = response.json()
                if company_suppliers:
                    suppliers.extend(company_suppliers)
                    break  # If we got suppliers from one company, use that
                    
            except Exception as e:
                logger.warning(f"Failed to get suppliers from {company}: {e}")
                continue
        
        if not suppliers:
            raise HTTPException(status_code=404, detail="No suppliers found")
        
        return {
            "success": True,
            "suppliers": suppliers,
            "count": len(suppliers)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting suppliers: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

