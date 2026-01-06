"""
Suppliers API Routes
"""
from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import get_current_user, get_credential_manager
from app.config import settings
from app.services.credential_manager_supabase import AccountLockedException, InvalidCredentialsException
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
    dataBaseName: str = None,  # Will be determined from company
    current_user: dict = Depends(get_current_user)
):
    """Get list of suppliers for a branch"""
    try:
        # Get credential manager
        cred_manager = get_credential_manager()
        
        # Determine company from branch_code using branch_config
        from scripts.data_fetchers.branch_config import ALL_BRANCHES
        company = None
        for branch in ALL_BRANCHES:
            if branch.get("branch_num") == branch_code:
                company = branch.get("company")
                break
        
        if not company:
            # Fallback: try both companies if branch_code not found
            logger.warning(f"Branch code {branch_code} not found in branch config, trying both companies")
            company = None
        
        # Get database name based on company
        database_names = {
            'NILA': 'PNLCUS0005DBREP',
            'DAIMA': 'P0757DB'
        }
        
        # If dataBaseName provided, use it; otherwise determine from company
        if dataBaseName:
            db_name = dataBaseName
        elif company:
            db_name = database_names.get(company, 'P0757DB')
        else:
            db_name = 'P0757DB'  # Default to DAIMA
        
        # Try companies in order: determined company first, then both if not found
        companies_to_try = [company] if company else ["NILA", "DAIMA"]
        suppliers = []
        auth_errors = []
        api_errors = []
        
        for company_to_try in companies_to_try:
            if not company_to_try:
                continue
            try:
                # Get authentication token
                token = cred_manager.get_valid_token(company_to_try)
                if not token:
                    # Check if credentials exist
                    creds = cred_manager.get_credentials(company_to_try)
                    if not creds:
                        auth_errors.append(f"{company_to_try}: No credentials configured")
                    else:
                        auth_errors.append(f"{company_to_try}: Authentication failed - check credentials in Settings")
                    continue
            except AccountLockedException as e:
                # Account is locked - tell user to unlock from Pharmacore first
                # The exception message already includes the username
                auth_errors.append(f"{company_to_try}: {e.message}")
                logger.error(f"🚫 {e.message}")
                continue
            except InvalidCredentialsException as e:
                # Invalid credentials - tell user to check credentials
                # The exception message already includes the username
                auth_errors.append(f"{company_to_try}: {e.message}")
                logger.error(f"🚫 {e.message}")
                continue
                
                # Use correct database name for this company
                db_name_for_company = database_names.get(company_to_try, db_name)
                
                # Get base URL
                base_url = cred_manager.get_credentials(company_to_try).get("base_url", "https://corebasebackendnila.co.ke:5019")
                base_url = base_url.rstrip("/")
                
                # Make API request
                url = f"{base_url}/Suppliers"
                params = {
                    "bcode": branch_code,
                    "supCode": sup_code,
                    "numberofSuppliers": numberofSuppliers,
                    "isActive": str(isActive).lower(),
                    "catcode": catcode,
                    "dataBaseName": db_name_for_company
                }
                
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Origin": "https://phamacoreonline.co.ke:5100",
                    "Referer": "https://phamacoreonline.co.ke:5100/"
                }
                
                logger.info(f"🔍 Fetching suppliers for branch_code={branch_code}, company={company_to_try}, database={db_name_for_company}")
                response = requests.get(url, params=params, headers=headers, verify=False, timeout=30)
                response.raise_for_status()
                
                company_suppliers = response.json()
                if company_suppliers:
                    suppliers.extend(company_suppliers)
                    logger.info(f"✅ Found {len(company_suppliers)} suppliers for {company_to_try}")
                    break  # If we got suppliers from one company, use that
                    
            except requests.exceptions.HTTPError as e:
                error_msg = f"{company_to_try}: API returned {e.response.status_code}"
                try:
                    error_data = e.response.json()
                    error_msg += f" - {error_data}"
                except:
                    error_msg += f" - {e.response.text[:200]}"
                api_errors.append(error_msg)
                logger.warning(f"Failed to get suppliers from {company_to_try}: {e}")
                continue
            except Exception as e:
                api_errors.append(f"{company_to_try}: {str(e)}")
                logger.warning(f"Failed to get suppliers from {company_to_try}: {e}")
                continue
        
        if not suppliers:
            # Provide detailed error message
            error_detail = f"No suppliers found for branch_code {branch_code}"
            
            # Check if account is locked - prioritize this message
            locked_errors = [err for err in auth_errors if 'locked' in err.lower() or 'unlock' in err.lower()]
            if locked_errors:
                error_detail = f"{'; '.join(locked_errors)}"
            elif auth_errors:
                error_detail += f". Authentication issues: {'; '.join(auth_errors)}"
            
            if api_errors:
                error_detail += f". API errors: {'; '.join(api_errors)}"
            
            raise HTTPException(status_code=403 if locked_errors else 404, detail=error_detail)
        
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

