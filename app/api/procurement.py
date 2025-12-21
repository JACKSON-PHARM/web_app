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
    # Add parent directory to import procurement bot
    parent_path = os.path.join(os.path.dirname(__file__), '..', '..', '..')
    if os.path.exists(parent_path):
        sys.path.insert(0, parent_path)
    from scripts.procurement_bot.integrated_procurement_bot import IntegratedProcurementBot
    from scripts.data_fetchers.branch_config import BRANCH_MAPPING, ALL_BRANCHES
    logger.info("✅ Imported procurement bot and branch config from scripts")
except ImportError:
    logger.warning("⚠️ Could not import procurement bot: No module named 'scripts' - procurement features will be limited")
    # Provide fallback empty values
    BRANCH_MAPPING = {}
    ALL_BRANCHES = []

from app.services.credential_manager import CredentialManager
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
        
        # Initialize credential manager
        cred_manager = CredentialManager(app_root=settings.LOCAL_CACHE_DIR)
        
        # Get source branch code if provided (for branch orders)
        source_branch_code_str = None
        if request.source_branch_name and request.source_branch_company:
            for branch in ALL_BRANCHES:
                if branch['branch_name'] == request.source_branch_name and branch['company'] == request.source_branch_company:
                    source_branch_code_str = branch.get('branchcode') or branch.get('branch_code')
                    break
        
        # Initialize procurement bot
        bot = IntegratedProcurementBot(
            stock_view_df=items_df,
            branch_name=request.branch_name,
            branch_code=branch_code,
            company=request.branch_company,
            credential_manager=cred_manager,
            order_mode=request.order_mode,
            branch_to_name=request.source_branch_name,
            branch_to_code=source_branch_code_str,  # Use branch code string (e.g., "BR001")
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
            
            return {
                "success": True,
                "message": result.get('message', f"Processed {processed_count} items successfully"),
                "results": results,
                "total_items": len(results),
                "successful_orders": processed_count,
                "order_number": order_number
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

