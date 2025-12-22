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
        # Log database status
        logger.info(f"📊 Priority items request: target={target_branch} ({target_company}), source={source_branch} ({source_company})")
        logger.info(f"📁 Database path: {db_manager.db_path}")
        logger.info(f"📁 Database exists: {os.path.exists(db_manager.db_path) if db_manager.db_path else False}")
        
        # Check if database has data
        if db_manager.db_path and os.path.exists(db_manager.db_path):
            try:
                import sqlite3
                conn = sqlite3.connect(db_manager.db_path)
                cursor = conn.cursor()
                
                # Check table counts
                tables_to_check = ['current_stock', 'stock_data', 'purchase_orders', 'branch_orders', 'sales']
                table_counts = {}
                for table in tables_to_check:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        table_counts[table] = count
                        logger.info(f"📋 Table '{table}': {count} rows")
                    except Exception as e:
                        logger.warning(f"⚠️ Table '{table}' not found or error: {e}")
                        table_counts[table] = 0
                
                conn.close()
                
                # If no data in key tables, return helpful error
                if table_counts.get('current_stock', 0) == 0 and table_counts.get('stock_data', 0) == 0:
                    logger.error("❌ Database has no stock data!")
                    return {
                        "success": False,
                        "error": "Database is empty. Please refresh data first by clicking 'Refresh Now' button.",
                        "data": [],
                        "count": 0,
                        "diagnostics": {
                            "database_path": db_manager.db_path,
                            "database_exists": True,
                            "table_counts": table_counts,
                            "message": "No stock data found. Please refresh data from APIs."
                        }
                    }
            except Exception as e:
                logger.error(f"❌ Error checking database: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
        # Use the wrapper db_manager directly - it always has db_path
        # If original manager exists, use it; otherwise use wrapper
        manager_to_use = db_manager._db_manager if hasattr(db_manager, '_db_manager') and db_manager._db_manager is not None else db_manager
        
        # Ensure db_path is set
        if not hasattr(manager_to_use, 'db_path') or not manager_to_use.db_path:
            manager_to_use.db_path = db_manager.db_path
        
        dashboard_service = DashboardService(manager_to_use)
        logger.info(f"🔍 Calling get_priority_items_between_branches...")
        priority_items = dashboard_service.get_priority_items_between_branches(
            target_branch,
            target_company,
            source_branch,
            source_company,
            limit=limit
        )
        
        logger.info(f"📊 DashboardService returned: {type(priority_items)}, empty: {priority_items is None or (hasattr(priority_items, 'empty') and priority_items.empty)}")
        
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
            logger.info(f"✅ Returning {len(records)} priority items")
            return {
                "success": True,
                "data": records,
                "count": len(priority_items)
            }
        else:
            logger.warning("⚠️ No priority items returned from DashboardService")
            # Check database again to provide helpful message
            try:
                import sqlite3
                conn = sqlite3.connect(db_manager.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM current_stock")
                stock_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM stock_data")
                stock_data_count = cursor.fetchone()[0]
                conn.close()
                
                if stock_count == 0 and stock_data_count == 0:
                    return {
                        "success": False,
                        "error": "Database is empty. Please refresh data first by clicking 'Refresh Now' button.",
                        "data": [],
                        "count": 0,
                        "message": "No stock data found in database. Please refresh data from APIs."
                    }
            except Exception as e:
                logger.error(f"Error checking database: {e}")
            
            return {
                "success": True,
                "data": [],
                "count": 0,
                "message": "No priority items found for the selected branches. Try selecting different branches or refresh data."
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

@router.get("/diagnostics")
async def get_database_diagnostics(
    current_user: dict = Depends(get_current_user),
    db_manager = Depends(get_db_manager)
):
    """Get database diagnostics to help troubleshoot empty data issues"""
    import sqlite3
    diagnostics = {
        "database_path": db_manager.db_path,
        "database_exists": False,
        "database_size_mb": 0,
        "tables": {},
        "summary": {}
    }
    
    try:
        if db_manager.db_path and os.path.exists(db_manager.db_path):
            diagnostics["database_exists"] = True
            diagnostics["database_size_mb"] = round(os.path.getsize(db_manager.db_path) / (1024 * 1024), 2)
            
            conn = sqlite3.connect(db_manager.db_path)
            cursor = conn.cursor()
            
            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Count rows in each table
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    diagnostics["tables"][table] = count
                except Exception as e:
                    diagnostics["tables"][table] = f"Error: {str(e)}"
            
            conn.close()
            
            # Summary
            key_tables = ['current_stock', 'stock_data', 'purchase_orders', 'branch_orders', 'sales']
            diagnostics["summary"] = {
                "has_stock_data": diagnostics["tables"].get('current_stock', 0) > 0 or diagnostics["tables"].get('stock_data', 0) > 0,
                "has_order_data": diagnostics["tables"].get('purchase_orders', 0) > 0 or diagnostics["tables"].get('branch_orders', 0) > 0,
                "has_sales_data": diagnostics["tables"].get('sales', 0) > 0,
                "total_tables": len(tables),
                "key_table_counts": {table: diagnostics["tables"].get(table, 0) for table in key_tables}
            }
            
            if not diagnostics["summary"]["has_stock_data"]:
                diagnostics["message"] = "⚠️ Database has no stock data. Please refresh data by clicking 'Refresh Now' button."
            elif diagnostics["summary"]["has_stock_data"] and diagnostics["summary"]["has_order_data"]:
                diagnostics["message"] = "✅ Database appears to have data. If tables are still empty, check branch selection or query filters."
            else:
                diagnostics["message"] = "⚠️ Database has stock data but may be missing order data. Try refreshing."
        else:
            diagnostics["message"] = "❌ Database file not found. Please refresh data to create database."
    except Exception as e:
        diagnostics["error"] = str(e)
        import traceback
        diagnostics["traceback"] = traceback.format_exc()
    
    return {
        "success": True,
        "diagnostics": diagnostics
    }

@router.get("/sync-status")
async def get_sync_status(
    current_user: dict = Depends(get_current_user),
    db_manager = Depends(get_db_manager)
):
    """Get database sync status - shows if local DB is synced with Drive"""
    import os
    from app.dependencies import get_drive_manager
    from app.config import settings
    
    status = {
        "local_database": {
            "exists": False,
            "path": str(db_manager.db_path) if db_manager.db_path else None,
            "size_mb": 0,
            "modified": None
        },
        "drive_database": {
            "exists": False,
            "modified": None
        },
        "sync_status": "unknown",
        "message": ""
    }
    
    try:
        # Check local database
        if db_manager.db_path and os.path.exists(db_manager.db_path):
            status["local_database"]["exists"] = True
            status["local_database"]["size_mb"] = round(os.path.getsize(db_manager.db_path) / (1024 * 1024), 2)
            status["local_database"]["modified"] = os.path.getmtime(db_manager.db_path)
        
        # Check Drive database
        try:
            drive_manager = get_drive_manager()
            if drive_manager.is_authenticated():
                drive_info = drive_manager.get_database_info()
                if drive_info and drive_info.get('exists'):
                    status["drive_database"]["exists"] = True
                    status["drive_database"]["modified"] = drive_info.get('modified')
                    
                    # Compare timestamps
                    if status["local_database"]["exists"]:
                        from datetime import datetime
                        local_mtime = datetime.fromtimestamp(status["local_database"]["modified"])
                        drive_timestamp = drive_info.get('modified')
                        if drive_timestamp:
                            try:
                                drive_mtime = datetime.fromisoformat(drive_timestamp.replace('Z', '+00:00'))
                                if drive_mtime > local_mtime:
                                    status["sync_status"] = "outdated"
                                    status["message"] = "Drive has newer data. Syncing in background..."
                                else:
                                    status["sync_status"] = "synced"
                                    status["message"] = "Database is up to date."
                            except Exception as e:
                                logger.error(f"Error parsing drive timestamp: {e}")
                                status["sync_status"] = "synced"
                                status["message"] = "Database is available."
                        else:
                            status["sync_status"] = "synced"
                            status["message"] = "Database is available."
                    else:
                        status["sync_status"] = "missing"
                        status["message"] = "Downloading database from Drive..."
                else:
                    status["sync_status"] = "no_drive_db"
                    status["message"] = "No database in Drive. Click 'Refresh All Data' to create one."
            else:
                status["sync_status"] = "not_authenticated"
                status["message"] = "Google Drive not authenticated. Using local database only."
        except Exception as e:
            logger.error(f"Error checking Drive status: {e}")
            status["sync_status"] = "error"
            status["message"] = "Could not check Drive status. Using local database."
    
    except Exception as e:
        status["sync_status"] = "error"
        status["message"] = f"Error checking sync status: {str(e)}"
        logger.error(f"Error getting sync status: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    return {
        "success": True,
        "status": status
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

