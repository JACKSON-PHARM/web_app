"""
Database-Backed Supplier Invoices Fetcher
Fetches Supplier Invoices from API and saves to SQLite database
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
from scripts.data_fetchers.branch_config import SUPPLIER_INVOICE_BRANCHES

# Configuration
START_YEAR = 2025
COMPANY_WORKERS = 2
BRANCH_WORKERS = 3
INVOICE_WORKERS = 20


class DatabaseSupplierInvoicesFetcher(DatabaseBaseFetcher):
    """
    Database-backed supplier invoices fetcher
    Fetches Supplier Invoices from API and saves to database
    """
    
    def __init__(self, app_root: str = None, db_manager=None, credential_manager=None):
        """
        Initialize database supplier invoices fetcher
        
        Args:
            app_root: Application root path
            db_manager: Database manager instance (optional)
            credential_manager: Credential manager instance (optional)
        """
        super().__init__("database_supplier_invoices_fetcher", app_root)
        # Override db_manager if provided
        if db_manager:
            self.db_manager = db_manager
        # Override cred_manager if provided
        if credential_manager:
            self.cred_manager = credential_manager
        self.base_url = "https://corebasebackendnila.co.ke:5019"
        
    def extract_invoice_number(self, full_doc_number: str) -> str:
        """Extract numeric part from document number"""
        if not full_doc_number:
            return "0"
        match = re.search(r'(\d+)$', str(full_doc_number))
        return match.group(1) if match else str(full_doc_number)

    def get_supplier_invoices(self, session, token: str, branch_num: int, 
                              start_date, end_date) -> List[Dict]:
        """Get supplier invoices for date range"""
        params = {
            "bcode": branch_num,
            "batched": "",
            "account": "",
            "startDate": self.format_date_for_api(start_date),
            "endDate": self.format_date_for_api(end_date),
            "reference": "",
            "amount": ""
        }
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Log the request details for debugging
        self.logger.debug(f"Requesting supplier invoices: branch_num={branch_num}, startDate={params['startDate']}, endDate={params['endDate']}")
        
        result = self.api_request(
            session, 
            f"{self.base_url}/api/SupplierInvoice/GetSupplierInvoices",
            params=params,
            headers=headers
        )
        
        # Handle different response types
        if result is None:
            self.logger.warning(f"API returned None for branch {branch_num} - this might indicate an error")
            return []
        
        if isinstance(result, list):
            invoice_count = len(result)
        elif isinstance(result, dict):
            # Some APIs wrap the list in a dict
            if 'data' in result:
                invoice_count = len(result['data']) if isinstance(result['data'], list) else 0
                result = result['data']
            else:
                invoice_count = 1 if result else 0
                result = [result] if result else []
        else:
            invoice_count = 0
            result = []
        
        self.logger.info(f"📥 Found {invoice_count} supplier invoices for branch {branch_num}")
        
        return result if isinstance(result, list) else []

    def get_supplier_invoice_details(self, session, token: str, branch_num: int, 
                                     invoice_num: int) -> List[Dict]:
        """Get supplier invoice details"""
        params = {
            "bcode": branch_num,
            "suppInvNum": invoice_num
        }
        
        headers = {"Authorization": f"Bearer {token}"}
        
        result = self.api_request(
            session,
            f"{self.base_url}/api/SupplierInvoice/GetsupplierInvoiceDetails",
            params=params,
            headers=headers
        )
        
        return result or []

    def format_supplier_invoice_for_database(self, details: List[Dict], branch_name: str, 
                                           invoice_date, doc_number: str, 
                                           company: str) -> List[Dict]:
        """Format supplier invoice details for database insertion"""
        formatted = []
        if not details:
            return formatted
            
        for item in details:
            try:
                quantity = float(item.get("dT_Quantity", 0) or 0)
                unit_price = float(item.get("dT_Price", 0) or 0)
                total_amount = float(item.get("dT_Total", 0) or 0)
                vat_amount = float(item.get("dT_Vatt", 0) or 0)
                net_amount = float(item.get("dT_Nett", 0) or 0)
                
                formatted.append({
                    "company": company,
                    "branch": branch_name,
                    "document_number": doc_number,
                    "document_date": self.format_date_for_db(invoice_date) if invoice_date else None,
                    "item_code": item.get("dT_ItemCode", ""),
                    "item_name": item.get("dT_ItemName", ""),
                    "units": quantity,
                    "unit_price": unit_price,
                    "total_amount": total_amount,
                    "supplier_id": item.get("hD2_SUPPLIERID", ""),
                    "supplier_name": item.get("hD2_SUPPLIERNAME", ""),
                    "reference": item.get("hD2_Reference", ""),
                    "done_by": item.get("hD2_Doneby", ""),
                    "document_status": item.get("hD2_Docstatus", ""),
                    "sales_code": item.get("hD3_SalesCodeName", ""),
                    "vat_code": item.get("dT_Vat", ""),
                    "vat_amount": vat_amount,
                    "net_amount": net_amount
                })
            except (ValueError, TypeError) as e:
                self.logger.warning(f"⚠️ Error formatting item for {doc_number}: {e}")
                continue
        
        return formatted

    def process_single_supplier_invoice(self, args) -> Optional[Dict]:
        """Process single supplier invoice"""
        branch_info, session, token, invoice = args
        
        try:
            doc_num = str(invoice.get("docNumber", "")).strip()
            if not doc_num:
                return None
                
            invoice_date = self.safe_date_parse(invoice.get("docDate"))
            
            # Check if already processed
            if self.is_document_processed(
                branch_info["company"], "SUPPLIER_INVOICE", doc_num, 
                self.format_date_for_db(invoice_date)
            ):
                return None
            
            # Extract invoice number from document number (like standalone script)
            invoice_num_str = self.extract_invoice_number(doc_num)
            
            # Try to convert to int, fallback to docID if needed
            try:
                invoice_num = int(invoice_num_str) if invoice_num_str and invoice_num_str != "0" else None
            except (ValueError, TypeError):
                invoice_num = None
            
            if not invoice_num:
                # Try using docID as fallback
                doc_id = invoice.get("docID")
                if doc_id:
                    try:
                        invoice_num = int(doc_id)
                    except (ValueError, TypeError):
                        self.logger.warning(f"Could not extract invoice number from {doc_num} or docID {doc_id}")
                        return None
                else:
                    self.logger.warning(f"Could not extract invoice number from {doc_num}")
                    return None
            
            # Get invoice details using invoice number
            details = self.get_supplier_invoice_details(session, token, 
                                                       branch_info["branch_num"], invoice_num)
            
            if details:
                formatted = self.format_supplier_invoice_for_database(
                    details, branch_info["branch_name"], invoice_date, doc_num, 
                    branch_info["company"]
                )
                if formatted:
                    return {
                        'invoice_data': formatted,
                        'company': branch_info["company"],
                        'doc_num': doc_num,
                        'invoice_date': invoice_date
                    }
        
        except Exception as e:
            self.logger.error(f"❌ Error processing invoice {doc_num}: {e}")
        
        return None

    def process_branch_supplier_invoices(self, branch_info: Dict, session, token: str) -> int:
        """Process all supplier invoices for a branch"""
        branch_code = branch_info["branchcode"]
        branch_name = branch_info["branch_name"]
        company = branch_info["company"]
        branch_num = branch_info["branch_num"]
        
        self.logger.info(f"🏢 Processing {branch_name} ({branch_code}, branch_num={branch_num}) [SUPPLIER INVOICES]")
        
        try:
            # Get date range (last 30 days for Supabase free tier)
            start_date, end_date = self.get_retention_date_range(30)
            
            self.logger.info(f"📅 {branch_name} (branch_num={branch_num}): Fetching supplier invoices from {start_date} to {end_date} (last 30 days)")
            
            # Get all supplier invoices from API
            self.logger.info(f"🔍 Fetching supplier invoices for {branch_name} (branch_num={branch_num}) from {start_date} to {end_date}")
            all_invoices = self.get_supplier_invoices(session, token, branch_num, start_date, end_date)
            
            if not all_invoices:
                self.logger.warning(f"⚠️ No supplier invoices returned from API for {branch_name} (branch_num={branch_num}). This could mean:")
                self.logger.warning(f"   1. No invoices exist for this branch in the date range")
                self.logger.warning(f"   2. API returned an error (check logs above)")
                self.logger.warning(f"   3. Authentication token might be invalid")
                return 0
            
            self.logger.info(f"📥 Retrieved {len(all_invoices)} invoices from API for {branch_name} (branch_num={branch_num})")
            
            # Log sample invoice if available
            if len(all_invoices) > 0:
                sample = all_invoices[0]
                self.logger.debug(f"Sample invoice: docNumber={sample.get('docNumber')}, docDate={sample.get('docDate')}")
            
            # Filter out already processed invoices
            unprocessed_invoices = []
            for invoice in all_invoices:
                doc_num = str(invoice.get("docNumber", "")).strip()
                if not doc_num:
                    continue
                    
                invoice_date = self.safe_date_parse(invoice.get("docDate"))
                
                if not self.is_document_processed(
                    company, "SUPPLIER_INVOICE", doc_num, 
                    self.format_date_for_db(invoice_date)
                ):
                    unprocessed_invoices.append(invoice)
            
            total_invoices = len(all_invoices)
            unprocessed_count = len(unprocessed_invoices)
            
            self.logger.info(f"📊 {branch_name}: {total_invoices} total invoices, {unprocessed_count} new invoices to process")
            
            if unprocessed_count == 0:
                self.logger.info(f"🎯 {branch_name}: All {total_invoices} invoices already processed")
                return 0
            
            # Process only unprocessed invoices
            total_processed = 0
            args_list = [(branch_info, session, token, invoice) 
                        for invoice in unprocessed_invoices]
            
            with ThreadPoolExecutor(max_workers=min(INVOICE_WORKERS, len(unprocessed_invoices))) as executor:
                future_to_invoice = {
                    executor.submit(self.process_single_supplier_invoice, arg): arg 
                    for arg in args_list
                }
                
                for future in as_completed(future_to_invoice):
                    try:
                        result = future.result(timeout=30)
                        if result:
                            # Save to database
                            saved_count = self.db_manager.insert_supplier_invoices(result['invoice_data'])
                            
                            if saved_count > 0:
                                # Mark as processed
                                self.mark_document_processed(
                                    result['company'], "SUPPLIER_INVOICE", 
                                    result['doc_num'], 
                                    self.format_date_for_db(result['invoice_date'])
                                )
                                total_processed += 1
                                self.logger.info(f"💾 Saved supplier invoice {result['doc_num']} ({saved_count} lines)")
                                
                    except Exception as e:
                        self.logger.error(f"❌ Invoice processing error: {e}")
            
            self.logger.info(f"✅ {branch_name}: {total_processed} new invoices processed")
            return total_processed
            
        except Exception as e:
            self.logger.error(f"❌ Error processing {branch_name}: {e}")
            return 0

    def process_company_supplier_invoices(self, company: str) -> int:
        """Process all branches for a company"""
        self.logger.info(f"🏭 Processing {company} [SUPPLIER INVOICES]")
        
        session = self.get_authenticated_session(company)
        if not session:
            self.logger.error(f"❌ Authentication failed for {company}")
            return 0
        
        # Get token for API calls
        token = self.cred_manager.get_valid_token(company)
        if not token:
            self.logger.error(f"❌ Could not get token for {company}")
            return 0
        
        company_branches = [b for b in SUPPLIER_INVOICE_BRANCHES if b["company"] == company]
        
        if not company_branches:
            self.logger.info(f"ℹ️ No supplier branches found for {company}")
            return 0
        
        self.logger.info(f"🔧 Processing {len(company_branches)} branches for {company}")
        
        total_invoices = 0
        
        # Process branches in parallel
        with ThreadPoolExecutor(max_workers=min(BRANCH_WORKERS, len(company_branches))) as executor:
            future_to_branch = {
                executor.submit(self.process_branch_supplier_invoices, branch, session, token): branch 
                for branch in company_branches
            }
            
            for future in as_completed(future_to_branch):
                try:
                    count = future.result()
                    total_invoices += count
                    self.logger.info(f"📈 {company} progress: {total_invoices} invoices so far")
                except Exception as e:
                    self.logger.error(f"❌ Branch processing error: {e}")
        
        self.logger.info(f"🏁 {company} SUPPLIER INVOICES: {total_invoices} total new invoices")
        return total_invoices

    def fetch_data(self, companies: list = None) -> int:
        """
        Unified system method - called by orchestrator
        Returns number of supplier invoices processed
        """
        try:
            if companies is None:
                companies = self.get_enabled_companies()
            
            if not companies:
                self.logger.warning("No enabled companies found")
                return 0
            
            self.logger.info(f"🔄 Starting supplier invoices sync for companies: {companies}")
            total_invoices = 0
            
            for company in companies:
                count = self.process_company_supplier_invoices(company)
                total_invoices += count
                self.logger.info(f"✅ {company}: {count} supplier invoices processed")
            
            self.logger.info(f"✅ Supplier invoices sync completed: {total_invoices} total invoices")
            return total_invoices
            
        except Exception as e:
            self.logger.error(f"❌ Supplier invoices sync error: {e}")
            return 0

    def run(self) -> Dict:
        """Main execution function"""
        self.log_script_start()
        
        if not self.validate_prerequisites():
            return {"success": False, "message": "No companies configured"}
        
        print("=" * 70)
        print("🚀 DATABASE-BACKED SUPPLIER INVOICE DOWNLOAD")
        print("=" * 70)
        print(f"📊 Supplier Invoice Branches: {len(SUPPLIER_INVOICE_BRANCHES)}")
        print(f"📅 Data Range: {START_YEAR}-01-01 to Today")
        print(f"⚡ Parallel Workers: {INVOICE_WORKERS}")
        print("=" * 70)
        
        total_invoices = 0
        start_time = datetime.now()
        
        try:
            companies = self.get_enabled_companies()
            
            print(f"🔄 Processing {len(companies)} companies...")
            
            with ThreadPoolExecutor(max_workers=COMPANY_WORKERS) as executor:
                future_to_company = {
                    executor.submit(self.process_company_supplier_invoices, company): company 
                    for company in companies
                }
                
                for future in as_completed(future_to_company):
                    company = future_to_company[future]
                    try:
                        count = future.result()
                        total_invoices += count
                        print(f"✅ {company}: {count:,} new supplier invoices")
                        
                    except Exception as e:
                        self.logger.error(f"❌ Error processing {company}: {str(e)}")
                        print(f"❌ {company}: Failed - {str(e)}")
            
            end_time = datetime.now()
            duration = end_time - start_time
            
            print(f"\n" + "=" * 70)
            print("🎉 SUPPLIER INVOICE DOWNLOAD COMPLETE!")
            print("=" * 70)
            print(f"📦 Total New Supplier Invoices: {total_invoices:,}")
            print(f"⏱️  Time taken: {duration}")
            if duration.total_seconds() > 0 and total_invoices > 0:
                speed = total_invoices / duration.total_seconds()
                print(f"📊 Processing speed: {speed:.1f} invoices/second")
            print("=" * 70)
            
            self.logger.info(f"SUPPLIER INVOICE DOWNLOAD COMPLETED: {total_invoices} new invoices")
            
            return {"success": True, "total_invoices": total_invoices, "duration": str(duration)}
            
        except Exception as e:
            self.logger.error(f"❌ Fatal error: {str(e)}")
            print(f"❌ Fatal error: {str(e)}")
            return {"success": False, "message": str(e)}


def main():
    """Main entry point"""
    fetcher = DatabaseSupplierInvoicesFetcher()
    result = fetcher.run()
    
    if result.get("success"):
        print(f"\n✅ Successfully processed {result.get('total_invoices', 0)} supplier invoices")
    else:
        print(f"\n❌ Failed: {result.get('message', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()

