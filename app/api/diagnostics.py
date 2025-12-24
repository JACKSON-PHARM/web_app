"""
Diagnostic API Routes - Check database connection and data
"""
from fastapi import APIRouter, Depends
from app.dependencies import get_current_user, get_db_manager
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/database-check")
async def check_database(
    current_user: dict = Depends(get_current_user),
    db_manager = Depends(get_db_manager)
):
    """Comprehensive database diagnostic - check connection and data"""
    
    results = {
        "database_type": "Unknown",
        "connected": False,
        "connection_string_set": False,
        "tables": {},
        "errors": []
    }
    
    try:
        # Check if using Supabase
        is_supabase = hasattr(db_manager, 'pool') or hasattr(db_manager, 'connection_string')
        results["database_type"] = "Supabase PostgreSQL" if is_supabase else "SQLite"
        results["connected"] = True
        
        # Check connection string
        if hasattr(db_manager, 'connection_string'):
            results["connection_string_set"] = True
            # Mask password in connection string
            conn_str = db_manager.connection_string
            if '@' in conn_str:
                parts = conn_str.split('@')
                if ':' in parts[0]:
                    user_pass = parts[0].split(':')
                    masked = f"{user_pass[0]}:****@{parts[1]}"
                    results["connection_string"] = masked
        else:
            results["connection_string_set"] = False
        
        # Check each table
        tables_to_check = [
            'current_stock',
            'supplier_invoices',
            'grn',
            'purchase_orders',
            'branch_orders',
            'hq_invoices',
            'inventory_analysis'
        ]
        
        conn = None
        try:
            if is_supabase:
                conn = db_manager.get_connection()
                cursor = conn.cursor()
                
                for table in tables_to_check:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        results["tables"][table] = {
                            "exists": True,
                            "record_count": count
                        }
                    except Exception as e:
                        results["tables"][table] = {
                            "exists": False,
                            "error": str(e)
                        }
                        results["errors"].append(f"Table {table}: {str(e)}")
                
                cursor.close()
                db_manager.put_connection(conn)
            else:
                # SQLite - check file
                db_path = getattr(db_manager, 'db_path', None)
                if db_path:
                    results["db_path"] = db_path
                    import os
                    results["db_file_exists"] = os.path.exists(db_path) if db_path else False
                else:
                    # PostgreSQL - no file path
                    results["db_path"] = "Supabase PostgreSQL"
                    results["db_file_exists"] = True
                
        except Exception as e:
            results["errors"].append(f"Connection error: {str(e)}")
            logger.error(f"Database check error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            if conn:
                try:
                    cursor.close()
                    db_manager.put_connection(conn)
                except:
                    pass
        
        # Summary
        total_records = sum(t.get("record_count", 0) for t in results["tables"].values() if isinstance(t, dict) and "record_count" in t)
        results["summary"] = {
            "total_records": total_records,
            "tables_with_data": len([t for t in results["tables"].values() if isinstance(t, dict) and t.get("record_count", 0) > 0]),
            "has_data": total_records > 0
        }
        
    except Exception as e:
        results["connected"] = False
        results["errors"].append(f"Failed to check database: {str(e)}")
        logger.error(f"Database check failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    return {
        "success": True,
        "diagnostics": results
    }

