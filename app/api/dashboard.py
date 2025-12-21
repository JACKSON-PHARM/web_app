"""
Dashboard API Routes
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional
from app.dependencies import get_current_user, get_db_manager
import sys
import os
import logging

# Set up logger first
logger = logging.getLogger(__name__)

# Try to import DashboardService - first from local web_app copy, then from parent ui folder
try:
    # First try: Import from web_app/app/services (for Render deployment)
    from app.services.dashboard_service import DashboardService
    logger.info("✅ Imported DashboardService from app.services")
except ImportError:
    try:
        # Second try: Import from parent ui folder (for local development)
        parent_path = os.path.join(os.path.dirname(__file__), '..', '..', '..')
        if os.path.exists(parent_path):
            sys.path.insert(0, parent_path)
        from ui.dashboard_service import DashboardService
        logger.info("✅ Imported DashboardService from parent ui folder")
    except ImportError:
        # Fallback: Service not available
        logger.error("❌ Could not import DashboardService from any location - dashboard will not work")
        DashboardService = None

router = APIRouter()

@router.get("/new-arrivals/test")
async def test_new_arrivals_api(
    current_user: dict = Depends(get_current_user)
):
    """Test endpoint to check if supplier invoice API is working"""
    try:
        from app.services.supplier_invoice_fetcher import SupplierInvoiceFetcher
        from app.services.credential_manager import CredentialManager
        from app.config import settings
        from datetime import datetime, timedelta
        
        cred_manager = CredentialManager(app_root=settings.LOCAL_CACHE_DIR)
        fetcher = SupplierInvoiceFetcher(cred_manager)
        
        # Test authentication
        token = fetcher._get_auth_token("NILA")
        if not token:
            return {
                "success": False,
                "error": "Authentication failed",
                "message": "Could not authenticate with API. Check credentials."
            }
        
        # Test getting invoices (just count, don't process details)
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=14)
        
        logger.info(f"🧪 Testing API for BABA DOGO HQ (branch_code=1) from {start_date} to {end_date}")
        invoices_hq = fetcher.get_supplier_invoices(1, start_date, end_date, "NILA")
        
        logger.info(f"📊 BABA DOGO HQ: {len(invoices_hq)} invoices")
        
        # Also test DAIMA MERU WHOLESALE (as shown in user's example)
        logger.info(f"🧪 Testing API for DAIMA MERU WHOLESALE (branch_code=13) from {start_date} to {end_date}")
        invoices_daima = fetcher.get_supplier_invoices(13, start_date, end_date, "DAIMA")
        
        logger.info(f"📊 DAIMA MERU WHOLESALE: {len(invoices_daima)} invoices")
        
        # Use the branch with more invoices, or DAIMA if both are 0
        if len(invoices_daima) > len(invoices_hq):
            invoices = invoices_daima
            branch_name = "DAIMA MERU WHOLESALE (bcode=13)"
        else:
            invoices = invoices_hq
            branch_name = "BABA DOGO HQ (bcode=1)"
        
        return {
            "success": True,
            "message": f"API is working. Found {len(invoices)} invoices in past 14 days from {branch_name}",
            "invoice_count": len(invoices),
            "date_range": f"{start_date} to {end_date}",
            "baba_dogo_hq_count": len(invoices_hq),
            "daima_meru_count": len(invoices_daima),
            "sample_invoices": invoices[:5] if invoices else []
        }
    except Exception as e:
        import traceback
        logger.error(f"Test failed: {e}")
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@router.get("/new-arrivals")
async def get_new_arrivals(
    target_branch: str = Query(default="BABA DOGO HQ"),
    target_company: str = Query(default="NILA"),
    limit: int = Query(default=100),
    use_api: bool = Query(default=True, description="Fetch directly from API instead of database"),
    current_user: dict = Depends(get_current_user),
    db_manager = Depends(get_db_manager)
):
    """Get new arrivals - fetches supplier invoices from API for past 14 days"""
    try:
        if use_api:
            # Fetch directly from API (new approach)
            from app.services.supplier_invoice_fetcher import SupplierInvoiceFetcher
            from app.services.credential_manager import CredentialManager
            from app.config import settings
            
            logger.info(f"🚀 Starting new arrivals fetch for {target_branch} ({target_company})")
            
            cred_manager = CredentialManager(app_root=settings.LOCAL_CACHE_DIR)
            fetcher = SupplierInvoiceFetcher(cred_manager)
            
            # Fetch from BABA DOGO HQ (BR001, branch_num: 1) for past 14 days
            # Note: If BABA DOGO HQ returns 0 invoices, try DAIMA MERU WHOLESALE (bcode=13) as shown in user's example
            logger.info("📥 Fetching supplier invoices from API for BABA DOGO HQ (branch_code=1)...")
            logger.info("   If this returns 0, BABA DOGO HQ may not have supplier invoices. Try DAIMA MERU WHOLESALE (bcode=13) instead.")
            
            new_arrivals_items = fetcher.get_new_arrivals(
                branch_name="BABA DOGO HQ",
                branch_code=1,  # BR001 = branch_num 1
                company="NILA",
                days=14
            )
            
            logger.info(f"📊 API returned {len(new_arrivals_items)} items for BABA DOGO HQ")
            
            # If no items from BABA DOGO HQ, try DAIMA MERU WHOLESALE (as shown in user's example)
            if not new_arrivals_items or len(new_arrivals_items) == 0:
                logger.info("🔄 Trying DAIMA MERU WHOLESALE (branch_code=13) as fallback...")
                new_arrivals_items = fetcher.get_new_arrivals(
                    branch_name="DAIMA MERU WHOLESALE",
                    branch_code=13,  # As shown in user's example
                    company="DAIMA",
                    days=14
                )
                logger.info(f"📊 API returned {len(new_arrivals_items)} items for DAIMA MERU WHOLESALE")
            
            logger.info(f"✅ API returned {len(new_arrivals_items)} items")
            
            if not new_arrivals_items:
                return {
                    "success": True,
                    "data": [],
                    "count": 0,
                    "message": "No new arrivals found in the past 14 days",
                    "source": "API"
                }
            
            # Convert to DataFrame for consistency with existing code
            import pandas as pd
            df = pd.DataFrame(new_arrivals_items)
            
            # Limit items before enrichment to speed things up
            if len(df) > limit:
                df = df.head(limit)
                logger.info(f"📊 Limited to {limit} items for faster processing")
            
            # Get stock data from database to enrich the results - OPTIMIZED BATCH QUERY
            try:
                # Use the wrapper db_manager directly - it always has db_path
                # If original manager exists, use it; otherwise use wrapper
                manager_to_use = db_manager._db_manager if hasattr(db_manager, '_db_manager') and db_manager._db_manager is not None else db_manager
                
                # Ensure db_path is set
                if not hasattr(manager_to_use, 'db_path') or not manager_to_use.db_path:
                    manager_to_use.db_path = db_manager.db_path
                
                dashboard_service = DashboardService(manager_to_use)
                
                # Get stock information for items - SINGLE BATCH QUERY instead of per-item
                db_path = dashboard_service._get_database_path(prefer_stock=True)
                import sqlite3
                conn = sqlite3.connect(db_path)
                
                logger.info("📊 Enriching with stock data from database...")
                
                # Get unique item codes
                item_codes = df['item_code'].unique().tolist()
                placeholders = ','.join(['?'] * len(item_codes))
                
                # Batch query for HQ stock
                cursor = conn.cursor()
                cursor.execute(f"""
                    SELECT item_code, stock_pieces, pack_size 
                    FROM current_stock 
                    WHERE item_code IN ({placeholders}) 
                    AND branch = ? AND company = ?
                """, item_codes + ["BABA DOGO HQ", "NILA"])
                hq_stock_dict = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
                
                # Batch query for target branch stock
                cursor.execute(f"""
                    SELECT item_code, stock_pieces, pack_size 
                    FROM current_stock 
                    WHERE item_code IN ({placeholders}) 
                    AND branch = ? AND company = ?
                """, item_codes + [target_branch, target_company])
                branch_stock_dict = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
                
                # Batch query for last order dates (combining purchase_orders and branch_orders)
                cursor.execute(f"""
                    SELECT item_code, MAX(document_date) as last_order_date
                    FROM (
                        SELECT item_code, document_date
                        FROM purchase_orders
                        WHERE item_code IN ({placeholders})
                        AND branch = ? AND company = ?
                        UNION ALL
                        SELECT item_code, document_date
                        FROM branch_orders
                        WHERE item_code IN ({placeholders})
                        AND source_branch = ? AND company = ?
                    ) combined_orders
                    GROUP BY item_code
                """, item_codes + [target_branch, target_company] + item_codes + [target_branch, target_company])
                last_order_dict = {row[0]: row[1] for row in cursor.fetchall()}
                
                conn.close()
                
                # Add stock information to dataframe
                def enrich_row(row):
                    item_code = row['item_code']
                    hq_data = hq_stock_dict.get(item_code, (0, 1))
                    branch_data = branch_stock_dict.get(item_code, (0, 1))
                    
                    hq_stock_pieces, hq_pack_size = hq_data
                    branch_stock_pieces, branch_pack_size = branch_data
                    
                    pack_size = hq_pack_size if hq_pack_size > 0 else (branch_pack_size if branch_pack_size > 0 else 1)
                    
                    return pd.Series({
                        'hq_stock_pieces': hq_stock_pieces,
                        'hq_stock_packs': hq_stock_pieces / pack_size if pack_size > 0 else 0,
                        'branch_stock_pieces': branch_stock_pieces,
                        'branch_stock_packs': branch_stock_pieces / pack_size if pack_size > 0 else 0,
                        'pack_size': pack_size,
                        'last_order_date': last_order_dict.get(item_code)
                    })
                
                stock_df = df.apply(enrich_row, axis=1)
                df = pd.concat([df.reset_index(drop=True), stock_df.reset_index(drop=True)], axis=1)
                
                logger.info("📊 Enriching with ABC class and AMC...")
                
                # Load ABC class and AMC from inventory analysis
                inventory_df = dashboard_service._load_inventory_analysis()
                if not inventory_df.empty:
                    branch_inventory = inventory_df[
                        (inventory_df.get('branch_name', '') == target_branch) & 
                        (inventory_df.get('company_name', '') == target_company)
                    ].copy()
                    
                    if branch_inventory.empty:
                        branch_inventory = inventory_df[
                            inventory_df.get('company_name', '') == target_company
                        ].copy()
                    
                    if not branch_inventory.empty:
                        merge_cols = ['item_code']
                        if 'abc_class' in branch_inventory.columns:
                            merge_cols.append('abc_class')
                        if 'adjusted_amc' in branch_inventory.columns:
                            merge_cols.append('adjusted_amc')
                        elif 'base_amc' in branch_inventory.columns:
                            merge_cols.append('base_amc')
                        
                        available_cols = [col for col in merge_cols if col in branch_inventory.columns]
                        if available_cols:
                            df = df.merge(
                                branch_inventory[available_cols].drop_duplicates('item_code'),
                                on='item_code',
                                how='left'
                            )
                            
                            if 'adjusted_amc' in df.columns:
                                df['amc'] = df['adjusted_amc']
                            elif 'base_amc' in df.columns:
                                df['amc'] = df['base_amc']
                
                # Ensure required columns exist
                if 'abc_class' not in df.columns:
                    df['abc_class'] = ''
                if 'amc' not in df.columns:
                    df['amc'] = 0
                
                df['abc_class'] = df['abc_class'].fillna('')
                df['amc'] = pd.to_numeric(df['amc'], errors='coerce').fillna(0)
                
                logger.info(f"✅ Enrichment complete. Returning {len(df)} items")
                
            except Exception as e:
                logger.warning(f"Could not enrich with stock data: {e}")
                import traceback
                logger.warning(traceback.format_exc())
                # Add default columns
                df['hq_stock_pieces'] = 0
                df['hq_stock_packs'] = 0
                df['branch_stock_pieces'] = 0
                df['branch_stock_packs'] = 0
                df['pack_size'] = 1
                df['abc_class'] = ''
                df['amc'] = 0
                df['last_order_date'] = None
            
            # Sort by document_date descending and limit
            df = df.sort_values('document_date', ascending=False).head(limit)
            
            # Convert to dict - replace NaN with None for JSON serialization
            import numpy as np
            df = df.replace([np.nan, np.inf, -np.inf], None)
            records = df.to_dict('records')
            
            # Ensure all NaN-like values are None
            for record in records:
                for key, value in record.items():
                    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
                        record[key] = None
            
            return {
                "success": True,
                "data": records,
                "count": len(records),
                "source": "API"
            }
        else:
            # Fallback to database approach (original)
            # Use the wrapper db_manager directly - it always has db_path
            # If original manager exists, use it; otherwise use wrapper
            manager_to_use = db_manager._db_manager if hasattr(db_manager, '_db_manager') and db_manager._db_manager is not None else db_manager
            
            # Ensure db_path is set
            if not hasattr(manager_to_use, 'db_path') or not manager_to_use.db_path:
                manager_to_use.db_path = db_manager.db_path
            
            dashboard_service = DashboardService(manager_to_use)
            new_arrivals = dashboard_service.get_new_arrivals_this_week(
                "BABA DOGO HQ",  # Source branch (always HQ)
                target_company,
                target_branch,
                target_company,
                limit=limit
            )
            
            # Convert DataFrame to dict - replace NaN with None for JSON serialization
            if new_arrivals is not None and not new_arrivals.empty:
                import numpy as np
                new_arrivals = new_arrivals.replace([np.nan, np.inf, -np.inf], None)
                records = new_arrivals.to_dict('records')
                # Ensure all NaN-like values are None
                for record in records:
                    for key, value in record.items():
                        if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
                            record[key] = None
                return {
                    "success": True,
                    "data": records,
                    "count": len(new_arrivals),
                    "source": "Database"
                }
            else:
                return {
                    "success": True,
                    "data": [],
                    "count": 0,
                    "source": "Database"
                }
    except Exception as e:
        import traceback
        logger.error(f"Error getting new arrivals: {e}")
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "data": [],
            "count": 0
        }

@router.get("/priority-items")
async def get_priority_items(
    target_branch: str = Query(default="BABA DOGO HQ"),
    target_company: str = Query(default="NILA"),
    source_branch: str = Query(default="BABA DOGO HQ"),
    source_company: str = Query(default="NILA"),
    limit: int = Query(default=50),
    current_user: dict = Depends(get_current_user),
    db_manager = Depends(get_db_manager)
):
    """Get priority items between branches"""
    try:
        # Use the wrapper db_manager directly - it always has db_path
        # If original manager exists, use it; otherwise use wrapper
        manager_to_use = db_manager._db_manager if hasattr(db_manager, '_db_manager') and db_manager._db_manager is not None else db_manager
        
        # Ensure db_path is set
        if not hasattr(manager_to_use, 'db_path') or not manager_to_use.db_path:
            manager_to_use.db_path = db_manager.db_path
        
        dashboard_service = DashboardService(manager_to_use)
        priority_items = dashboard_service.get_priority_items_between_branches(
            target_branch,
            target_company,
            source_branch,
            source_company,
            limit=limit
        )
        
        # Convert DataFrame to dict - replace NaN with None for JSON serialization
        if priority_items is not None and not priority_items.empty:
            import numpy as np
            priority_items = priority_items.replace([np.nan, np.inf, -np.inf], None)
            records = priority_items.to_dict('records')
            # Ensure all NaN-like values are None
            for record in records:
                for key, value in record.items():
                    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
                        record[key] = None
            return {
                "success": True,
                "data": records,
                "count": len(priority_items)
            }
        else:
            return {
                "success": True,
                "data": [],
                "count": 0
            }
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "data": [],
            "count": 0
        }

@router.get("/branches")
async def get_branches(
    company: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db_manager = Depends(get_db_manager)
):
    """Get list of branches"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Fetching branches" + (f" for {company}" if company else ""))
        branches = db_manager.get_branches(company)
        logger.info(f"Found {len(branches)} branches")
        
        if not branches:
            logger.warning("No branches found, returning empty list")
        
        return {
            "success": True,
            "data": branches
        }
    except Exception as e:
        logger.error(f"Error getting branches: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e),
            "data": []
        }

