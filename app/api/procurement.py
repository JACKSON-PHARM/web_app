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
        # Note: We don't import CredentialManager as it's not needed - we create a simple temp class
        
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
                    # Use /Auth endpoint (not /api/auth/login) with userName/password format
                    auth_url = f"{self.base_url}/Auth"
                    response = session.post(auth_url, json={
                        'userName': self.username,  # Note: userName (camelCase), not username
                        'password': self.password
                    }, timeout=15, verify=False)
                    
                    logger.info(f"🔐 Auth response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        data = response.json()
                        token = data.get('token')  # Response contains 'token', not 'access_token'
                        if token:
                            logger.info(f"✅ Authentication successful, got token")
                            return token
                        else:
                            logger.error(f"❌ No token in auth response: {data}")
                    else:
                        error_text = response.text[:500] if response.text else "No error message"
                        logger.error(f"❌ Authentication failed: HTTP {response.status_code} - {error_text}")
                except Exception as e:
                    logger.error(f"❌ Error getting token: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
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
            # For branch orders:
            # - request.branch_name = target branch (where we're viewing stock) = where order is CREATED
            # - request.source_branch_name = source branch (where stock comes FROM) = where stock is requested FROM
            # The order is CREATED at target branch, requesting stock FROM source branch
            # So branch_to_name/branch_to_code should be SOURCE branch (where stock comes FROM)
            branch_to_name = request.source_branch_name  # Source branch = where stock comes FROM
            
            # Get source branch code (where stock comes FROM) and convert to "BR001" format
            source_branch_code = None
            if request.source_branch_name and request.source_branch_company:
                for branch in ALL_BRANCHES:
                    if branch['branch_name'] == request.source_branch_name and branch['company'] == request.source_branch_company:
                        source_branch_code_raw = branch.get('branchcode') or branch.get('branch_code')
                        if isinstance(source_branch_code_raw, str) and source_branch_code_raw.startswith('BR'):
                            try:
                                source_branch_code = int(source_branch_code_raw.replace('BR', ''))
                            except:
                                source_branch_code = int(source_branch_code_raw) if source_branch_code_raw.isdigit() else None
                        else:
                            source_branch_code = int(source_branch_code_raw) if str(source_branch_code_raw).isdigit() else None
                        break
            
            # Convert source branch code to "BR001" format for branchToCode
            if source_branch_code:
                if isinstance(source_branch_code, int):
                    branch_to_code_str = f"BR{source_branch_code:03d}"  # e.g., 1 -> "BR001", 18 -> "BR018"
                elif isinstance(source_branch_code, str) and source_branch_code.startswith('BR'):
                    branch_to_code_str = source_branch_code
                else:
                    try:
                        num = int(source_branch_code)
                        branch_to_code_str = f"BR{num:03d}"
                    except:
                        branch_to_code_str = str(source_branch_code)
            else:
                branch_to_code_str = None
            
            logger.info(f"Branch order: Target branch (where order is CREATED) = {request.branch_name} (code: {branch_code}), Source branch (where stock comes FROM) = {branch_to_name} (code: {branch_to_code_str})")
        else:
            # For purchase orders: user selects external suppliers, so branch_to_name is not used
            # Source branch selection is maintained for compatibility but not used for branch_to_name
            # Purchase orders are from external suppliers, not from another branch
            branch_to_name = None
            branch_to_code_str = None
            logger.info(f"Purchase order: Branch = {request.branch_name}, Supplier = {getattr(request, 'supplier_name', 'N/A')}, Source branch (for reference only) = {request.source_branch_name}")
        
        # Initialize procurement bot
        # For branch orders: 
        # - branch_name/branch_code should be TARGET branch (where order is CREATED)
        # - branch_to_name/branch_to_code should be SOURCE branch (where stock comes FROM)
        # For purchase orders: branch_name is the branch making the order
        actual_branch_name = request.branch_name  # Target branch (where order is created)
        actual_branch_code = branch_code  # Target branch code
        
        if request.order_mode == "branch_order":
            # For branch orders, the order is CREATED at the target branch
            # Stock comes FROM the source branch
            # So we keep target branch as actual_branch_name/branch_code
            # And set branch_to to source branch
            pass  # Already set correctly above
        
        # CRITICAL: Use request.company (procurement company) for authentication, not branch_company
        # The user selects the company (NILA/DAIMA) for API authentication
        # This is different from branch_company which is the branch's company
        procurement_company = request.company  # Company selected by user for authentication
        
        bot = IntegratedProcurementBot(
            stock_view_df=items_df,
            branch_name=actual_branch_name,  # Source branch for branch orders, branch making order for purchase orders
            branch_code=actual_branch_code,  # Source branch code for branch orders
            company=procurement_company,  # Use procurement company for authentication (user-selected)
            credential_manager=cred_manager,
            order_mode=request.order_mode,
            branch_to_name=branch_to_name,  # Target branch for branch orders (where order goes TO)
            branch_to_code=branch_to_code_str,  # Target branch code for branch orders
            manual_selection=request.manual_selection,
            supplier_code=getattr(request, 'supplier_code', None),  # Optional supplier code
            supplier_name=getattr(request, 'supplier_name', None)  # Optional supplier name
        )
        
        logger.info(f"🔐 Procurement bot initialized: company={procurement_company} (for auth), branch={actual_branch_name}, mode={request.order_mode}")
        
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
            order_numbers = result.get('order_numbers', [])  # Array of order numbers (for multiple orders)
            processed_count = result.get('processed_count', len(selected_items))
            total_orders = result.get('total_orders', 1)  # Number of orders created
            
            # If order_numbers array exists, use it; otherwise use single order_number
            if order_numbers and len(order_numbers) > 0:
                order_number = order_numbers[0]  # Use first order number as primary
            
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
            
            response_data = {
                "success": True,
                "message": result.get('message', f"Processed {processed_count} items successfully"),
                "results": results,
                "total_items": len(results),
                "successful_orders": processed_count,
                "order_number": order_number,  # Primary order number (first one)
                "order_mode": request.order_mode,
                "target_branch": target_branch,
            }
            
            # Add order_numbers array if multiple orders were created
            if order_numbers and len(order_numbers) > 0:
                response_data["order_numbers"] = order_numbers
                response_data["total_orders"] = total_orders
            
            return response_data
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

