"""
Database-Backed GRN (Goods Received Notes) Fetcher
Fetches GRN data from API and saves to SQLite database
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
from scripts.data_fetchers.branch_config import GRN_BRANCHES, get_branches_for_company

# Configuration
START_YEAR = 2025
COMPANY_WORKERS = 2
BRANCH_WORKERS = 3
GRN_WORKERS = 20


class DatabaseGRNFetcher(DatabaseBaseFetcher):
    """
    Database-backed GRN fetcher
    Fetches Goods Received Notes from API and saves to database
    """
    
    def __init__(self, app_root: str = None, db_manager=None, credential_manager=None):
        """
        Initialize database GRN fetcher
        
        Args:
            app_root: Application root path
            db_manager: Database manager instance (optional)
            credential_manager: Credential manager instance (optional)
        """
        super().__init__("database_grn_fetcher", app_root)
        # Override db_manager if provided
        if db_manager:
            self.db_manager = db_manager
        # Override cred_manager if provided
        if credential_manager:
            self.cred_manager = credential_manager
        self.base_url = "https://corebasebackendnila.co.ke:5019"
        
    def get_grns(self, session, token: str, branch_num: int, start_date, end_date) -> List[Dict]:
        """Get all GRNs for a date range"""
        params = {
            "bcode": branch_num,
            "startDate": self.format_date_for_api(start_date),
            "endDate": self.format_date_for_api(end_date),
            "search": "",
            "batched": "true"
        }
        url = f"{self.base_url}/api/GoodsReceived/GetGRNs"
        headers = {"Authorization": f"Bearer {token}"}
        
        result = self.api_request(session, url, params=params, headers=headers)
        grn_count = len(result) if result else 0
        self.logger.info(f"📥 Found {grn_count} GRNs for branch {branch_num}")
        
        return result or []

    def get_grn_details(self, session, token: str, branch_num: int, grn_number: str) -> List[Dict]:
        """Get GRN details for a specific GRN"""
        params = {"bcode": branch_num, "grnnum": grn_number}
        url = f"{self.base_url}/api/GoodsReceived/GetGRNDetails"
        headers = {"Authorization": f"Bearer {token}"}
        
        return self.api_request(session, url, params=params, headers=headers) or []

    def convert_quantity(self, value) -> float:
        """Convert quantity values with commas to float"""
        if value is None:
            return 0.0
        try:
            if isinstance(value, str):
                value = ''.join(c for c in value if c.isdigit() or c in '-,.')
                if '-' in value:
                    return -float(value.replace('-', '').replace(',', ''))
                return float(value.replace(',', ''))
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def format_grn_for_database(self, details: List[Dict], branch_name: str, 
                                grn_date, doc_number: str, grn_data: Dict, company: str) -> List[Dict]:
        """Format GRN details for database insertion"""
        formatted = []
        if not details:
            return formatted
            
        for item in details:
            try:
                quantity = self.convert_quantity(item.get("dT_Quantity", 0))
                
                formatted.append({
                    "company": company,
                    "branch": branch_name,
                    "document_number": doc_number,
                    "document_date": self.format_date_for_db(grn_date),
                    "item_code": item.get("dT_ItemCode", ""),
                    "item_name": item.get("dT_ItemName", ""),
                    "quantity": quantity,
                    "destination": grn_data.get("suppName", ""),
                    "comments": grn_data.get("comments", "")
                })
            except Exception as e:
                self.logger.error(f"Error formatting GRN item: {e}")
                continue
        
        return formatted

    def process_single_grn(self, args) -> Optional[Dict]:
        """Process a single GRN"""
        branch_info, session, token, grn = args
        
        try:
            doc_num = str(grn.get("grnNumber", "")).strip()
            if not doc_num:
                return None
                
            grn_date = self.safe_date_parse(grn.get("grnDate"))
            
            # Check if already processed
            if self.is_document_processed(
                branch_info["company"], "GRN", doc_num, self.format_date_for_db(grn_date)
            ):
                return None
            
            # Get GRN details
            details = self.get_grn_details(session, token, branch_info["branch_num"], doc_num)
            if not details:
                return None
            
            # Format for database
            formatted = self.format_grn_for_database(
                details, branch_info["branch_name"], grn_date, doc_num, grn, branch_info["company"]
            )
            
            if formatted:
                return {
                    'grn_data': formatted,
                    'company': branch_info["company"],
                    'doc_num': doc_num,
                    'grn_date': grn_date
                }
        
        except Exception as e:
            self.logger.error(f"❌ Error processing GRN: {e}")
        
        return None

    def process_branch_grns(self, branch_info: Dict, session, token: str) -> int:
        """Process all GRNs for a branch"""
        branch_code = branch_info["branchcode"]
        branch_name = branch_info["branch_name"]
        company = branch_info["company"]
        
        self.logger.info(f"🏢 Processing {branch_name} [GRN]")
        
        try:
            # Get date range
            today = datetime.now().date()
            year_start = datetime(START_YEAR, 1, 1).date()
            
            self.logger.info(f"📅 {branch_name}: Checking {year_start} to {today}")
            
            # Get all GRNs from API
            all_grns = self.get_grns(session, token, branch_info["branch_num"], year_start, today)
            
            if not all_grns:
                self.logger.info(f"ℹ️ No GRNs found for {branch_name}")
                return 0
            
            # Filter out already processed GRNs
            unprocessed_grns = []
            for grn in all_grns:
                doc_num = str(grn.get("grnNumber", "")).strip()
                if not doc_num:
                    continue
                    
                grn_date = self.safe_date_parse(grn.get("grnDate"))
                
                if not self.is_document_processed(
                    company, "GRN", doc_num, self.format_date_for_db(grn_date)
                ):
                    unprocessed_grns.append(grn)
            
            total_grns = len(all_grns)
            unprocessed_count = len(unprocessed_grns)
            
            self.logger.info(f"📊 {branch_name}: {total_grns} total GRNs, {unprocessed_count} new GRNs to process")
            
            if unprocessed_count == 0:
                self.logger.info(f"🎯 {branch_name}: All {total_grns} GRNs already processed")
                return 0
            
            # Process unprocessed GRNs
            total_processed = 0
            total_items = 0
            args_list = [(branch_info, session, token, grn) for grn in unprocessed_grns]
            
            with ThreadPoolExecutor(max_workers=min(GRN_WORKERS, len(unprocessed_grns))) as executor:
                future_to_grn = {executor.submit(self.process_single_grn, arg): arg for arg in args_list}
                
                for future in as_completed(future_to_grn):
                    try:
                        result = future.result(timeout=30)
                        if result:
                            # Save to database
                            saved_count = self.db_manager.insert_goods_received_notes(result['grn_data'])
                            
                            if saved_count > 0:
                                # Mark as processed
                                self.mark_document_processed(
                                    result['company'], "GRN", result['doc_num'], 
                                    self.format_date_for_db(result['grn_date'])
                                )
                                total_processed += 1
                                total_items += saved_count
                                self.logger.info(f"💾 Saved GRN {result['doc_num']} ({saved_count} items)")
                                
                    except Exception as e:
                        self.logger.error(f"❌ GRN processing error: {e}")
            
            self.logger.info(f"✅ {branch_name}: {total_processed} new GRNs processed ({total_items} total items)")
            return total_processed
            
        except Exception as e:
            self.logger.error(f"❌ Error processing {branch_name}: {e}")
            return 0

    def process_company(self, company: str) -> int:
        """Process all branches for a company"""
        self.logger.info(f"🏭 Processing {company} [GRN]")
        
        session = self.get_authenticated_session(company)
        if not session:
            self.logger.error(f"❌ Authentication failed for {company}")
            return 0
        
        # Get token for API calls
        token = self.cred_manager.get_valid_token(company)
        if not token:
            self.logger.error(f"❌ Could not get token for {company}")
            return 0
        
        # Get branches for this company
        company_branches = [b for b in GRN_BRANCHES if b["company"] == company]
        
        if not company_branches:
            self.logger.info(f"ℹ️ No GRN branches found for {company}")
            return 0
        
        self.logger.info(f"🔧 Processing {len(company_branches)} branches for {company}")
        
        total_grns = 0
        
        # Process branches in parallel
        with ThreadPoolExecutor(max_workers=min(BRANCH_WORKERS, len(company_branches))) as executor:
            future_to_branch = {
                executor.submit(self.process_branch_grns, branch, session, token): branch 
                for branch in company_branches
            }
            
            for future in as_completed(future_to_branch):
                try:
                    count = future.result()
                    total_grns += count
                    self.logger.info(f"📈 {company} progress: {total_grns} GRNs so far")
                except Exception as e:
                    self.logger.error(f"❌ Branch processing error: {e}")
        
        self.logger.info(f"🏁 {company} GRN: {total_grns} total new GRNs")
        return total_grns

    def fetch_data(self, companies: list = None) -> int:
        """
        Unified system method - called by orchestrator
        Returns number of GRNs processed
        """
        try:
            if companies is None:
                companies = self.get_enabled_companies()
            
            if not companies:
                self.logger.warning("No enabled companies found")
                return 0
            
            self.logger.info(f"🔄 Starting GRN sync for companies: {companies}")
            total_grns = 0
            
            for company in companies:
                count = self.process_company(company)
                total_grns += count
                self.logger.info(f"✅ {company}: {count} GRNs processed")
            
            self.logger.info(f"✅ GRN sync completed: {total_grns} total GRNs")
            return total_grns
            
        except Exception as e:
            self.logger.error(f"❌ GRN sync error: {e}")
            return 0

    def run(self) -> Dict:
        """Main execution function"""
        self.log_script_start()
        
        if not self.validate_prerequisites():
            return {"success": False, "message": "No companies configured"}
        
        print("=" * 60)
        print("🚀 DATABASE-BACKED GRN DOWNLOAD")
        print("=" * 60)
        print(f"📊 GRN Branches: {len(GRN_BRANCHES)}")
        print(f"📅 Data Range: {START_YEAR}-01-01 to Today")
        print(f"⚡ Parallel Workers: {GRN_WORKERS}")
        print("=" * 60)
        
        total_grns = 0
        start_time = datetime.now()
        
        try:
            companies = self.get_enabled_companies()
            
            # Process GRNs for all companies
            with ThreadPoolExecutor(max_workers=COMPANY_WORKERS) as executor:
                future_to_company = {
                    executor.submit(self.process_company, company): company 
                    for company in companies
                }
                
                completed = 0
                for future in as_completed(future_to_company):
                    company = future_to_company[future]
                    try:
                        count = future.result()
                        total_grns += count
                        
                        completed += 1
                        progress_pct = (completed / len(companies)) * 100
                        print(f"📈 Progress: {completed}/{len(companies)} companies ({progress_pct:.1f}%) - {company}: {count} GRNs")
                        
                    except Exception as e:
                        self.logger.error(f"❌ Company error for {company}: {e}")
                        completed += 1
            
            end_time = datetime.now()
            duration = end_time - start_time
            
            print(f"\n🎉 GRN DOWNLOAD COMPLETE!")
            print("=" * 60)
            print(f"📦 New GRNs Processed: {total_grns:,}")
            print(f"⏱️  Time taken: {duration}")
            if duration.total_seconds() > 0 and total_grns > 0:
                speed = total_grns / duration.total_seconds()
                print(f"📊 Processing speed: {speed:.1f} GRNs/second")
            print("=" * 60)
            
            self.logger.info(f"GRN DOWNLOAD COMPLETED: {total_grns} new GRNs")
            
            return {"success": True, "total_grns": total_grns, "duration": str(duration)}
            
        except Exception as e:
            self.logger.error(f"❌ Fatal error: {str(e)}")
            print(f"❌ Fatal error: {str(e)}")
            return {"success": False, "message": str(e)}


def main():
    """Main entry point"""
    fetcher = DatabaseGRNFetcher()
    result = fetcher.run()
    
    if result.get("success"):
        print(f"\n✅ Successfully processed {result.get('total_grns', 0)} GRNs")
    else:
        print(f"\n❌ Failed: {result.get('message', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()

