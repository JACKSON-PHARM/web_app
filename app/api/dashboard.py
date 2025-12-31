"""
Dashboard API Routes
"""
from fastapi import APIRouter, Depends, Query, HTTPException, status
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
                # ALL data is in Supabase PostgreSQL - use database manager directly
                dashboard_service = DashboardService(db_manager)
                
                # Get stock information for items - SINGLE BATCH QUERY
                logger.info("📊 Enriching with stock data from Supabase...")
                
                # Get unique item codes
                item_codes = df['item_code'].unique().tolist()
                placeholders = ','.join(['%s'] * len(item_codes))
                
                # Batch query for HQ stock
                hq_stock_results = dashboard_service._execute_query(f"""
                    SELECT item_code, stock_pieces, pack_size 
                    FROM current_stock 
                    WHERE item_code IN ({placeholders}) 
                    AND branch = %s AND company = %s
                """, tuple(item_codes) + ("BABA DOGO HQ", "NILA"))
                hq_stock_dict = {row['item_code']: (row['stock_pieces'], row['pack_size']) for row in hq_stock_results}
                
                # Batch query for target branch stock
                branch_stock_results = dashboard_service._execute_query(f"""
                    SELECT item_code, stock_pieces, pack_size 
                    FROM current_stock 
                    WHERE item_code IN ({placeholders}) 
                    AND branch = %s AND company = %s
                """, tuple(item_codes) + (target_branch, target_company))
                branch_stock_dict = {row['item_code']: (row['stock_pieces'], row['pack_size']) for row in branch_stock_results}
                
                # Batch query for last order dates
                last_order_results = dashboard_service._execute_query(f"""
                    SELECT item_code, MAX(document_date) as last_order_date
                    FROM (
                        SELECT item_code, document_date
                        FROM purchase_orders
                        WHERE item_code IN ({placeholders})
                        AND branch = %s AND company = %s
                        UNION ALL
                        SELECT item_code, document_date
                        FROM branch_orders
                        WHERE item_code IN ({placeholders})
                        AND source_branch = %s AND company = %s
                    ) combined_orders
                    GROUP BY item_code
                """, tuple(item_codes) + (target_branch, target_company) + tuple(item_codes) + (target_branch, target_company))
                last_order_dict = {row['item_code']: row['last_order_date'] for row in last_order_results}
                
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
            # Use PostgreSQL database manager directly
            dashboard_service = DashboardService(db_manager)
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
    limit: int = Query(default=200),
    current_user: dict = Depends(get_current_user),
    db_manager = Depends(get_db_manager)
):
    """Get priority items between branches"""
    try:
        # Log database status
        logger.info(f"📊 Priority items request: target={target_branch} ({target_company}), source={source_branch} ({source_company})")
        logger.info("📁 Using Supabase PostgreSQL database")
        
        # Always PostgreSQL - check data via queries
        try:
            from app.services.dashboard_service import DashboardService
            dashboard_service = DashboardService(db_manager)
            tables_to_check = ['current_stock', 'supplier_invoices', 'purchase_orders', 'branch_orders', 'hq_invoices']
            table_counts = {}
            for table in tables_to_check:
                try:
                    result = dashboard_service._execute_query(f"SELECT COUNT(*) as count FROM {table}")
                    count = result[0]['count'] if result else 0
                    table_counts[table] = count
                    logger.info(f"📋 Table '{table}': {count} rows")
                except Exception as e:
                    logger.warning(f"⚠️ Table '{table}' not found or error: {e}")
                    table_counts[table] = 0
            
            # Check if we have data
            total_records = sum(table_counts.values())
            db_has_data = total_records > 0
            
            if db_has_data:
                # Check if refresh is in progress
                from app.services.refresh_status import RefreshStatusService
                refresh_status = RefreshStatusService.get_status()
                is_refreshing = refresh_status.get("is_refreshing", False)
                
                # If no data in key tables, return success with empty data but indicate refresh status
                if table_counts.get('current_stock', 0) == 0:
                    logger.warning("⚠️ Database has no stock data yet")
                    return {
                        "success": True,  # Return success so UI can handle gracefully
                        "data": [],
                        "count": 0,
                        "is_refreshing": is_refreshing,
                        "message": "No data available yet. Refresh in progress..." if is_refreshing else "Database is empty. Please refresh data.",
                        "diagnostics": {
                            "database_path": "Supabase PostgreSQL",
                            "database_exists": True,
                            "table_counts": table_counts,
                            "refresh_in_progress": is_refreshing
                        }
                    }
        except Exception as e:
            logger.error(f"❌ Error checking database: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        # Use PostgreSQL database manager directly
        dashboard_service = DashboardService(db_manager)
        logger.info(f"🔍 Calling get_priority_items_between_branches...")
        
        # Add timeout wrapper for the query (max 60 seconds)
        import asyncio
        import concurrent.futures
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                dashboard_service.get_priority_items_between_branches,
                target_branch,
                target_company,
                source_branch,
                source_company,
                limit=limit
            )
            try:
                priority_items = future.result(timeout=60.0)  # 60 second timeout
                logger.info(f"📊 DashboardService returned: {type(priority_items)}, empty: {priority_items is None or (hasattr(priority_items, 'empty') and priority_items.empty)}")
            except concurrent.futures.TimeoutError:
                logger.error("❌ Priority items query timed out after 60 seconds")
                return {
                    "success": False,
                    "error": "Query timeout - the database query took too long. The materialized view may need to be refreshed.",
                    "data": [],
                    "count": 0,
                    "message": "Query timeout. Try refreshing the materialized views or use smaller branch selections."
                }
            except Exception as e:
                logger.error(f"❌ Error executing priority items query: {e}")
                import traceback
                logger.error(traceback.format_exc())
                raise
        
        # Convert DataFrame to dict - replace NaN with None for JSON serialization
        if priority_items is not None and not priority_items.empty:
            import numpy as np
            priority_items = priority_items.replace([np.nan, np.inf, -np.inf], None)
            records = priority_items.to_dict('records')
            # Ensure all NaN-like values are None and format dates
            for record in records:
                for key, value in record.items():
                    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
                        record[key] = None
                    # Format date fields
                    if 'date' in key.lower() and value:
                        if isinstance(value, str):
                            # Already a string, check if it's a valid date format
                            if value not in ['', 'NaT', 'nan', 'None']:
                                record[key] = value
                            else:
                                record[key] = None
                        elif pd.notna(value):
                            try:
                                record[key] = pd.to_datetime(value).strftime('%Y-%m-%d')
                            except:
                                record[key] = str(value) if value else None
                        else:
                            record[key] = None
            logger.info(f"✅ Returning {len(records)} priority items")
            # Check if refresh is in progress
            from app.services.refresh_status import RefreshStatusService
            refresh_status = RefreshStatusService.get_status()
            is_refreshing = refresh_status.get("is_refreshing", False)
            
            return {
                "success": True,
                "data": records,
                "count": len(priority_items),
                "is_refreshing": is_refreshing,
                "message": "Data refresh in progress. This data may update automatically." if is_refreshing else None
            }
        else:
            logger.warning("⚠️ No priority items returned from DashboardService")
            # Check if source and target are the same (common issue)
            if target_branch == source_branch and target_company == source_company:
                return {
                    "success": True,
                    "data": [],
                    "count": 0,
                    "message": f"⚠️ Source and target branches are the same ({source_branch}). Priority items show items available at the source branch that are needed at a different target branch. Please select different branches.",
                    "help": "Priority items require: 1) Source branch (e.g., HQ) that HAS stock, 2) Target branch (e.g., retail branch) that NEEDS stock"
                }
            
            # Check database again to provide helpful message
            try:
                # Always PostgreSQL - use execute_query
                result = db_manager.execute_query("SELECT COUNT(*) as count FROM current_stock")
                stock_count = result[0]['count'] if result else 0
                
                # Check if source branch has stock
                source_result = db_manager.execute_query("SELECT COUNT(*) as count FROM current_stock WHERE branch = %s AND company = %s", (source_branch, source_company))
                source_stock_count = source_result[0]['count'] if source_result else 0
                
                # Check if target branch has stock
                target_result = db_manager.execute_query("SELECT COUNT(*) as count FROM current_stock WHERE branch = %s AND company = %s", (target_branch, target_company))
                target_stock_count = target_result[0]['count'] if target_result else 0
                
                if stock_count == 0:
                    return {
                        "success": False,
                        "error": "Database is empty. Please refresh data first by clicking 'Refresh Now' button.",
                        "data": [],
                        "count": 0,
                        "message": "No stock data found in database. Please refresh data from APIs."
                    }
                
                # Provide more specific message
                if source_stock_count == 0:
                    return {
                        "success": True,
                        "data": [],
                        "count": 0,
                        "message": f"Source branch ({source_branch}) has no stock data. Please refresh stock data.",
                        "diagnostics": {
                            "source_branch_stock_count": source_stock_count,
                            "target_branch_stock_count": target_stock_count
                        }
                    }
            except Exception as e:
                logger.error(f"Error checking database: {e}")
            
            return {
                "success": True,
                "data": [],
                "count": 0,
                "message": f"No priority items found. Source ({source_branch}) may have all items that target ({target_branch}) needs, or target already has sufficient stock. Try selecting different branches."
            }
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        error_msg = str(e)
        logger.error(f"❌ Error in get_priority_items: {error_msg}")
        logger.error(f"Full traceback:\n{error_traceback}")
        
        # Check if it's the db_path error specifically
        if "db_path" in error_msg.lower() or "db_path" in error_traceback.lower():
            logger.error("🔍 Detected db_path error - this should be fixed now with db_path as regular attribute")
            # Try to provide helpful error message
            error_msg = f"Database configuration error (fixed): {error_msg}. Please refresh the page."
        
        return {
            "success": False,
            "error": error_msg,
            "traceback": error_traceback,
            "data": [],
            "count": 0
        }

