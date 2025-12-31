"""
Sanity Check Service
Validates data freshness and correctness after refresh operations
"""
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple
from app.services.refresh_status import RefreshStatusService

logger = logging.getLogger(__name__)


class SanityCheckService:
    """Service for validating data sanity after refresh"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
    
    def check_document_sanity(self, branch_name: str, company: str, 
                             document_type: str) -> Tuple[bool, Optional[str]]:
        """
        Check if branch has documents with today or yesterday date.
        
        Rule: For document-based reports (orders, supplies, etc):
        - For each branch: There must exist at least one document with:
          - document_date = today OR
          - document_date = yesterday
        - If no such document exists → branch is FAILED
        
        This accounts for weekends and holidays (no calendar logic needed yet).
        
        Args:
            branch_name: Branch name to check
            company: Company name
            document_type: "purchase_orders", "branch_orders", or "supplier_invoices"
        
        Returns:
            Tuple[bool, Optional[str]]: (is_sane, reason_if_failed)
        """
        try:
            today = date.today()
            yesterday = today - timedelta(days=1)
            
            today_str = today.strftime('%Y-%m-%d')
            yesterday_str = yesterday.strftime('%Y-%m-%d')
            
            # Map document_type to table name
            table_map = {
                "purchase_orders": "purchase_orders",
                "branch_orders": "branch_orders",
                "supplier_invoices": "supplier_invoices"
            }
            
            if document_type not in table_map:
                return False, f"Unknown document type: {document_type}"
            
            table_name = table_map[document_type]
            
            # Determine branch column based on document type
            if document_type == "branch_orders":
                branch_column = "source_branch"
            else:
                branch_column = "branch"
            
            # Query for documents with today or yesterday date
            query = f"""
                SELECT COUNT(*) as count
                FROM {table_name}
                WHERE UPPER(TRIM({branch_column})) = UPPER(TRIM(%s))
                  AND UPPER(TRIM(company)) = UPPER(TRIM(%s))
                  AND document_date IN (%s, %s)
            """
            
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            try:
                cursor.execute(query, (branch_name, company, today_str, yesterday_str))
                result = cursor.fetchone()
                count = result[0] if result else 0
                
                if count > 0:
                    self.logger.info(f"✅ {branch_name} ({document_type}): Found {count} document(s) with today/yesterday date")
                    return True, None
                else:
                    reason = f"No documents with date {today_str} or {yesterday_str}"
                    self.logger.warning(f"❌ {branch_name} ({document_type}): {reason}")
                    return False, reason
                    
            finally:
                cursor.close()
                self.db_manager.put_connection(conn)
                
        except Exception as e:
            self.logger.error(f"❌ Error checking document sanity for {branch_name} ({document_type}): {e}")
            return False, f"Error checking documents: {str(e)}"
    
    def check_stock_sanity(self, branch_name: str, company: str, 
                          refresh_started: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Check if stock data is sane for a branch.
        
        Rules:
        - Stock rows exist after refresh
        - Old stock rows for that branch were deleted
        - No stock rows remain with source_updated < refresh_started
        
        Args:
            branch_name: Branch name to check
            company: Company name
            refresh_started: ISO timestamp when refresh started (optional)
        
        Returns:
            Tuple[bool, Optional[str]]: (is_sane, reason_if_failed)
        """
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            try:
                # Check 1: Stock rows exist for this branch
                query = """
                    SELECT COUNT(*) as count
                    FROM current_stock
                    WHERE UPPER(TRIM(branch)) = UPPER(TRIM(%s))
                      AND UPPER(TRIM(company)) = UPPER(TRIM(%s))
                """
                cursor.execute(query, (branch_name, company))
                result = cursor.fetchone()
                stock_count = result[0] if result else 0
                
                if stock_count == 0:
                    reason = "No stock rows found after refresh"
                    self.logger.warning(f"❌ {branch_name} (stock): {reason}")
                    return False, reason
                
                self.logger.info(f"✅ {branch_name} (stock): Found {stock_count} stock rows")
                
                # Check 2: If refresh_started provided, check for stale rows
                if refresh_started:
                    try:
                        refresh_dt = datetime.fromisoformat(refresh_started.replace('Z', '+00:00'))
                        refresh_str = refresh_dt.strftime('%Y-%m-%d %H:%M:%S')
                        
                        # Check for rows with source_updated < refresh_started
                        stale_query = """
                            SELECT COUNT(*) as count
                            FROM current_stock
                            WHERE UPPER(TRIM(branch)) = UPPER(TRIM(%s))
                              AND UPPER(TRIM(company)) = UPPER(TRIM(%s))
                              AND source_updated < %s
                        """
                        cursor.execute(stale_query, (branch_name, company, refresh_str))
                        stale_result = cursor.fetchone()
                        stale_count = stale_result[0] if stale_result else 0
                        
                        if stale_count > 0:
                            reason = f"Found {stale_count} stale stock rows with source_updated < refresh_started"
                            self.logger.warning(f"❌ {branch_name} (stock): {reason}")
                            return False, reason
                        
                        self.logger.info(f"✅ {branch_name} (stock): No stale rows found")
                    except Exception as e:
                        self.logger.warning(f"⚠️ Could not check stale rows for {branch_name}: {e}")
                        # Don't fail sanity check if we can't check stale rows - just log warning
                
                return True, None
                
            finally:
                cursor.close()
                self.db_manager.put_connection(conn)
                
        except Exception as e:
            self.logger.error(f"❌ Error checking stock sanity for {branch_name}: {e}")
            return False, f"Error checking stock: {str(e)}"
    
    def check_all_branches_sanity(self, branches: List[Dict], refresh_started: Optional[str] = None) -> Dict:
        """
        Check sanity for all branches across all report types.
        
        Args:
            branches: List of branch dicts with "branch_name", "company", and optionally "branchcode"
            refresh_started: ISO timestamp when refresh started
        
        Returns:
            Dict with structure:
            {
                "branches": {
                    "BranchName": {
                        "status": "success" | "failed",
                        "reason": "..." (if failed)
                    }
                },
                "reports": {
                    "stock": "success" | "partial" | "failed",
                    "orders": "success" | "partial" | "failed",
                    "supplier_invoices": "success" | "partial" | "failed"
                }
            }
        """
        result = {
            "branches": {},
            "reports": {
                "stock": "success",
                "orders": "success",
                "supplier_invoices": "success"
            }
        }
        
        # Track report-level status
        stock_failures = 0
        orders_failures = 0
        supplier_invoices_failures = 0
        
        for branch_info in branches:
            branch_name = branch_info.get("branch_name")
            company = branch_info.get("company")
            
            if not branch_name or not company:
                continue
            
            branch_status = {"status": "success", "reason": None}
            branch_failed = False
            
            # Check stock sanity
            stock_sane, stock_reason = self.check_stock_sanity(branch_name, company, refresh_started)
            if not stock_sane:
                branch_status["status"] = "failed"
                branch_status["reason"] = f"Stock: {stock_reason}"
                branch_failed = True
                stock_failures += 1
            
            # Check document sanity for orders
            # Purchase orders
            po_sane, po_reason = self.check_document_sanity(branch_name, company, "purchase_orders")
            # Branch orders
            bo_sane, bo_reason = self.check_document_sanity(branch_name, company, "branch_orders")
            
            # Orders are sane if at least one type has documents
            orders_sane = po_sane or bo_sane
            if not orders_sane:
                if not branch_failed:
                    branch_status["status"] = "failed"
                branch_status["reason"] = (branch_status.get("reason") or "") + f" Orders: {po_reason or bo_reason}"
                branch_failed = True
                orders_failures += 1
            
            # Check supplier invoices
            si_sane, si_reason = self.check_document_sanity(branch_name, company, "supplier_invoices")
            if not si_sane:
                if not branch_failed:
                    branch_status["status"] = "failed"
                branch_status["reason"] = (branch_status.get("reason") or "") + f" Supplier Invoices: {si_reason}"
                branch_failed = True
                supplier_invoices_failures += 1
            
            result["branches"][branch_name] = branch_status
        
        # Determine report-level status
        total_branches = len(branches)
        
        if stock_failures == 0:
            result["reports"]["stock"] = "success"
        elif stock_failures == total_branches:
            result["reports"]["stock"] = "failed"
        else:
            result["reports"]["stock"] = "partial"
        
        if orders_failures == 0:
            result["reports"]["orders"] = "success"
        elif orders_failures == total_branches:
            result["reports"]["orders"] = "failed"
        else:
            result["reports"]["orders"] = "partial"
        
        if supplier_invoices_failures == 0:
            result["reports"]["supplier_invoices"] = "success"
        elif supplier_invoices_failures == total_branches:
            result["reports"]["supplier_invoices"] = "failed"
        else:
            result["reports"]["supplier_invoices"] = "partial"
        
        return result

