"""
Database-Backed Orders Fetcher
Fetches Purchase Orders and Branch Orders from API and saves to SQLite database
Uses credentials from frontend via CredentialManager
"""
import os
import sys
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional

# Add app root to path
app_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, app_root)

from scripts.data_fetchers.database_base_fetcher import DatabaseBaseFetcher
from scripts.data_fetchers.branch_config import PURCHASE_ORDER_BRANCHES, BRANCH_ORDER_BRANCHES, BRANCH_MAPPING

# Configuration
START_YEAR = 2025
COMPANY_WORKERS = 2
BRANCH_WORKERS = 3
ORDER_WORKERS = 20


class DatabaseOrdersFetcher(DatabaseBaseFetcher):
    """
    Database-backed orders fetcher
    Fetches Purchase Orders and Branch Orders from API and saves to database
    """
    
    def __init__(self, app_root: str = None, db_manager=None, credential_manager=None):
        """
        Initialize database orders fetcher
        
        Args:
            app_root: Application root path
            db_manager: Database manager instance (optional)
            credential_manager: Credential manager instance (optional)
        """
        super().__init__("database_orders_fetcher", app_root)
        # Override db_manager if provided
        if db_manager:
            self.db_manager = db_manager
        # Override cred_manager if provided
        if credential_manager:
            self.cred_manager = credential_manager
        self.base_url = "https://corebasebackendnila.co.ke:5019"
        
    def extract_numeric_key(self, doc_number: str) -> int:
        """Extract numeric part from document number"""
        if not doc_number:
            return 0
        match = re.search(r'(\d+)$', str(doc_number))
        return int(match.group(1)) if match else 0

    def get_orders(self, session, token: str, order_type: str, branch_num: int, 
                   start_date, end_date) -> List[Dict]:
        """Get all orders for a date range"""
        if order_type == "purchase":
            params = {
                "bcode": branch_num,
                "search": "",
                "startDate": self.format_date_for_api(start_date),
                "endDate": self.format_date_for_api(end_date),
                "batched": "true"
            }
            url = f"{self.base_url}/api/PurchaseOrder/GetPurchaseOrders"
        else:  # branch order
            params = {
                "bcode": branch_num,
                "startDate": self.format_date_for_api(start_date),
                "endDate": self.format_date_for_api(end_date),
                "amount": "",
                "account": "",
                "reference": "",
                "batched": "true"
            }
            url = f"{self.base_url}/api/BranchOrders/GetOrderDocuments"
        
        headers = {"Authorization": f"Bearer {token}"}
        result = self.api_request(session, url, params=params, headers=headers)
        
        order_count = len(result) if result else 0
        self.logger.info(f"📥 Found {order_count} {order_type} orders for branch {branch_num}")
        
        return result or []

    def get_order_details(self, session, token: str, order_type: str, 
                         branch_num: int, order_number: str) -> List[Dict]:
        """Get order details for a specific order"""
        if order_type == "purchase":
            order_num = self.extract_numeric_key(order_number)
            params = {"bcode": branch_num, "purchaseOrderNum": order_num}
            url = f"{self.base_url}/api/PurchaseOrder/GetPurchaseOrdersDetails"
        else:  # branch order
            params = {"bcode": branch_num, "ordernum": order_number}
            url = f"{self.base_url}/api/BranchOrders/GetBranchOrder"
        
        headers = {"Authorization": f"Bearer {token}"}
        return self.api_request(session, url, params=params, headers=headers) or []

    def format_order_for_database(self, details: List[Dict], order_type: str, 
                                 branch_name: str, order_date, doc_number: str, 
                                 company: str) -> List[Dict]:
        """Format order details for database insertion"""
        formatted = []
        if not details:
            return formatted
            
        for item in details:
            try:
                if order_type == "purchase":
                    source_branch = branch_name
                    dest_branch = item.get("suppName", "")
                else:  # branch order
                    source_branch = BRANCH_MAPPING.get(item.get("hD2_SenderBranch", ""), "")
                    dest_branch = BRANCH_MAPPING.get(item.get("hD2_ReceiverBranch", ""), "")
                
                quantity = float(item.get("dT_Quantity", 0) or 0)
                unit_price = float(item.get("dT_Price", 0) or 0)
                total_price = float(item.get("dT_Total", 0) or 0)
                
                if order_type == "purchase":
                    formatted.append({
                        "company": company,
                        "branch": branch_name,
                        "document_number": doc_number,
                        "document_date": self.format_date_for_db(order_date),
                        "item_code": item.get("dT_ItemCode", ""),
                        "item_name": item.get("dT_ItemName", ""),
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "total_price": total_price,
                        "supplier_name": item.get("suppName", ""),
                        "reference": item.get("hD2_Reference", ""),
                        "comments": item.get("hD2_Comments", ""),
                        "done_by": item.get("hD2_Doneby", ""),
                        "source_branch": source_branch,
                        "destination_branch": dest_branch
                    })
                else:  # branch order
                    formatted.append({
                        "company": company,
                        "source_branch": source_branch,
                        "destination_branch": dest_branch,
                        "document_number": doc_number,
                        "document_date": self.format_date_for_db(order_date),
                        "item_code": item.get("dT_ItemCode", ""),
                        "item_name": item.get("dT_ItemName", ""),
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "total_price": total_price,
                        "reference": item.get("hD2_Reference", ""),
                        "comments": item.get("hD2_Comments", ""),
                        "done_by": item.get("hD2_Doneby", ""),
                        "status": item.get("hD2_Status", "")
                    })
            except Exception as e:
                self.logger.error(f"Error formatting order item: {e}")
                continue
        
        return formatted

    def process_single_order(self, args) -> Optional[Dict]:
        """Process a single order"""
        order_type, branch_info, session, token, order = args
        
        try:
            doc_num = str(order.get("docNumber", "")).strip()
            if not doc_num:
                return None
                
            order_date = self.safe_date_parse(order.get("docDate"))
            
            # Check if already processed
            if self.is_document_processed(
                branch_info["company"], order_type.upper(), doc_num, 
                self.format_date_for_db(order_date)
            ):
                return None
            
            # Get order details
            order_number = doc_num if order_type == "purchase" else order.get("bordeR_num")
            if not order_number:
                return None
                
            details = self.get_order_details(session, token, order_type, 
                                           branch_info["branch_num"], order_number)
            if not details:
                return None
            
            # Format for database
            formatted = self.format_order_for_database(
                details, order_type, branch_info["branch_name"], order_date, 
                doc_num, branch_info["company"]
            )
            
            if formatted:
                return {
                    'order_data': formatted,
                    'company': branch_info["company"],
                    'doc_num': doc_num,
                    'order_date': order_date,
                    'order_type': order_type
                }
        
        except Exception as e:
            self.logger.error(f"❌ Error processing {order_type} order: {e}")
        
        return None

    def process_branch_orders(self, order_type: str, branch_info: Dict, 
                             session, token: str) -> int:
        """Process all orders for a branch"""
        branch_code = branch_info["branchcode"]
        branch_name = branch_info["branch_name"]
        company = branch_info["company"]
        
        self.logger.info(f"🏢 Processing {branch_name} [{order_type.upper()}]")
        
        try:
            # Get date range (from start of 2025 to today - same as standalone scripts)
            start_date, end_date = self.get_full_year_date_range(START_YEAR)
            
            self.logger.info(f"📅 {branch_name}: Fetching {order_type} orders from {start_date} to {end_date} (full year {START_YEAR})")
            
            # Get all orders from API
            all_orders = self.get_orders(session, token, order_type, 
                                        branch_info["branch_num"], start_date, end_date)
            
            if not all_orders:
                self.logger.info(f"ℹ️ No {order_type} orders found for {branch_name}")
                return 0
            
            # Filter out already processed orders
            unprocessed_orders = []
            for order in all_orders:
                doc_num = str(order.get("docNumber", "")).strip()
                if not doc_num:
                    continue
                    
                order_date = self.safe_date_parse(order.get("docDate"))
                
                if not self.is_document_processed(
                    company, order_type.upper(), doc_num, 
                    self.format_date_for_db(order_date)
                ):
                    unprocessed_orders.append(order)
            
            total_orders = len(all_orders)
            unprocessed_count = len(unprocessed_orders)
            
            self.logger.info(f"📊 {branch_name}: {total_orders} total orders, {unprocessed_count} new orders to process")
            
            if unprocessed_count == 0:
                self.logger.info(f"🎯 {branch_name}: All {total_orders} orders already processed")
                return 0
            
            # Process unprocessed orders
            total_processed = 0
            args_list = [(order_type, branch_info, session, token, order) 
                        for order in unprocessed_orders]
            
            with ThreadPoolExecutor(max_workers=min(ORDER_WORKERS, len(unprocessed_orders))) as executor:
                future_to_order = {executor.submit(self.process_single_order, arg): arg 
                                 for arg in args_list}
                
                for future in as_completed(future_to_order):
                    try:
                        result = future.result(timeout=30)
                        if result:
                            # Save to database
                            if result['order_type'] == "purchase":
                                saved_count = self.db_manager.insert_purchase_orders(result['order_data'])
                            else:
                                saved_count = self.db_manager.insert_branch_orders(result['order_data'])
                            
                            if saved_count > 0:
                                # Mark as processed
                                self.mark_document_processed(
                                    result['company'], result['order_type'].upper(), 
                                    result['doc_num'], self.format_date_for_db(result['order_date'])
                                )
                                total_processed += 1
                                self.logger.info(f"💾 Saved order {result['doc_num']} ({saved_count} lines)")
                                
                    except Exception as e:
                        self.logger.error(f"❌ Order processing error: {e}")
            
            self.logger.info(f"✅ {branch_name}: {total_processed} new orders processed")
            return total_processed
            
        except Exception as e:
            self.logger.error(f"❌ Error processing {branch_name}: {e}")
            return 0

    def process_company(self, order_type: str, company: str) -> int:
        """Process all branches for a company"""
        self.logger.info(f"🏭 Processing {company} [{order_type.upper()}]")
        
        session = self.get_authenticated_session(company)
        if not session:
            self.logger.error(f"❌ Authentication failed for {company}")
            return 0
        
        # Get token for API calls
        token = self.cred_manager.get_valid_token(company)
        if not token:
            self.logger.error(f"❌ Could not get token for {company}")
            return 0
        
        # Select appropriate branches
        if order_type == "purchase":
            company_branches = [b for b in PURCHASE_ORDER_BRANCHES if b["company"] == company]
        else:
            company_branches = [b for b in BRANCH_ORDER_BRANCHES if b["company"] == company]
        
        if not company_branches:
            self.logger.info(f"ℹ️ No {order_type} branches found for {company}")
            return 0
        
        self.logger.info(f"🔧 Processing {len(company_branches)} branches for {company}")
        
        total_orders = 0
        
        # Process branches in parallel
        with ThreadPoolExecutor(max_workers=min(BRANCH_WORKERS, len(company_branches))) as executor:
            future_to_branch = {
                executor.submit(self.process_branch_orders, order_type, branch, session, token): branch 
                for branch in company_branches
            }
            
            for future in as_completed(future_to_branch):
                try:
                    count = future.result()
                    total_orders += count
                    self.logger.info(f"📈 {company} progress: {total_orders} orders so far")
                except Exception as e:
                    self.logger.error(f"❌ Branch processing error: {e}")
        
        self.logger.info(f"🏁 {company} {order_type.upper()}: {total_orders} total new orders")
        return total_orders

    def fetch_data(self, companies: list = None) -> int:
        """
        Unified system method - called by orchestrator
        Returns number of orders processed
        """
        try:
            if companies is None:
                companies = self.get_enabled_companies()
            
            if not companies:
                self.logger.warning("No enabled companies found")
                return 0
            
            # Clean up old records (>90 days) before fetching new ones
            self.logger.info("🧹 Cleaning old orders (>90 days)...")
            deleted_po = self.cleanup_old_records("purchase_orders", "document_date", retention_days=90)
            deleted_bo = self.cleanup_old_records("branch_orders", "document_date", retention_days=90)
            if deleted_po > 0 or deleted_bo > 0:
                self.logger.info(f"✅ Cleaned {deleted_po + deleted_bo:,} old order records")
            
            self.logger.info(f"🔄 Starting orders sync for companies: {companies}")
            total_orders = 0
            
            # Process purchase orders and branch orders for each company
            for company in companies:
                purchase_count = self.process_company("purchase", company)
                branch_count = self.process_company("branch", company)
                company_total = purchase_count + branch_count
                total_orders += company_total
                self.logger.info(f"✅ {company}: {purchase_count} purchase + {branch_count} branch = {company_total} orders")
            
            self.logger.info(f"✅ Orders sync completed: {total_orders} total orders")
            return total_orders
            
        except Exception as e:
            self.logger.error(f"❌ Orders sync error: {e}")
            return 0

    def run(self) -> Dict:
        """Main execution function"""
        self.log_script_start()
        
        if not self.validate_prerequisites():
            return {"success": False, "message": "No companies configured"}
        
        print("=" * 60)
        print("🚀 DATABASE-BACKED ORDER DOWNLOAD")
        print("=" * 60)
        print(f"📊 Purchase Branches: {len(PURCHASE_ORDER_BRANCHES)}")
        print(f"📊 Branch Branches: {len(BRANCH_ORDER_BRANCHES)}")
        print(f"📅 Data Range: {START_YEAR}-01-01 to Today")
        print(f"⚡ Parallel Workers: {ORDER_WORKERS}")
        print("=" * 60)
        
        total_purchase_orders = 0
        total_branch_orders = 0
        start_time = datetime.now()
        
        try:
            companies = self.get_enabled_companies()
            
            # Process purchase orders first, then branch orders
            tasks = []
            for company in companies:
                tasks.append(("purchase", company))
                tasks.append(("branch", company))
            
            with ThreadPoolExecutor(max_workers=COMPANY_WORKERS) as executor:
                future_to_task = {
                    executor.submit(self.process_company, task[0], task[1]): task 
                    for task in tasks
                }
                
                completed = 0
                for future in as_completed(future_to_task):
                    order_type, company = future_to_task[future]
                    try:
                        count = future.result()
                        if order_type == "purchase":
                            total_purchase_orders += count
                        else:
                            total_branch_orders += count
                        
                        completed += 1
                        progress_pct = (completed / len(tasks)) * 100
                        print(f"📈 Progress: {completed}/{len(tasks)} tasks ({progress_pct:.1f}%) - {company} {order_type}: {count} orders")
                        
                    except Exception as e:
                        self.logger.error(f"❌ Task error for {company} {order_type}: {e}")
                        completed += 1
            
            end_time = datetime.now()
            duration = end_time - start_time
            total_orders = total_purchase_orders + total_branch_orders
            
            print(f"\n🎉 DOWNLOAD COMPLETE!")
            print("=" * 60)
            print(f"📦 New Purchase Orders: {total_purchase_orders:,}")
            print(f"📦 New Branch Orders: {total_branch_orders:,}")
            print(f"📦 Total New Orders: {total_orders:,}")
            print(f"⏱️  Time taken: {duration}")
            if duration.total_seconds() > 0 and total_orders > 0:
                speed = total_orders / duration.total_seconds()
                print(f"📊 Processing speed: {speed:.1f} orders/second")
            print("=" * 60)
            
            self.logger.info(f"ORDER DOWNLOAD COMPLETED: {total_orders} new orders")
            
            return {
                "success": True, 
                "total_purchase_orders": total_purchase_orders,
                "total_branch_orders": total_branch_orders,
                "total_orders": total_orders,
                "duration": str(duration)
            }
            
        except Exception as e:
            self.logger.error(f"❌ Fatal error: {str(e)}")
            print(f"❌ Fatal error: {str(e)}")
            return {"success": False, "message": str(e)}


def main():
    """Main entry point"""
    fetcher = DatabaseOrdersFetcher()
    result = fetcher.run()
    
    if result.get("success"):
        print(f"\n✅ Successfully processed {result.get('total_orders', 0)} orders")
    else:
        print(f"\n❌ Failed: {result.get('message', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()

