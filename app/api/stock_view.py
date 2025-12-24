"""
Stock View API Routes
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional
from app.dependencies import get_current_user, get_db_manager
import sys
import os
import logging

# Set up logger first
logger = logging.getLogger(__name__)

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
    import asyncio
    
    try:
        if StockViewService is None:
            return {
                "success": False,
                "error": "StockViewService not available - parent directory import failed",
                "data": [],
                "count": 0
            }
        
        logger.info(f"Stock view request: branch={branch_name}, company={branch_company}, source={source_branch_name}, source_company={source_branch_company}")
        
        # ALL data is in Supabase PostgreSQL
        logger.info("Using Supabase PostgreSQL database")
        
        # Use defaults if not provided
        if not source_branch_name:
            source_branch_name = "BABA DOGO HQ"
        if not source_branch_company:
            source_branch_company = branch_company
        
        logger.info(f"Calling stock view service with: branch={branch_name}, company={branch_company}, source={source_branch_name}, source_company={source_branch_company}")
        
        # Use PostgreSQL-compatible stock view service
        try:
            from app.services.stock_view_service_postgres import StockViewServicePostgres
            stock_service = StockViewServicePostgres(db_manager)
            
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
            
            rows_returned = len(stock_data) if stock_data is not None and not stock_data.empty else 0
            logger.info(f"Stock view service returned: {rows_returned} rows")
            if rows_returned == 0:
                logger.warning(f"⚠️ Stock view returned empty - branch={branch_name}, company={branch_company}, source={source_branch_name}, source_company={source_branch_company}")
        except ImportError as e:
            logger.error(f"Could not import StockViewServicePostgres: {e}")
            return {
                "success": False,
                "error": f"Stock view service not available: {str(e)}",
                "data": [],
                "count": 0
            }
        except Exception as e:
            logger.error(f"Error calling stock view service: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": f"Error loading stock data: {str(e)}",
                "data": [],
                "count": 0,
                "traceback": traceback.format_exc()
            }
        
        # Check if database has data if stock_data is empty
        if (stock_data is None or stock_data.empty):
            logger.warning("⚠️ Stock view returned empty data, checking database...")
            try:
                # Check if PostgreSQL
                is_postgres = hasattr(db_manager, 'connection_string') or hasattr(db_manager, 'pool') or 'PostgresDatabaseManager' in str(type(db_manager))
                
                # Always PostgreSQL - use database manager's execute_query
                from app.services.dashboard_service import DashboardService
                dashboard_service = DashboardService(db_manager)
                stock_count_result = dashboard_service._execute_query("SELECT COUNT(*) as count FROM current_stock")
                stock_count = stock_count_result[0]['count'] if stock_count_result else 0
                
                # Try stock_data table (might not exist)
                try:
                    stock_data_result = dashboard_service._execute_query("SELECT COUNT(*) as count FROM stock_data")
                    stock_data_count = stock_data_result[0]['count'] if stock_data_result else 0
                except:
                    stock_data_count = 0
                
                logger.info(f"📋 Database check: current_stock={stock_count} rows, stock_data={stock_data_count} rows")
                
                if stock_count == 0 and stock_data_count == 0:
                    return {
                        "success": False,
                        "error": "Database is empty. Please refresh data first by clicking 'Refresh Now' button.",
                        "data": [],
                        "count": 0,
                        "diagnostics": {
                            "database_path": "Supabase PostgreSQL",
                            "database_exists": True,
                            "current_stock_rows": stock_count,
                            "stock_data_rows": stock_data_count,
                            "message": "No stock data found. Please refresh data from APIs."
                        }
                    }
            except Exception as e:
                logger.error(f"Error checking database: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
        # Convert DataFrame to dict - replace NaN with None for JSON serialization
        if stock_data is not None and not stock_data.empty:
            try:
                # Replace NaN/NaT values with None for JSON serialization
                import numpy as np
                import pandas as pd
                
                # Convert all datetime columns to strings first
                for col in stock_data.columns:
                    if pd.api.types.is_datetime64_any_dtype(stock_data[col]):
                        stock_data[col] = stock_data[col].dt.strftime('%Y-%m-%d').replace('NaT', None)
                
                # Replace NaN/NaT/Inf values
                stock_data = stock_data.replace([np.nan, np.inf, -np.inf], None)
                
                # Convert to dict
                records = stock_data.to_dict('records')
                
                # Final cleanup - ensure all problematic values are None
                for record in records:
                    for key, value in record.items():
                        if value is None:
                            continue
                        if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
                            record[key] = None
                        elif isinstance(value, pd.Timestamp):
                            record[key] = value.strftime('%Y-%m-%d') if pd.notna(value) else None
                        elif str(value) in ['NaT', 'nan', 'NaN']:
                            record[key] = None
                
                logger.info(f"✅ Successfully converted {len(records)} records to JSON format")
                return {
                    "success": True,
                    "data": records,
                    "count": len(stock_data)
                }
            except Exception as convert_error:
                logger.error(f"Error converting DataFrame to JSON: {convert_error}")
                import traceback
                logger.error(traceback.format_exc())
                return {
                    "success": False,
                    "error": f"Error formatting data for display: {str(convert_error)}",
                    "data": [],
                    "count": 0
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

