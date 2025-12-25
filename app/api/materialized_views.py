"""
API endpoint to refresh materialized views
Can be called by scheduler or manually
"""
from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import get_current_user, get_db_manager
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/refresh")
async def refresh_materialized_views(
    current_user: dict = Depends(get_current_user),
    db_manager = Depends(get_db_manager)
):
    """Refresh materialized views - can be called by scheduler or manually"""
    try:
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        logger.info("🔄 Refreshing materialized views...")
        
        # Try to use the PostgreSQL function if it exists
        try:
            cursor.execute("SELECT refresh_materialized_views()")
            result = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            db_manager.put_connection(conn)
            
            logger.info(f"✅ Refreshed materialized views via function: {result}")
            return {
                "success": True,
                "message": "Materialized views refreshed successfully",
                "details": result
            }
        except Exception as func_error:
            # Function doesn't exist or failed, use direct refresh
            logger.warning(f"⚠️ Refresh function not available, using direct refresh: {func_error}")
            conn.rollback()
            
            # Refresh views directly
            try:
                cursor.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY stock_view_materialized")
                logger.info("✅ Refreshed stock_view_materialized")
            except Exception as e:
                # Try without CONCURRENTLY
                cursor.execute("REFRESH MATERIALIZED VIEW stock_view_materialized")
                logger.info("✅ Refreshed stock_view_materialized (without CONCURRENTLY)")
            
            try:
                cursor.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY priority_items_materialized")
                logger.info("✅ Refreshed priority_items_materialized")
            except Exception as e:
                # Try without CONCURRENTLY
                cursor.execute("REFRESH MATERIALIZED VIEW priority_items_materialized")
                logger.info("✅ Refreshed priority_items_materialized (without CONCURRENTLY)")
            
            conn.commit()
            cursor.close()
            db_manager.put_connection(conn)
            
            return {
                "success": True,
                "message": "Materialized views refreshed successfully (direct refresh)"
            }
            
    except Exception as e:
        logger.error(f"❌ Error refreshing materialized views: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if conn:
            try:
                conn.rollback()
                cursor.close()
                db_manager.put_connection(conn)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Error refreshing views: {str(e)}")

