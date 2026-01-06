"""
Database-Backed Stock Position Fetcher
Fetches current stock position from API and saves to SQLite database
Uses credentials from frontend via CredentialManager
"""
import os
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional

# Add app root to path
app_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, app_root)

from scripts.data_fetchers.database_base_fetcher import DatabaseBaseFetcher
from scripts.data_fetchers.branch_config import ALL_BRANCHES, get_branches_for_company

# Configuration
MAX_BRANCH_WORKERS = 15  # Increased for faster stock sync (most critical data)


class DatabaseStockFetcher(DatabaseBaseFetcher):
    """
    Database-backed stock position fetcher
    Fetches current stock from API and saves to database
    """
    
    def __init__(self, app_root: str = None, db_manager=None, credential_manager=None):
        """
        Initialize database stock fetcher
        
        Args:
            app_root: Application root path
            db_manager: Database manager instance (optional)
            credential_manager: Credential manager instance (optional)
        """
        super().__init__("database_stock_fetcher", app_root)
        # Override db_manager if provided
        if db_manager:
            self.db_manager = db_manager
        # Override cred_manager if provided
        if credential_manager:
            self.cred_manager = credential_manager
        self.base_url = "https://corebasebackendnila.co.ke:5019"
        
    def get_branch_stock(self, session, token: str, branch_num: int) -> List[Dict]:
        """Fetch stock data for a branch"""
        url = f"{self.base_url}/api/StockCentral/BranchStockPosition"
        params = {
            "bcode": branch_num,
            "invcode": "",
            "subgroupcode": "",
            "packagecode": "",
            "stockstatus": "",
            "numberOfItems": 10000,  # Get all items
            "moleculename": "",
            "moleculestrength": "",
            "groupcode": "",
            "manufacturercode": ""
        }
        
        headers = {"Authorization": f"Bearer {token}"}
        result = self.api_request(session, url, params=params, headers=headers)
        
        stock_count = len(result) if result else 0
        self.logger.info(f"📥 Found {stock_count} stock items for branch {branch_num}")
        
        return result or []

    def format_stock_for_database(self, stock_items: List[Dict], branch_name: str, 
                                  company: str) -> List[Dict]:
        """Format stock data for database insertion"""
        formatted = []
        
        # Ensure company is uppercase and trimmed for consistency
        company = (company or "").upper().strip()
        if not company:
            self.logger.error(f"⚠️ Company is empty for branch {branch_name} - cannot format stock data")
            return []
        
        for item in stock_items:
            try:
                # Calculate stock value
                pack_size = item.get("pacK_QTY", 1) or 1
                unit_price = item.get("unitPrice", 0.0) or 0.0
                quantity = float(item.get("calcQty", 0) or 0)
                stock_value = unit_price * quantity
                
                formatted.append({
                    "branch": branch_name.strip() if branch_name else "",
                    "item_code": item.get("inV_CODE", ""),
                    "item_name": item.get("description", ""),
                    "stock_string": item.get("calcpw", "0W0P"),
                    "stock_pieces": int(quantity),
                    "company": company,  # Always uppercase and trimmed
                    "pack_size": pack_size,
                    "unit_price": unit_price,
                    "stock_value": stock_value,
                    "source_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            except Exception as e:
                self.logger.error(f"Error formatting stock item: {e}")
                continue
        
        return formatted

    def process_branch_stock(self, branch_info: Dict, token: str) -> List[Dict]:
        """Process stock data for a single branch"""
        branch_code = branch_info["branchcode"]
        branch_name = branch_info["branch_name"]
        company = branch_info["company"]
        branch_num = branch_info["branch_num"]
        
        try:
            # Get session for this company
            session = self.get_authenticated_session(company)
            if not session:
                self.logger.error(f"❌ Could not get session for {company}")
                return []
            
            # Get stock data from API
            stock_items = self.get_branch_stock(session, token, branch_num)
            
            if not stock_items:
                self.logger.info(f"No stock items found for {branch_name}")
                return []
            
            # Format stock data
            formatted_stock = self.format_stock_for_database(stock_items, branch_name, company)
            
            self.logger.info(f"✅ Processed {len(formatted_stock)} items for {branch_name}")
            return formatted_stock
            
        except Exception as e:
            self.logger.error(f"Error processing stock for {branch_name}: {str(e)}")
            return []

    def process_company_stock(self, company: str, refresh_started: Optional[str] = None) -> Dict:
        """
        Process stock data for all branches of a company
        
        Returns:
            Dict with structure:
            {
                "total_updated": int,
                "branches": {
                    "BranchName": {
                        "status": "success" | "failed",
                        "records": int,
                        "reason": "..." (if failed)
                    }
                }
            }
        """
        self.logger.info(f"Processing stock for {company} company")
        
        result = {
            "total_updated": 0,
            "branches": {}
        }
        
        # Get authentication token
        token = self.cred_manager.get_valid_token(company)
        if not token:
            self.logger.error(f"Failed to authenticate for {company}")
            return result
        
        # Get branches for this company
        company_branches = [b for b in ALL_BRANCHES if b["company"] == company]
        
        if not company_branches:
            self.logger.info(f"No branches found for {company}")
            return result
        
        # Process branches in parallel and collect branch-level data
        branch_stock_data = {}  # {branch_name: [stock_data]}
        
        with ThreadPoolExecutor(max_workers=MAX_BRANCH_WORKERS) as executor:
            futures = {
                executor.submit(self.process_branch_stock, branch, token): branch
                for branch in company_branches
            }
            
            for future in as_completed(futures):
                branch = futures[future]
                branch_name = branch['branch_name']
                try:
                    stock_data = future.result()
                    if stock_data:
                        branch_stock_data[branch_name] = stock_data
                        result["branches"][branch_name] = {
                            "status": "success",
                            "records": len(stock_data),
                            "reason": None
                        }
                        self.logger.info(f"Processed {len(stock_data)} items for {branch_name}")
                    else:
                        result["branches"][branch_name] = {
                            "status": "failed",
                            "records": 0,
                            "reason": "No stock data returned from API"
                        }
                        self.logger.warning(f"⚠️ No stock data for {branch_name}")
                except Exception as e:
                    result["branches"][branch_name] = {
                        "status": "failed",
                        "records": 0,
                        "reason": f"Error processing branch: {str(e)}"
                    }
                    self.logger.error(f"Error processing branch {branch_name}: {str(e)}")
        
        # Collect all stock data for insertion
        all_stock_data = []
        for branch_name, stock_data in branch_stock_data.items():
            all_stock_data.extend(stock_data)
        
        # Save to database - use UPSERT to atomically update existing records
        # This ensures we always have the latest version without risking empty table
        if all_stock_data:
            # Use replace_all=False to trigger UPSERT mode
            # UPSERT will atomically update existing records or insert new ones
            # After successful insert, cleanup will remove any remaining old versions
            updated = self.db_manager.insert_current_stock(all_stock_data, replace_all=False)
            result["total_updated"] = updated
            self.logger.info(f"✅ Inserted/updated {updated} stock records for {company} (using UPSERT - always retains latest version)")
        
        return result

    def fetch_data(self, companies: list = None, refresh_started: Optional[str] = None) -> Dict:
        """
        Unified system method - called by orchestrator
        Returns branch-level results for sanity checking
        
        Args:
            companies: List of companies to process
            refresh_started: ISO timestamp when refresh started (for sanity checks)
        
        Returns:
            Dict with structure:
            {
                "success": bool,
                "total_updated": int,
                "branches": {
                    "BranchName": {
                        "status": "success" | "failed",
                        "records": int,
                        "reason": "..." (if failed)
                    }
                }
            }
        """
        try:
            if companies is None:
                companies = self.get_enabled_companies()
            
            if not companies:
                self.logger.warning("No enabled companies found")
                return {
                    "success": False,
                    "total_updated": 0,
                    "branches": {},
                    "message": "No enabled companies found"
                }
            
            self.logger.info(f"🔄 Starting stock sync for companies: {companies}")
            if refresh_started:
                self.logger.info(f"📅 Refresh started at: {refresh_started}")
            
            result = {
                "success": True,
                "total_updated": 0,
                "branches": {}
            }
            
            # Process companies in parallel for faster execution
            # Each company processes its branches in parallel, and companies can run in parallel too
            if len(companies) > 1:
                self.logger.info(f"⚡ Processing {len(companies)} companies in parallel...")
                with ThreadPoolExecutor(max_workers=min(len(companies), 2)) as executor:  # Max 2 companies in parallel to avoid overwhelming Supabase
                    futures = {
                        executor.submit(self.process_company_stock, company, refresh_started): company
                        for company in companies
                    }
                    
                    for future in as_completed(futures):
                        company = futures[future]
                        try:
                            company_result = future.result()
                            result["total_updated"] += company_result.get("total_updated", 0)
                            # Merge branch results
                            result["branches"].update(company_result.get("branches", {}))
                            self.logger.info(f"✅ {company}: {company_result.get('total_updated', 0)} stock records inserted")
                        except Exception as e:
                            self.logger.error(f"❌ Error processing {company}: {str(e)}")
                            result["success"] = False
            else:
                # Single company - process normally
                for company in companies:
                    company_result = self.process_company_stock(company, refresh_started)
                    result["total_updated"] += company_result.get("total_updated", 0)
                    result["branches"].update(company_result.get("branches", {}))
                    self.logger.info(f"✅ {company}: {company_result.get('total_updated', 0)} stock records inserted")
            
            self.logger.info(f"✅ Stock sync completed: {result['total_updated']} total records across {len(result['branches'])} branches")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Stock sync error: {e}")
            return {
                "success": False,
                "total_updated": 0,
                "branches": {},
                "message": str(e)
            }

    def run(self) -> Dict:
        """Main execution function (standalone mode)"""
        self.log_script_start()
        
        if not self.validate_prerequisites():
            return {"success": False, "message": "No companies configured"}
        
        print("=" * 60)
        print("🚀 DATABASE-BACKED STOCK SYNCHRONIZATION")
        print("=" * 60)
        print(f"📊 Total Branches: {len(ALL_BRANCHES)}")
        print(f"⚡ Max Branch Workers: {MAX_BRANCH_WORKERS}")
        print("=" * 60)
        
        start_time = datetime.now()
        result = self.fetch_data()
        execution_time = datetime.now() - start_time
        
        # Handle both old (int) and new (Dict) return types for backward compatibility
        if isinstance(result, dict):
            total_updated = result.get("total_updated", 0)
            success = result.get("success", True)
        else:
            # Legacy: result is int
            total_updated = result
            success = True
        
        print(f"\n🎉 STOCK SYNCHRONIZATION COMPLETE!")
        print("=" * 60)
        print(f"📦 Total Records Updated: {total_updated:,}")
        print(f"⏱️  Time taken: {execution_time}")
        print("=" * 60)
        
        if isinstance(result, dict):
            return {
                "success": success,
                "total_updated": total_updated,
                "duration": str(execution_time),
                "branches": result.get("branches", {})
            }
        else:
            return {"success": True, "total_updated": total_updated, "duration": str(execution_time)}


def main():
    """Main entry point"""
    fetcher = DatabaseStockFetcher()
    result = fetcher.run()
    
    if result.get("success"):
        print(f"\n✅ Successfully updated {result.get('total_updated', 0)} stock records")
    else:
        print(f"\n❌ Failed: {result.get('message', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()

