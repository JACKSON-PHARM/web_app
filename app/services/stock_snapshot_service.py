"""
Stock Snapshot Service - PostgreSQL-First Implementation
Uses stock_snapshot() function as single source of truth
No pandas, no materialized views, no CSV merges
"""
import logging
from typing import List, Dict, Optional
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

class StockSnapshotService:
    """
    Service for querying stock snapshot using canonical PostgreSQL function
    Replaces pandas merges and materialized views
    """
    
    def __init__(self, db_manager):
        """Initialize with PostgreSQL database manager"""
        self.db_manager = db_manager
        if not (hasattr(db_manager, 'connection_string') or hasattr(db_manager, 'pool')):
            raise ValueError("StockSnapshotService requires PostgresDatabaseManager")
        logger.info("StockSnapshotService initialized - using stock_snapshot() function")
    
    def get_snapshot(self, target_branch: str, source_branch: str, company: str) -> List[Dict]:
        """
        Get complete stock snapshot using canonical function
        
        Args:
            target_branch: Branch to analyze
            source_branch: Source branch for stock comparison
            company: Company name (NILA or DAIMA)
            
        Returns:
            List of dictionaries with all stock snapshot data
        """
        conn = None
        cursor = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT * FROM stock_snapshot(%s, %s, %s)
            """, (target_branch, source_branch, company))
            
            results = cursor.fetchall()
            logger.info(f"✅ Retrieved {len(results)} items from stock_snapshot()")
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"❌ Error getting stock snapshot: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.db_manager.put_connection(conn)
    
    def get_priority_items(self, target_branch: str, source_branch: str, company: str,
                          priority_only: bool = True, days: Optional[int] = None) -> List[Dict]:
        """
        Get priority items using stock_snapshot function
        
        Args:
            target_branch: Target branch
            source_branch: Source branch
            company: Company name
            priority_only: If True, only return LOW/RECENT_ORDER/RECENT_INVOICE
            days: Filter by recent activity (last N days)
            
        Returns:
            List of priority items
        """
        conn = None
        cursor = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            query = """
                SELECT * FROM stock_snapshot(%s, %s, %s)
                WHERE 1=1
            """
            params = [target_branch, source_branch, company]
            
            if priority_only:
                query += " AND priority_flag IN ('LOW', 'RECENT_ORDER', 'RECENT_INVOICE')"
            
            if days:
                query += """
                    AND (
                        last_order_date >= CURRENT_DATE - INTERVAL '%s days'
                        OR last_invoice_date >= CURRENT_DATE - INTERVAL '%s days'
                        OR last_supplier_invoice_date >= CURRENT_DATE - INTERVAL '%s days'
                    )
                """
                params.extend([days, days, days])
            
            query += " ORDER BY priority_flag, item_code"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            logger.info(f"✅ Retrieved {len(results)} priority items")
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"❌ Error getting priority items: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.db_manager.put_connection(conn)
    
    def get_new_arrivals(self, branch: str, company: str, days: int = 7) -> List[Dict]:
        """
        Get new arrivals (items with recent orders/invoices)
        
        Args:
            branch: Branch to check
            company: Company name
            days: Number of days to look back
            
        Returns:
            List of new arrival items
        """
        conn = None
        cursor = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT * FROM stock_snapshot(%s, %s, %s)
                WHERE (
                    last_order_date >= CURRENT_DATE - INTERVAL '%s days'
                    OR last_invoice_date >= CURRENT_DATE - INTERVAL '%s days'
                    OR last_supplier_invoice_date >= CURRENT_DATE - INTERVAL '%s days'
                )
                ORDER BY 
                    COALESCE(last_order_date, last_invoice_date, last_supplier_invoice_date) DESC,
                    item_code
            """, (branch, branch, company, days, days, days))
            
            results = cursor.fetchall()
            logger.info(f"✅ Retrieved {len(results)} new arrivals")
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"❌ Error getting new arrivals: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.db_manager.put_connection(conn)
    
    def get_low_stock_items(self, branch: str, company: str, 
                           threshold_pct: float = 30.0) -> List[Dict]:
        """
        Get items with low stock levels
        
        Args:
            branch: Branch to check
            company: Company name
            threshold_pct: Stock level percentage threshold (default 30%)
            
        Returns:
            List of low stock items
        """
        conn = None
        cursor = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT * FROM stock_snapshot(%s, %s, %s)
                WHERE priority_flag = 'LOW'
                   OR stock_level_vs_amc < %s
                ORDER BY stock_level_vs_amc ASC, item_code
            """, (branch, branch, company, threshold_pct))
            
            results = cursor.fetchall()
            logger.info(f"✅ Retrieved {len(results)} low stock items")
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"❌ Error getting low stock items: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.db_manager.put_connection(conn)

