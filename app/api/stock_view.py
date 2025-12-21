"""
Stock View API Routes
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional
from app.dependencies import get_current_user, get_db_manager
import sys
import os

# Try to import StockViewService - first from local web_app copy, then from parent ui folder
try:
    # First try: Import from web_app/app/services (for Render deployment)
    from app.services.stock_view_service import StockViewService
    logger.info("✅ Imported StockViewService from app.services")
except ImportError:
    try:
        # Second try: Import from parent ui folder (for local development)
        parent_path = os.path.join(os.path.dirname(__file__), '..', '..', '..')
        if os.path.exists(parent_path):
            sys.path.insert(0, parent_path)
        from ui.stock_view_service import StockViewService
        logger.info("✅ Imported StockViewService from parent ui folder")
    except ImportError:
        # Fallback: Service not available
        import logging
        logger = logging.getLogger(__name__)
        logger.error("❌ Could not import StockViewService from any location - stock view will not work")
        StockViewService = None

router = APIRouter()

@router.get("/data")
async def get_stock_view_data(
    branch_name: str = Query(...),
    branch_company: str = Query(...),
    source_branch_name: Optional[str] = Query(default=None),
    source_branch_company: Optional[str] = Query(default=None),
    current_user: dict = Depends(get_current_user),
    db_manager = Depends(get_db_manager)
):
    """Get stock view data - optimized with timeout handling"""
    import logging
    import asyncio
    logger = logging.getLogger(__name__)
    
    try:
        if StockViewService is None:
            return {
                "success": False,
                "error": "StockViewService not available - parent directory import failed",
                "data": [],
                "count": 0
            }
        
        logger.info(f"Stock view request: branch={branch_name}, company={branch_company}, source={source_branch_name}, source_company={source_branch_company}")
        logger.info(f"Database path: {db_manager.db_path}")
        
        app_root = os.path.join(os.path.dirname(__file__), '..', '..', '..')
        if not os.path.exists(app_root):
            app_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        stock_service = StockViewService(db_manager.db_path, app_root)
        
        # Use defaults if not provided
        if not source_branch_name:
            source_branch_name = "BABA DOGO HQ"
        if not source_branch_company:
            source_branch_company = branch_company
        
        logger.info(f"Calling get_stock_view_data with: branch={branch_name}, company={branch_company}, source={source_branch_name}, source_company={source_branch_company}")
        
        # Run query in executor to prevent blocking (with 4 minute timeout)
        loop = asyncio.get_event_loop()
        stock_data = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: stock_service.get_stock_view_data(
                    branch_name,
                    branch_company,
                    source_branch_name,
                    source_branch_company
                )
            ),
            timeout=240.0  # 4 minutes timeout
        )
        
        logger.info(f"Stock view service returned: {len(stock_data) if stock_data is not None and not stock_data.empty else 0} rows")
        
        # Convert DataFrame to dict - replace NaN with None for JSON serialization
        if stock_data is not None and not stock_data.empty:
            # Replace NaN/NaT values with None for JSON serialization
            import numpy as np
            stock_data = stock_data.replace([np.nan, np.inf, -np.inf], None)
            # Convert to dict
            records = stock_data.to_dict('records')
            # Ensure all NaN-like values are None
            for record in records:
                for key, value in record.items():
                    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
                        record[key] = None
            return {
                "success": True,
                "data": records,
                "count": len(stock_data)
            }
        else:
            return {
                "success": True,
                "data": [],
                "count": 0
            }
    except asyncio.TimeoutError:
        logger.error("Stock view query timed out after 4 minutes")
        return {
            "success": False,
            "error": "Query timed out. The database is large and the query is taking longer than expected. Please try again or contact support.",
            "data": [],
            "count": 0
        }
    except Exception as e:
        import traceback
        logger.error(f"Stock view error: {e}")
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "data": [],
            "count": 0
        }

