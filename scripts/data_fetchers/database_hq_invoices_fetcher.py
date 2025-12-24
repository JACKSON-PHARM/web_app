"""
HQ Invoices Fetcher
Fetches sales invoices and branch transfers from BABA DOGO HQ API
and stores them in the hq_invoices table
"""
import logging
import requests
import urllib3
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.services.database_manager import DatabaseManager
from app.services.credential_manager import CredentialManager
from app.config import settings

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class DatabaseHQInvoicesFetcher:
    """Fetches HQ invoices and branch transfers from API and stores in database"""
    
    # Daima branches to filter for
    DAIMA_BRANCHES = [
        "DAIMA MERU RETAIL",
        "DAIMA THIKA RETAIL", 
        "DAIMA BIASHARA THIKA WHOLESALE",
        "DAIMA MERU WHOLESALE",
        "DAIMA MAKUTANO RETAILS"
    ]
    
    def __init__(self, db_manager: DatabaseManager, credential_manager: CredentialManager):
        self.db_manager = db_manager
        self.credential_manager = credential_manager
        self.base_url = settings.NILA_API_URL or "https://corebasebackendnila.co.ke:5019"
        self.logger = logging.getLogger("DatabaseHQInvoicesFetcher")
        
    def _get_auth_token(self) -> Optional[str]:
        """Authenticate and get JWT token"""
        creds = self.credential_manager.get_credentials("NILA")
        if not creds:
            self.logger.error("No NILA credentials found")
            return None
        
        payload = {
            "userName": creds.get("username"),
            "password": creds.get("password"),
            "machineCookie": "",
            "clientPin": 0,
            "latt": "",
            "long": "",
            "ipLocation": ""
        }
        
        url = f"{self.base_url}/Auth"
        
        try:
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                verify=False,
                timeout=15
            )
            response.raise_for_status()
            return response.json().get("token")
        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            return None
    
    def _get_sales_invoices(self, token: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Fetch sales invoices from BABA DOGO HQ (BR001)"""
        url = f"{self.base_url}/api/SalesInvoice/GetSalesInvoice"
        params = {
            "bcode": 1,  # BR001
            "startDate": start_date.strftime("%d/%m/%Y"),
            "endDate": end_date.strftime("%d/%m/%Y"),
            "batched": "true",
            "cusRef": "",
            "account": "",
            "amount": "",
            "salesCategory": 0,
            "viewall": "true"
        }
        
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(url, params=params, headers=headers, verify=False, timeout=30)
            response.raise_for_status()
            invoices = response.json() or []
            
            # Filter for Daima branches
            filtered = [inv for inv in invoices if inv.get("acctName") in self.DAIMA_BRANCHES]
            return filtered
        except Exception as e:
            self.logger.error(f"Failed to fetch invoices: {e}")
            return []
    
    def _get_invoice_details(self, token: str, doc_id: str) -> List[Dict]:
        """Fetch detailed invoice items"""
        url = f"{self.base_url}/api/SalesInvoice/GetSalesInvoiceDetails"
        params = {"bcode": 1, "invNumber": doc_id}
        
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(url, params=params, headers=headers, verify=False, timeout=30)
            response.raise_for_status()
            return response.json().get("salesinvoicedetails", [])
        except Exception as e:
            self.logger.error(f"Failed to fetch invoice details for {doc_id}: {e}")
            return []
    
    def _get_branch_transfers(self, token: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Fetch branch transfers created by BABA DOGO HQ"""
        url = f"{self.base_url}/api/BranchTransfer/GetBranchTransfers"
        params = {
            "bcode": 1,
            "posted": "true",
            "startDate": start_date.strftime("%d/%m/%Y"),
            "endDate": end_date.strftime("%d/%m/%Y"),
            "reference": "",
            "amount": ""
        }
        
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(url, params=params, headers=headers, verify=False, timeout=30)
            response.raise_for_status()
            return response.json() or []
        except Exception as e:
            self.logger.error(f"Failed to fetch branch transfers: {e}")
            return []
    
    def _get_transfer_details(self, token: str, doc_id: str) -> List[Dict]:
        """Fetch detailed transfer items"""
        url = f"{self.base_url}/api/BranchTransfer/GetBranchTransfersDetails"
        params = {"bcode": 1, "docID": doc_id}
        
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(url, params=params, headers=headers, verify=False, timeout=30)
            response.raise_for_status()
            return response.json() or []
        except Exception as e:
            self.logger.error(f"Failed to fetch transfer details for {doc_id}: {e}")
            return []
    
    def _process_invoice_data(self, invoice: Dict, details: List[Dict]) -> List[Dict]:
        """Transform invoice data to hq_invoices format"""
        processed = []
        branch_name = invoice.get("acctName", "UNKNOWN")
        invoice_number = invoice.get("docNumber", "")
        doc_date_str = invoice.get("docDate", "")
        
        # Parse date
        try:
            if 'T' in doc_date_str:
                doc_date = datetime.strptime(doc_date_str.split('T')[0], "%Y-%m-%d").date()
            else:
                doc_date = datetime.strptime(doc_date_str, "%Y-%m-%d").date()
        except:
            doc_date = datetime.now().date()
        
        for item in details:
            processed.append({
                "branch": branch_name,
                "invoice_number": invoice_number,
                "item_code": item.get("dT_ItemCode", ""),
                "item_name": item.get("dT_ItemName", ""),
                "quantity": float(item.get("dT_Quantity", 0) or 0),
                "ref": item.get("hD2_Comments", ""),
                "date": doc_date,
                "document_type": "Invoice",
                "source_branch": "BABA DOGO HQ",
                "destination_branch": branch_name
            })
        
        return processed
    
    def _process_transfer_data(self, transfer: Dict, details: List[Dict]) -> List[Dict]:
        """Transform transfer data to hq_invoices format"""
        processed = []
        branch_name = transfer.get("acctName", "UNKNOWN")  # Destination branch
        transfer_number = transfer.get("docNumber", "")
        doc_date_str = transfer.get("docDate", "")
        
        # Parse date
        try:
            if 'T' in doc_date_str:
                doc_date = datetime.strptime(doc_date_str.split('T')[0], "%Y-%m-%d").date()
            else:
                doc_date = datetime.strptime(doc_date_str, "%Y-%m-%d").date()
        except:
            doc_date = datetime.now().date()
        
        for item in details:
            processed.append({
                "branch": branch_name,
                "invoice_number": transfer_number,
                "item_code": item.get("dT_ItemCode", ""),
                "item_name": item.get("dT_ItemName", ""),
                "quantity": float(item.get("dT_Quantity", 0) or 0),
                "ref": item.get("hD2_Reference", ""),
                "date": doc_date,
                "document_type": "Branch Transfer",
                "source_branch": "BABA DOGO HQ",
                "destination_branch": branch_name
            })
        
        return processed
    
    def _update_monthly_quantities(self, conn, cursor, current_month: int, current_year: int):
        """Update this_month_qty for all records in current month"""
        try:
            # Use PostgreSQL or SQLite syntax
            if hasattr(self.db_manager, 'get_connection'):
                # PostgreSQL
                cursor.execute("""
                    UPDATE hq_invoices h1
                    SET this_month_qty = (
                        SELECT COALESCE(SUM(quantity), 0)
                        FROM hq_invoices h2
                        WHERE h2.branch = h1.branch
                          AND h2.item_code = h1.item_code
                          AND EXTRACT(MONTH FROM h2.date) = %s
                          AND EXTRACT(YEAR FROM h2.date) = %s
                    )
                    WHERE EXTRACT(MONTH FROM h1.date) = %s
                      AND EXTRACT(YEAR FROM h1.date) = %s
                """, (current_month, current_year, current_month, current_year))
            else:
                # SQLite
                cursor.execute("""
                    UPDATE hq_invoices
                    SET this_month_qty = (
                        SELECT COALESCE(SUM(quantity), 0)
                        FROM hq_invoices h2
                        WHERE h2.branch = hq_invoices.branch
                          AND h2.item_code = hq_invoices.item_code
                          AND strftime('%%m', h2.date) = ?
                          AND strftime('%%Y', h2.date) = ?
                    )
                    WHERE strftime('%%m', date) = ?
                      AND strftime('%%Y', date) = ?
                """, (f"{current_month:02d}", str(current_year), f"{current_month:02d}", str(current_year)))
            
            updated = cursor.rowcount
            self.logger.info(f"✅ Updated this_month_qty for {updated} records")
        except Exception as e:
            self.logger.error(f"Error updating monthly quantities: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
    
    def fetch_data(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> int:
        """
        Fetch invoices and transfers from API and store in database
        Returns number of records processed
        """
        if start_date is None:
            # Default to last 30 days (for Supabase free tier)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
        elif end_date is None:
            end_date = datetime.now()
        
        self.logger.info(f"🔄 Fetching HQ invoices/transfers from {start_date.date()} to {end_date.date()}")
        
        token = self._get_auth_token()
        if not token:
            self.logger.error("❌ Failed to authenticate")
            return 0
        
        total_records = 0
        
        # Get database connection (works for both PostgreSQL and SQLite)
        try:
            if hasattr(self.db_manager, 'get_connection'):
                # PostgreSQL
                conn = self.db_manager.get_connection()
                cursor = conn.cursor()
            elif hasattr(self.db_manager, 'get_db_connection'):
                # SQLite
                conn = self.db_manager.get_db_connection()
                cursor = conn.cursor()
            else:
                self.logger.error("Database manager doesn't support get_connection() or get_db_connection()")
                return 0
        except Exception as e:
            self.logger.error(f"Failed to get database connection: {e}")
            return 0
        
        try:
            
            # Process invoices
            self.logger.info("📥 Fetching sales invoices...")
            invoices = self._get_sales_invoices(token, start_date, end_date)
            self.logger.info(f"   Found {len(invoices)} invoices")
            
            for invoice in invoices:
                doc_id = invoice.get("docID")
                if not doc_id:
                    continue
                
                details = self._get_invoice_details(token, doc_id)
                if details:
                    processed = self._process_invoice_data(invoice, details)
                    
                    # Insert into database
                    for record in processed:
                        try:
                            # Use PostgreSQL or SQLite syntax
                            if hasattr(self.db_manager, 'get_connection'):
                                # PostgreSQL
                                cursor.execute("""
                                    INSERT INTO hq_invoices 
                                    (branch, invoice_number, item_code, item_name, quantity, ref, date, 
                                     document_type, source_branch, destination_branch)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    ON CONFLICT (branch, invoice_number, item_code, date)
                                    DO UPDATE SET
                                        item_name = EXCLUDED.item_name,
                                        quantity = EXCLUDED.quantity,
                                        ref = EXCLUDED.ref,
                                        document_type = EXCLUDED.document_type,
                                        source_branch = EXCLUDED.source_branch,
                                        destination_branch = EXCLUDED.destination_branch,
                                        processed_at = CURRENT_TIMESTAMP
                                """, (
                                    record["branch"], record["invoice_number"], record["item_code"],
                                    record["item_name"], record["quantity"], record["ref"],
                                    record["date"], record["document_type"],
                                    record["source_branch"], record["destination_branch"]
                                ))
                            else:
                                # SQLite
                                cursor.execute("""
                                    INSERT OR REPLACE INTO hq_invoices 
                                    (branch, invoice_number, item_code, item_name, quantity, ref, date, 
                                     document_type, source_branch, destination_branch)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    record["branch"], record["invoice_number"], record["item_code"],
                                    record["item_name"], record["quantity"], record["ref"],
                                    record["date"], record["document_type"],
                                    record["source_branch"], record["destination_branch"]
                                ))
                            total_records += 1
                        except Exception as e:
                            self.logger.warning(f"Failed to insert invoice record: {e}")
                            continue
            
            # Process branch transfers
            self.logger.info("📥 Fetching branch transfers...")
            transfers = self._get_branch_transfers(token, start_date, end_date)
            self.logger.info(f"   Found {len(transfers)} transfers")
            
            for transfer in transfers:
                doc_id = transfer.get("docID")
                if not doc_id:
                    continue
                
                details = self._get_transfer_details(token, doc_id)
                if details:
                    processed = self._process_transfer_data(transfer, details)
                    
                    # Insert into database
                    for record in processed:
                        try:
                            # Use PostgreSQL or SQLite syntax
                            if hasattr(self.db_manager, 'get_connection'):
                                # PostgreSQL
                                cursor.execute("""
                                    INSERT INTO hq_invoices 
                                    (branch, invoice_number, item_code, item_name, quantity, ref, date,
                                     document_type, source_branch, destination_branch)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    ON CONFLICT (branch, invoice_number, item_code, date)
                                    DO UPDATE SET
                                        item_name = EXCLUDED.item_name,
                                        quantity = EXCLUDED.quantity,
                                        ref = EXCLUDED.ref,
                                        document_type = EXCLUDED.document_type,
                                        source_branch = EXCLUDED.source_branch,
                                        destination_branch = EXCLUDED.destination_branch,
                                        processed_at = CURRENT_TIMESTAMP
                                """, (
                                    record["branch"], record["invoice_number"], record["item_code"],
                                    record["item_name"], record["quantity"], record["ref"],
                                    record["date"], record["document_type"],
                                    record["source_branch"], record["destination_branch"]
                                ))
                            else:
                                # SQLite
                                cursor.execute("""
                                    INSERT OR REPLACE INTO hq_invoices 
                                    (branch, invoice_number, item_code, item_name, quantity, ref, date,
                                     document_type, source_branch, destination_branch)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    record["branch"], record["invoice_number"], record["item_code"],
                                    record["item_name"], record["quantity"], record["ref"],
                                    record["date"], record["document_type"],
                                    record["source_branch"], record["destination_branch"]
                                ))
                            total_records += 1
                        except Exception as e:
                            self.logger.warning(f"Failed to insert transfer record: {e}")
                            continue
            
            conn.commit()
            
            # Update monthly quantities
            current_month = datetime.now().month
            current_year = datetime.now().year
            self._update_monthly_quantities(conn, cursor, current_month, current_year)
            conn.commit()
            
            self.logger.info(f"✅ Processed {total_records} invoice/transfer records")
            
        except Exception as e:
            self.logger.error(f"❌ Error fetching HQ invoices: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            conn.rollback()
        finally:
            cursor.close()
            if hasattr(self.db_manager, 'put_connection'):
                self.db_manager.put_connection(conn)
            else:
                conn.close()
        
        return total_records