@router.get("/diagnostics")
async def get_database_diagnostics(
    current_user: dict = Depends(get_current_user),
    db_manager = Depends(get_db_manager)
):
    """Get database diagnostics to help troubleshoot empty data issues"""
    # Always PostgreSQL
    diagnostics = {
        "database_path": "Supabase PostgreSQL",
        "database_exists": False,
        "database_size_mb": 0,
        "tables": {},
        "summary": {}
    }
    
    try:
        # Always PostgreSQL - use database manager queries
        diagnostics["database_exists"] = True
        diagnostics["database_size_mb"] = None  # PostgreSQL doesn't have file size
        
        # Get table counts from PostgreSQL
        try:
            # Query information_schema to get all tables
            tables_result = db_manager.execute_query("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """)
            tables = [row['table_name'] for row in tables_result] if tables_result else []
            
            # Count rows in each table
            for table in tables:
                try:
                    result = db_manager.execute_query(f"SELECT COUNT(*) as count FROM {table}")
                    count = result[0]['count'] if result else 0
                    diagnostics["tables"][table] = count
                except Exception as e:
                    diagnostics["tables"][table] = f"Error: {str(e)}"
            
            # Summary
            key_tables = ['current_stock', 'supplier_invoices', 'purchase_orders', 'branch_orders', 'hq_invoices']
            diagnostics["summary"] = {
                "has_stock_data": diagnostics["tables"].get('current_stock', 0) > 0,
                "has_order_data": diagnostics["tables"].get('purchase_orders', 0) > 0 or diagnostics["tables"].get('branch_orders', 0) > 0,
                "has_invoice_data": diagnostics["tables"].get('supplier_invoices', 0) > 0 or diagnostics["tables"].get('hq_invoices', 0) > 0,
                "total_tables": len(tables),
                "key_table_counts": {table: diagnostics["tables"].get(table, 0) for table in key_tables}
            }
            
            if not diagnostics["summary"]["has_stock_data"]:
                diagnostics["message"] = "⚠️ Database has no stock data. Data refreshes automatically every hour."
            elif diagnostics["summary"]["has_stock_data"] and diagnostics["summary"]["has_order_data"]:
                diagnostics["message"] = "✅ Database appears to have data. If tables are still empty, check branch selection or query filters."
            else:
                diagnostics["message"] = "⚠️ Database has stock data but may be missing order data. Wait for next scheduled refresh."
        except Exception as e:
            diagnostics["error"] = str(e)
            diagnostics["message"] = f"Error checking database: {str(e)}"
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
    """Get database sync status - shows database connection status and credential status"""
    import os
    from app.config import settings
    from app.dependencies import get_credential_manager
    
    # Check if using Supabase or SQLite
    is_supabase = hasattr(db_manager, 'pool')
    
    # Check credentials status
    cred_manager = get_credential_manager()
    cred_status = {}
    missing_credentials = []
    for company in ["NILA", "DAIMA"]:
        creds = cred_manager.get_credentials(company)
        configured = creds is not None and bool(creds.get('username')) and bool(creds.get('password'))
        cred_status[company] = {
            "configured": configured,
            "enabled": creds.get('enabled', False) if creds else False
        }
        if not configured:
            missing_credentials.append(company)
    
    status = {
        "database_type": "Supabase PostgreSQL" if is_supabase else "SQLite",
        "connected": True,
        "sync_status": "synced",  # Supabase is always synced (no sync needed)
        "message": "Database is connected and ready" if is_supabase else "Using local SQLite database"
    }
    
    try:
        # For Supabase, just verify connection
        if is_supabase:
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM current_stock")
            stock_count = cursor.fetchone()[0]
            cursor.close()
            db_manager.put_connection(conn)
            status["stock_records"] = stock_count
            status["message"] = f"Connected to Supabase - {stock_count:,} stock records available"
        else:
            # For SQLite, check file
            # Always PostgreSQL - no local database
            status["local_database"] = {
                "exists": False,
                "path": None,
                "message": "All data stored in Supabase PostgreSQL"
            }
            status["message"] = "Using Supabase PostgreSQL database"
    
    except Exception as e:
        status["sync_status"] = "error"
        status["message"] = f"Error checking sync status: {str(e)}"
        status["connected"] = False
        logger.error(f"Error getting sync status: {e}")
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(error_traceback)
        # Don't raise - return error in response so frontend can handle
        return {
            "success": False,
            "error": str(e),
            "status": status
        }
    
    # Add credentials status to response
    status["credentials"] = cred_status
    status["missing_credentials"] = missing_credentials
    if missing_credentials:
        status["credentials_message"] = f"⚠️ API credentials not configured for: {', '.join(missing_credentials)}. Please configure credentials in Settings to enable data refresh."
    
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
    """Get list of unique branches from current_stock table (matches desktop version behavior)"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Fetching branches from current_stock" + (f" for {company}" if company else ""))
        
        # Query current_stock directly like desktop version does
        # Desktop version: SELECT DISTINCT branch, company FROM current_stock ORDER BY company, branch
        # Use case-insensitive comparison and ensure we get all branches regardless of company case
        if company:
            query = """
                SELECT DISTINCT branch, company 
                FROM current_stock 
                WHERE UPPER(TRIM(company)) = UPPER(TRIM(%s))
                AND branch IS NOT NULL 
                AND TRIM(branch) != ''
                ORDER BY company, branch
            """
            params = (company,)
        else:
            query = """
                SELECT DISTINCT branch, company 
                FROM current_stock 
                WHERE branch IS NOT NULL 
                AND TRIM(branch) != ''
                AND company IS NOT NULL
                AND TRIM(company) != ''
                ORDER BY company, branch
            """
            params = None
        
        # Execute query using database manager
        result = db_manager.execute_query(query, params)
        logger.info(f"Query returned {len(result) if result else 0} rows")
        
        # Format branches like desktop version: [{"branch_name": "...", "company": "...", "branch_code": "..."}]
        branches = []
        if result:
            for row in result:
                branch_name = row.get('branch') or row.get('branch_name', '')
                branch_company = row.get('company') or row.get('company_name', '')
                if branch_name and branch_company:
                    branches.append({
                        "branch_name": branch_name.strip(),
                        "company": branch_company.strip(),
                        "branch_code": row.get('branch_code', ''),  # May not exist
                        "branch": branch_name.strip()  # For compatibility
                    })
        
        logger.info(f"Found {len(branches)} unique branches")
        
        # Diagnostic: Check what companies and branches are actually in the database
        try:
            diagnostic_query = """
                SELECT company, COUNT(DISTINCT branch) as branch_count, COUNT(*) as total_records
                FROM current_stock
                GROUP BY company
                ORDER BY company
            """
            diagnostic_result = db_manager.execute_query(diagnostic_query)
            logger.info(f"📊 Database diagnostic - Companies in current_stock:")
            for row in diagnostic_result:
                logger.info(f"   {row.get('company', 'Unknown')}: {row.get('branch_count', 0)} branches, {row.get('total_records', 0):,} records")
        except Exception as diag_error:
            logger.warning(f"Could not run diagnostic query: {diag_error}")
        
        if not branches:
            logger.warning("No branches found in current_stock table")
            # Check if we have data at all
            try:
                count_result = db_manager.execute_query("SELECT COUNT(*) as count FROM current_stock")
                stock_count = count_result[0]['count'] if count_result else 0
                logger.info(f"Database has {stock_count} stock records but no distinct branches found")
                if stock_count > 0:
                    logger.warning("⚠️ current_stock has data but no distinct branches - check branch/company columns")
                    # Try to see what columns exist
                    try:
                        sample_query = "SELECT * FROM current_stock LIMIT 1"
                        sample = db_manager.execute_query(sample_query)
                        if sample:
                            logger.info(f"Sample record columns: {list(sample[0].keys())}")
                    except:
                        pass
            except Exception as check_error:
                logger.error(f"Error checking stock count: {check_error}")
        
        return {
            "success": True,
            "data": branches
        }
    except Exception as e:
        logger.error(f"Error getting branches: {e}")
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(error_traceback)
        
        # Return proper error response (don't raise HTTPException to avoid 500)
        # Return 200 with error details so frontend can handle gracefully
        return {
            "success": False,
            "error": str(e),
            "data": [],
            "message": f"Failed to load branches: {str(e)}",
            "traceback": error_traceback
        }

@router.get("/items")
async def get_items(
    branch: Optional[str] = None,
    company: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db_manager = Depends(get_db_manager)
):
    """Get list of unique items from current_stock table"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Fetching items" + (f" for branch={branch}, company={company}" if branch or company else ""))
        
        # Build query to get unique items from current_stock
        if branch and company:
            query = """
                SELECT DISTINCT 
                    item_code,
                    MAX(item_name) as item_name,
                    MAX(company) as company,
                    MAX(branch) as branch
                FROM current_stock
                WHERE branch = %s AND company = %s
                GROUP BY item_code
                ORDER BY item_code
            """
            params = (branch, company)
        elif company:
            query = """
                SELECT DISTINCT 
                    item_code,
                    MAX(item_name) as item_name,
                    MAX(company) as company
                FROM current_stock
                WHERE company = %s
                GROUP BY item_code
                ORDER BY item_code
            """
            params = (company,)
        else:
            query = """
                SELECT DISTINCT 
                    item_code,
                    MAX(item_name) as item_name
                FROM current_stock
                GROUP BY item_code
                ORDER BY item_code
            """
            params = None
        
        items = db_manager.execute_query(query, params)
        logger.info(f"Found {len(items)} unique items")
        
        return {
            "success": True,
            "data": items,
            "count": len(items)
        }
    except Exception as e:
        logger.error(f"Error getting items: {e}")
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(error_traceback)
        
        return {
            "success": False,
            "error": str(e),
            "data": [],
            "count": 0,
            "message": f"Failed to load items: {str(e)}"
        }

