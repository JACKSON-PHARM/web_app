"""
Procurement Bot API Routes
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.dependencies import get_current_user, get_db_manager
import sys
import os
import pandas as pd
import logging

# Set up logger first
logger = logging.getLogger(__name__)

# Try to import procurement bot and branch config from scripts
IntegratedProcurementBot = None
BRANCH_MAPPING = {}
ALL_BRANCHES = []

try:
    # Path should already be set in app/main.py, so scripts module should be available
    from scripts.procurement_bot.integrated_procurement_bot import IntegratedProcurementBot
    from scripts.data_fetchers.branch_config import BRANCH_MAPPING, ALL_BRANCHES
    logger.info("✅ Imported procurement bot and branch config from scripts")
except ImportError:
    # This is expected if procurement_bot doesn't exist - feature will be unavailable
    logger.warning("⚠️ Could not import procurement bot - procurement features will be limited")
    # Provide fallback empty values
    BRANCH_MAPPING = {}
    ALL_BRANCHES = []

from app.dependencies import get_credential_manager
from app.config import settings

router = APIRouter()

class ProcurementRequest(BaseModel):
    items: List[Dict[str, Any]]  # List of items with item_code, quantity, etc.
    branch_name: str
    branch_company: str
    source_branch_name: Optional[str] = None
    source_branch_company: Optional[str] = None
    order_mode: str = "purchase_order"  # "purchase_order" or "branch_order"
    manual_selection: bool = True
    supplier_code: Optional[str] = None  # Supplier code for purchase orders
    supplier_name: Optional[str] = None  # Supplier name for purchase orders
    # Credentials for accountability - user must provide current credentials
    company: str  # "NILA" or "DAIMA"
    username: str
    password: str
    base_url: Optional[str] = None

@router.post("/run")
async def run_procurement_bot(
    request: ProcurementRequest,
    current_user: dict = Depends(get_current_user),
    db_manager = Depends(get_db_manager)
):
    """Run procurement bot on selected items"""
    if IntegratedProcurementBot is None:
        raise HTTPException(
            status_code=503,
            detail="Procurement bot not available - scripts module not found. This feature requires the full application codebase."
        )
    
    try:
        # Get branch code from branch name
        branch_code = None
        for branch in ALL_BRANCHES:
            if branch['branch_name'] == request.branch_name and branch['company'] == request.branch_company:
                # Try both 'branchcode' and 'branch_code' keys
                branch_code = branch.get('branchcode') or branch.get('branch_code')
                if isinstance(branch_code, str) and branch_code.startswith('BR'):
                    # Extract numeric part if needed (e.g., "BR001" -> 1)
                    try:
                        branch_code = int(branch_code.replace('BR', ''))
                    except:
                        pass
                break
        
        if not branch_code:
            raise HTTPException(status_code=400, detail=f"Branch code not found for {request.branch_name} ({request.branch_company})")
        
        # Convert items list to DataFrame
        items_df = pd.DataFrame(request.items)
        
        # Create temporary credential manager with user-provided credentials
        # This ensures accountability - user must provide current credentials
        from app.services.credential_manager_supabase import CredentialManagerSupabase
        from app.services.credential_manager import CredentialManager
        
        # Create a temporary credential manager that uses provided credentials
        # We'll create a temporary instance that doesn't save to database
        class TempCredentialManager:
            """Temporary credential manager for procurement using user-provided credentials"""
            def __init__(self, company, username, password, base_url):
                self.company = company
                self.username = username
                self.password = password
                self.base_url = base_url or 'https://corebasebackendnila.co.ke:5019'
                self._token_cache = {}
                self._session_cache = {}
            
            def get_credentials(self, company: str):
                """Return provided credentials for the specified company"""
                if company == self.company:
                    return {
                        'username': self.username,
                        'password': self.password,
                        'base_url': self.base_url,
                        'enabled': True
                    }
                return None
            
            def get_valid_token(self, company: str):
                """Get token using provided credentials"""
                if company != self.company:
                    return None
                
                import requests
                try:
                    session = requests.Session()
                    auth_url = f"{self.base_url}/api/auth/login"
                    response = session.post(auth_url, json={
                        'username': self.username,
                        'password': self.password
                    }, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        return data.get('access_token') or data.get('token')
                except Exception as e:
                    logger.error(f"Error getting token: {e}")
                return None
            
            def get_session(self, company: str):
                """Get session for company"""
                import requests
                from requests.adapters import HTTPAdapter
                from urllib3.util.retry import Retry
                
                if company != self.company:
                    return None
                
                session = requests.Session()
                retry_strategy = Retry(
                    total=3,
                    backoff_factor=1,
                    status_forcelist=[429, 500, 502, 503, 504]
                )
                adapter = HTTPAdapter(max_retries=retry_strategy)
                session.mount("http://", adapter)
                session.mount("https://", adapter)
                return session
        
        # Use user-provided credentials for procurement
        cred_manager = TempCredentialManager(
            request.company,
            request.username,
            request.password,
            request.base_url
        )
        logger.info(f"✅ Using user-provided credentials for procurement (company: {request.company}, user: {request.username})")
        
        # For branch orders: branch_to_name should be the TARGET branch (where order is going TO)
        # For purchase orders: branch_to_name is not used (external suppliers, not branch-to-branch)
        branch_to_name = None
        branch_to_code_str = None
        
        if request.order_mode == "branch_order":
            # For branch orders, the target branch (where order is going TO) is request.branch_name
            # The source branch (where stock is coming FROM) is request.source_branch_name
            branch_to_name = request.branch_name  # Target branch = where order is going TO
            branch_to_code_str = str(branch_code)  # Use the target branch code
            logger.info(f"Branch order: Target branch (where order goes TO) = {branch_to_name}, Source branch (where stock comes FROM) = {request.source_branch_name}")
        else:
            # For purchase orders: user selects external suppliers, so branch_to_name is not used
            # Source branch selection is maintained for compatibility but not used for branch_to_name
            # Purchase orders are from external suppliers, not from another branch
            branch_to_name = None
            branch_to_code_str = None
            logger.info(f"Purchase order: Branch = {request.branch_name}, Supplier = {getattr(request, 'supplier_name', 'N/A')}, Source branch (for reference only) = {request.source_branch_name}")
        
        # Initialize procurement bot
        bot = IntegratedProcurementBot(
            stock_view_df=items_df,
            branch_name=request.branch_name,
            branch_code=branch_code,
            company=request.branch_company,
            credential_manager=cred_manager,
            order_mode=request.order_mode,
            branch_to_name=branch_to_name,  # Target branch for branch orders, source branch for purchase orders
            branch_to_code=branch_to_code_str,  # Use branch code string (e.g., "BR001")
            manual_selection=request.manual_selection,
            supplier_code=getattr(request, 'supplier_code', None),  # Optional supplier code
            supplier_name=getattr(request, 'supplier_name', None)  # Optional supplier name
        )
        
        # Prepare data
        prepared_df = bot.prepare_data()
        
        if prepared_df.empty:
            return {
                "success": False,
                "message": "No items to process",
                "results": []
            }
        
        # For manual selection, use the items directly (skip selection logic)
        if request.manual_selection:
            # Use the prepared dataframe directly as selected items
            selected_items = prepared_df.copy()
            
            # Use custom_order_quantity if provided (from user input), otherwise use amc
            if 'custom_order_quantity' in selected_items.columns:
                # User has specified custom quantities - use them
                selected_items['order_quantity'] = selected_items['custom_order_quantity'].fillna(selected_items.get('amc', 1))
                # Also update amc to match custom quantity for consistency
                selected_items['amc'] = selected_items['custom_order_quantity'].fillna(selected_items.get('amc', 1))
                logger.info(f"Using custom order quantities for {len(selected_items)} manually selected items")
            elif 'order_quantity' not in selected_items.columns:
                # Fall back to AMC if no custom quantity specified
                selected_items['order_quantity'] = selected_items.get('amc', 1)
                logger.info(f"Using AMC as order quantity for {len(selected_items)} manually selected items")
            else:
                # order_quantity already exists, use it
                logger.info(f"Using existing order_quantity for {len(selected_items)} manually selected items")
            
            # Ensure order_status is set
            if 'order_status' not in selected_items.columns:
                selected_items['order_status'] = 'READY_TO_ORDER'
            
            # Update bot's internal dataframe to use selected items
            bot.stock_view_df = selected_items
        else:
            # Auto-selection: use selection logic
            selected_items = bot.select_items(prepared_df)
            if selected_items.empty:
                return {
                    "success": False,
                    "message": "No items selected for ordering",
                    "results": []
                }
            # Update bot's internal dataframe to use selected items
            bot.stock_view_df = selected_items
        
        # Process orders using the bot's process method
        result = bot.process()
        
        # Format results
        results = []
        if result.get('success'):
            # Extract order details from result
            order_number = result.get('order_number', bot.order_doc_number)
            processed_count = result.get('processed_count', len(selected_items))
            
            # Create result entries for each item
            for _, item in selected_items.iterrows():
                results.append({
                    "item_code": item.get('item_code', ''),
                    "item_name": item.get('item_name', ''),
                    "quantity": item.get('order_quantity', 0),
                    "success": True,
                    "message": f"Order created successfully",
                    "order_doc": order_number
                })
            
            # Determine target branch for notification
            target_branch = request.branch_name
            if request.order_mode == "branch_order":
                target_branch = request.branch_name  # For branch orders, target is where order goes TO
            elif request.order_mode == "purchase_order":
                target_branch = request.branch_name  # For purchase orders, target is the branch making the order
            
            return {
                "success": True,
                "message": result.get('message', f"Processed {processed_count} items successfully"),
                "results": results,
                "total_items": len(results),
                "successful_orders": processed_count,
                "order_number": order_number,
                "order_mode": request.order_mode,
                "target_branch": target_branch,
                "target_company": request.branch_company
            }
        else:
            # Process failed
            for _, item in selected_items.iterrows():
                results.append({
                    "item_code": item.get('item_code', ''),
                    "item_name": item.get('item_name', ''),
                    "quantity": item.get('order_quantity', 0),
                    "success": False,
                    "message": result.get('message', 'Order creation failed'),
                    "order_doc": None
                })
            
            return {
                "success": False,
                "message": result.get('message', 'Order creation failed'),
                "results": results,
                "total_items": len(results),
                "successful_orders": 0
            }
        
    except Exception as e:
        logger.error(f"Error running procurement bot: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_procurement_status(
    current_user: dict = Depends(get_current_user)
):
    """Get procurement bot status"""
    return {
        "success": True,
        "available": True,
        "order_modes": ["purchase_order", "branch_order"]
    }

