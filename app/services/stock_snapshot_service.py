"""
Stock Snapshot Service - PostgreSQL-First Implementation
NO MATERIALIZED VIEWS - Direct table queries only
Handles stock_string parsing and priority computation in Python
"""
import logging
import re
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

class StockSnapshotService:
    """
    Service for querying stock snapshot using canonical PostgreSQL function
    NO materialized views, NO pandas, NO CSV
    """
    
    def __init__(self, db_manager):
        """Initialize with PostgreSQL database manager"""
        self.db_manager = db_manager
        if not (hasattr(db_manager, 'connection_string') or hasattr(db_manager, 'pool')):
            raise ValueError("StockSnapshotService requires PostgresDatabaseManager")
        logger.info("StockSnapshotService initialized - using stock_snapshot() function (NO materialized views)")
    
    def parse_stock_string(self, stock_string: str, pack_size: float) -> float:
        """
        Parse stock_string to total pieces
        
        Format: "XWYP" where:
        - X = whole packs (before 'W')
        - Y = loose pieces (before 'P')
        
        Returns: total_pieces = (whole_packs × pack_size) + loose_pieces
        """
        if not stock_string or not isinstance(stock_string, str) or stock_string in ['nan', 'None', '']:
            return 0.0
        
        # Ensure pack_size is valid
        if pack_size <= 0:
            pack_size = 1.0
        
        # Extract whole packs (digits before 'W')
        whole_match = re.search(r'(\d+)W', stock_string)
        whole_packs = int(whole_match.group(1)) if whole_match else 0
        
        # Extract loose pieces (digits before 'P')
        pieces_match = re.search(r'(\d+)P', stock_string)
        loose_pieces = int(pieces_match.group(1)) if pieces_match else 0
        
        # Calculate total pieces: (whole_packs × pack_size) + loose_pieces
        total_pieces = (float(whole_packs) * float(pack_size)) + float(loose_pieces)
        return float(total_pieces)
    
    def compute_stock_level_pct(self, total_pieces: float, amc_packs: float, pack_size: float) -> float:
        """
        Compute stock level percentage
        
        stock_level_pct = (total_pieces / amc_pieces) * 100
        where amc_pieces = amc_packs × pack_size
        """
        if amc_packs <= 0 or pack_size <= 0:
            return 0.0
        
        amc_pieces = amc_packs * pack_size
        if amc_pieces <= 0:
            return 0.0
        
        stock_level_pct = (total_pieces / amc_pieces) * 100
        return round(stock_level_pct, 2)
    
    def compute_priority_flag(self, stock_level_pct: float, last_order_date: Optional[datetime], 
                            last_invoice_date: Optional[datetime]) -> str:
        """
        Compute priority flag based on business rules
        
        LOW             → stock_level_pct < 30
        RECENT_ORDER    → last_order_date within 7 days
        RECENT_INVOICE  → last_invoice_date within 7 days
        NORMAL          → otherwise
        """
        # Check recent activity first (takes precedence)
        today = datetime.now().date()
        seven_days_ago = today - timedelta(days=7)
        
        if last_order_date and isinstance(last_order_date, (datetime, type(today))):
            order_date = last_order_date.date() if isinstance(last_order_date, datetime) else last_order_date
            if order_date >= seven_days_ago:
                return 'RECENT_ORDER'
        
        if last_invoice_date and isinstance(last_invoice_date, (datetime, type(today))):
            invoice_date = last_invoice_date.date() if isinstance(last_invoice_date, datetime) else last_invoice_date
            if invoice_date >= seven_days_ago:
                return 'RECENT_INVOICE'
        
        # Check stock level
        if stock_level_pct < 30:
            return 'LOW'
        
        return 'NORMAL'
    
    def get_snapshot(self, target_branch: str, source_branch: str, company: str) -> List[Dict]:
        """
        Get complete stock snapshot using canonical function
        
        Args:
            target_branch: Branch to analyze
            source_branch: Source branch for stock comparison
            company: Company name (NILA or DAIMA)
            
        Returns:
            List of dictionaries with all stock snapshot data (computed fields included)
        """
        conn = None
        cursor = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT * FROM stock_snapshot(%s::text, %s::text, %s::text)
            """, (target_branch, source_branch, company))
            
            raw_results = cursor.fetchall()
            logger.info(f"✅ Retrieved {len(raw_results)} items from stock_snapshot()")
            
            # Process results: parse stock_string and compute fields
            processed_results = []
            for row in raw_results:
                row_dict = dict(row)
                
                # Ensure pack_size is float (PostgreSQL NUMERIC returns as Decimal)
                pack_size = float(row_dict.get('pack_size', 1))
                if pack_size <= 0:
                    pack_size = 1.0
                
                # Parse stock_string to get total pieces for target branch
                target_stock_string = str(row_dict.get('target_stock_display', '0W0P'))
                if target_stock_string in ['nan', 'None', '']:
                    target_stock_string = '0W0P'
                
                target_total_pieces = self.parse_stock_string(target_stock_string, pack_size)
                
                # Get AMC in packs (adjusted_amc from inventory_analysis_new is stored in PACKS)
                # Convert to pieces exactly once for stock calculations
                adjusted_amc_packs_raw = row_dict.get('adjusted_amc_packs', 0)
                # Handle Decimal type from PostgreSQL
                if hasattr(adjusted_amc_packs_raw, '__float__'):
                    adjusted_amc_packs = float(adjusted_amc_packs_raw)
                else:
                    adjusted_amc_packs = float(adjusted_amc_packs_raw) if adjusted_amc_packs_raw else 0.0
                
                # Convert AMC from packs to pieces for stock percentage calculation
                amc_pieces = adjusted_amc_packs * pack_size
                
                # CRITICAL: Calculate stock_level_pct ONCE here - this is the ONLY place it's calculated
                # Formula: stock_level_pct = (target_total_pieces / amc_pieces) * 100
                # Both values must be in PIECES for correct calculation
                if amc_pieces <= 0:
                    stock_level_pct = 0.0
                else:
                    stock_level_pct = (target_total_pieces / amc_pieces) * 100
                    stock_level_pct = round(stock_level_pct, 2)
                
                # Store the calculated value - this is READ-ONLY for StockViewServicePostgres
                row_dict['stock_level_pct'] = stock_level_pct
                
                # Log first few items for debugging (verify calculation)
                if len(processed_results) < 3:
                    logger.info(f"Stock level calc: item={row_dict.get('item_code')}, "
                               f"stock_string={target_stock_string}, pack_size={pack_size}, "
                               f"target_pieces={target_total_pieces}, adjusted_amc_packs={adjusted_amc_packs}, "
                               f"amc_pieces={amc_pieces}, stock_level_pct={stock_level_pct}%")
                    # Verify calculation
                    expected = (target_total_pieces / amc_pieces) * 100 if amc_pieces > 0 else 0.0
                    logger.info(f"   Verification: ({target_total_pieces} pieces / {amc_pieces} pieces) * 100 = {expected:.2f}%")
                
                # Compute priority flag (from dates and stock level)
                last_order_date = row_dict.get('last_order_date')
                last_invoice_date = row_dict.get('last_invoice_date')
                last_supplier_invoice_date = row_dict.get('last_supplier_invoice_date')
                priority_flag = self.compute_priority_flag(stock_level_pct, last_order_date, last_invoice_date)
                row_dict['priority_flag'] = priority_flag
                
                # Add computed fields for compatibility
                row_dict['target_total_pieces'] = target_total_pieces
                row_dict['amc_pieces'] = amc_pieces  # AMC in pieces (converted from packs)
                row_dict['adjusted_amc_packs'] = adjusted_amc_packs  # Store original packs value for display
                
                processed_results.append(row_dict)
            
            logger.info(f"✅ Processed {len(processed_results)} items with computed fields")
            return processed_results
            
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
        # Get full snapshot
        all_items = self.get_snapshot(target_branch, source_branch, company)
        
        # Filter in Python (NO SQL filtering on stock_string)
        filtered_items = []
        for item in all_items:
            # Filter by priority flag
            if priority_only:
                if item.get('priority_flag') not in ['LOW', 'RECENT_ORDER', 'RECENT_INVOICE']:
                    continue
            
            # Filter by source stock availability (parse source stock_string)
            source_stock_string = item.get('source_stock_display', '0W0P')
            pack_size = float(item.get('pack_size', 1))
            source_total_pieces = self.parse_stock_string(source_stock_string, pack_size)
            
            if source_total_pieces <= 0:
                continue
            
            # Filter by target stock (low stock needed)
            target_stock_string = item.get('target_stock_display', '0W0P')
            target_total_pieces = self.parse_stock_string(target_stock_string, pack_size)
            
            if target_total_pieces >= 1000:  # Has sufficient stock
                continue
            
            # Filter by date if specified
            if days:
                today = datetime.now().date()
                cutoff_date = today - timedelta(days=days)
                
                last_order = item.get('last_order_date')
                last_invoice = item.get('last_invoice_date')
                last_supplier_invoice = item.get('last_supplier_invoice_date')
                
                has_recent_activity = False
                if last_order:
                    order_date = last_order.date() if isinstance(last_order, datetime) else last_order
                    if order_date >= cutoff_date:
                        has_recent_activity = True
                if last_invoice:
                    invoice_date = last_invoice.date() if isinstance(last_invoice, datetime) else last_invoice
                    if invoice_date >= cutoff_date:
                        has_recent_activity = True
                if last_supplier_invoice:
                    supplier_date = last_supplier_invoice.date() if isinstance(last_supplier_invoice, datetime) else last_supplier_invoice
                    if supplier_date >= cutoff_date:
                        has_recent_activity = True
                
                if not has_recent_activity:
                    continue
            
            filtered_items.append(item)
        
        # Sort by source stock (descending)
        filtered_items.sort(key=lambda x: self.parse_stock_string(x.get('source_stock_display', '0W0P'), 
                                                                  float(x.get('pack_size', 1))), 
                           reverse=True)
        
        logger.info(f"✅ Filtered to {len(filtered_items)} priority items")
        return filtered_items
    
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
        # Get snapshot (target = source = branch for new arrivals)
        all_items = self.get_snapshot(branch, branch, company)
        
        # Filter by recent activity
        today = datetime.now().date()
        cutoff_date = today - timedelta(days=days)
        
        new_arrivals = []
        for item in all_items:
            last_order = item.get('last_order_date')
            last_invoice = item.get('last_invoice_date')
            last_supplier_invoice = item.get('last_supplier_invoice_date')
            
            has_recent_activity = False
            
            if last_order:
                order_date = last_order.date() if isinstance(last_order, datetime) else last_order
                if order_date >= cutoff_date:
                    has_recent_activity = True
            
            if last_invoice:
                invoice_date = last_invoice.date() if isinstance(last_invoice, datetime) else last_invoice
                if invoice_date >= cutoff_date:
                    has_recent_activity = True
            
            if last_supplier_invoice:
                supplier_date = last_supplier_invoice.date() if isinstance(last_supplier_invoice, datetime) else last_supplier_invoice
                if supplier_date >= cutoff_date:
                    has_recent_activity = True
            
            if has_recent_activity:
                new_arrivals.append(item)
        
        # Sort by most recent activity
        new_arrivals.sort(key=lambda x: max(
            x.get('last_order_date') or datetime.min,
            x.get('last_invoice_date') or datetime.min,
            x.get('last_supplier_invoice_date') or datetime.min
        ), reverse=True)
        
        logger.info(f"✅ Retrieved {len(new_arrivals)} new arrivals")
        return new_arrivals
