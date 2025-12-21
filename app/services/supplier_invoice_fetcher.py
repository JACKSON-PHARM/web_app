"""
Supplier Invoice Fetcher Service
Fetches supplier invoices directly from API for new arrivals
"""
import requests
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from app.services.credential_manager import CredentialManager
from app.config import settings
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class SupplierInvoiceFetcher:
    """Fetches supplier invoices from API for new arrivals"""
    
    BASE_URL = "https://corebasebackendnila.co.ke:5019"
    MAX_RETRIES = 2
    RETRY_DELAY = 0.5
    
    def __init__(self, credential_manager: CredentialManager):
        self.credential_manager = credential_manager
        self.session = requests.Session()
        self.token = None
    
    def _get_auth_token(self, company: str) -> Optional[str]:
        """Get authentication token for company"""
        try:
            token = self.credential_manager.get_valid_token(company)
            if token:
                self.token = token
                return token
            
            # Try to authenticate if no token
            creds = self.credential_manager.get_credentials(company)
            if not creds or not creds.get('username') or not creds.get('password'):
                logger.error(f"No credentials available for {company}")
                return None
            
            # Authenticate
            payload = {
                "userName": creds['username'],
                "password": creds['password']
            }
            
            headers = {
                "Content-Type": "application/json",
                "Origin": "https://phamacoreonline.co.ke:5100",
                "Referer": "https://phamacoreonline.co.ke:5100/",
                "Accept": "application/json"
            }
            
            response = self.session.post(
                f"{self.BASE_URL}/Auth",
                json=payload,
                headers=headers,
                verify=False,
                timeout=30
            )
            response.raise_for_status()
            
            token = response.json().get("token")
            if token:
                self.token = token
                logger.info(f"✅ Authenticated for {company}")
                return token
            
            logger.error(f"❌ No token received for {company}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Auth failed for {company}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def _api_request(self, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Optional[List]:
        """Make API request with retry logic"""
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.debug(f"🌐 API Request (attempt {attempt + 1}): {url}")
                logger.debug(f"   Params: {params}")
                
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    verify=False,
                    timeout=30
                )
                
                logger.debug(f"📡 Response status: {response.status_code}, content-length: {len(response.content) if response.content else 0}")
                
                if response.status_code == 400:
                    logger.warning(f"⚠️ API returned 400 Bad Request")
                    logger.debug(f"Response content: {response.text[:500]}")
                    return []
                elif response.status_code >= 500:
                    logger.warning(f"⚠️ API returned {response.status_code}")
                    if attempt < self.MAX_RETRIES - 1:
                        import time
                        time.sleep(self.RETRY_DELAY)
                        continue
                
                response.raise_for_status()
                
                if response.content:
                    try:
                        json_data = response.json()
                        logger.debug(f"✅ API returned data type: {type(json_data)}")
                        if isinstance(json_data, list):
                            logger.debug(f"   List length: {len(json_data)}")
                        elif isinstance(json_data, dict):
                            logger.debug(f"   Dict keys: {list(json_data.keys())}")
                        return json_data if json_data else []
                    except ValueError as e:
                        logger.error(f"❌ Failed to parse JSON: {e}")
                        logger.debug(f"Response text (first 500 chars): {response.text[:500]}")
                        return []
                else:
                    logger.warning(f"⚠️ Empty response")
                    return []
                    
            except Exception as e:
                logger.error(f"❌ API request failed (attempt {attempt + 1}): {e}")
                import traceback
                logger.debug(traceback.format_exc())
                if attempt < self.MAX_RETRIES - 1:
                    import time
                    time.sleep(self.RETRY_DELAY)
                    continue
        
        return None
    
    def _get_database_name(self, company: str) -> str:
        """Get database name for company
        
        NILA uses: PNLCUS0005DBREP
        DAIMA uses: P0757DB
        """
        database_names = {
            'NILA': 'PNLCUS0005DBREP',  # NILA database name
            'DAIMA': 'P0757DB'  # DAIMA database name
        }
        db_name = database_names.get(company.upper(), 'P0757DB')
        logger.debug(f"📊 Database name for {company}: {db_name}")
        return db_name
    
    def get_supplier_invoices(self, branch_num: int, start_date: datetime.date, end_date: datetime.date, company: str) -> List[Dict]:
        """Get supplier invoices for date range"""
        if not self.token:
            token = self._get_auth_token(company)
            if not token:
                return []
        
        # Get correct database name for company
        database_name = self._get_database_name(company)
        
        # Format dates as dd/mm/yyyy (matching working fetcher)
        params = {
            "bcode": branch_num,
            "batched": "",
            "account": "",
            "startDate": start_date.strftime("%d/%m/%Y"),
            "endDate": end_date.strftime("%d/%m/%Y"),
            "reference": "",
            "amount": "",
            "dataBaseName": database_name  # NILA: PNLCUS0005DBREP, DAIMA: P0757DB
        }
        
        logger.info(f"📊 Using database name: {database_name} for {company}")
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Origin": "https://phamacoreonline.co.ke:5100",
            "Referer": "https://phamacoreonline.co.ke:5100/",
            "Accept": "application/json"
        }
        
        logger.info(f"🔍 Requesting supplier invoices: bcode={branch_num}, startDate={params['startDate']}, endDate={params['endDate']}")
        
        result = self._api_request(
            f"{self.BASE_URL}/api/SupplierInvoice/GetSupplierInvoices",
            params=params,
            headers=headers
        )
        
        # Handle different response types (like the working fetcher does)
        if result is None:
            logger.warning(f"⚠️ API returned None for branch {branch_num}")
            return []
        
        if isinstance(result, list):
            invoice_count = len(result)
        elif isinstance(result, dict):
            if 'data' in result:
                invoice_count = len(result['data']) if isinstance(result['data'], list) else 0
                result = result['data']
            else:
                invoice_count = 1 if result else 0
                result = [result] if result else []
        else:
            invoice_count = 0
            result = []
        
        logger.info(f"📥 Supplier invoices for branch {branch_num}: {invoice_count} invoices")
        
        return result if isinstance(result, list) else []
    
    def get_supplier_invoice_details(self, branch_num: int, doc_id: int, company: str) -> List[Dict]:
        """Get supplier invoice details
        
        Args:
            branch_num: Branch code number
            doc_id: Document ID (integer, e.g., 13007578) - NOT the docNumber string
            company: Company name
        """
        if not self.token:
            token = self._get_auth_token(company)
            if not token:
                return []
        
        # Get correct database name for company
        database_name = self._get_database_name(company)
        
        # Use docID (integer) as suppInvNum parameter
        params = {
            "bcode": branch_num,
            "suppInvNum": doc_id,  # This should be the docID (integer), not docNumber
            "dataBaseName": database_name  # NILA: PNLCUS0005DBREP, DAIMA: P0757DB
        }
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Origin": "https://phamacoreonline.co.ke:5100",
            "Referer": "https://phamacoreonline.co.ke:5100/",
            "Accept": "application/json"
        }
        
        logger.debug(f"🔍 Requesting invoice details: bcode={branch_num}, suppInvNum={doc_id}")
        
        result = self._api_request(
            f"{self.BASE_URL}/api/SupplierInvoice/GetsupplierInvoiceDetails",
            params=params,
            headers=headers
        )
        
        return result or []
    
    def get_new_arrivals(self, branch_name: str = "BABA DOGO HQ", branch_code: int = 1, 
                        company: str = "NILA", days: int = 14) -> List[Dict]:
        """
        Get new arrivals (supplier invoices) from specified branch for the past N days
        
        Args:
            branch_name: Branch name (e.g., "BABA DOGO HQ")
            branch_code: Branch code number (e.g., 1 for BR001)
            company: Company name ("NILA" or "DAIMA")
            days: Number of days to look back (default: 14)
        
        Returns:
            List of invoice items with details
        """
        try:
            # Calculate date range
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            logger.info(f"📅 Fetching supplier invoices for {branch_name} ({company}) from {start_date} to {end_date}")
            
            # Get supplier invoices
            invoices = self.get_supplier_invoices(branch_code, start_date, end_date, company)
            
            if not invoices:
                logger.info(f"ℹ️ No supplier invoices found for {branch_name} in the past {days} days")
                return []
            
            # Process invoices and get details - LIMIT to most recent invoices for performance
            # Sort by date (most recent first) and limit to top 20 invoices to avoid timeout
            invoices_sorted = sorted(invoices, key=lambda x: x.get("docDate", ""), reverse=True)[:20]
            logger.info(f"📋 Processing top {len(invoices_sorted)} most recent invoices (out of {len(invoices)} total)")
            
            new_arrivals = []
            processed_count = 0
            
            for invoice in invoices_sorted:
                try:
                    doc_num = str(invoice.get("docNumber", "")).strip()
                    if not doc_num:
                        continue
                    
                    invoice_date_str = invoice.get("docDate")
                    if not invoice_date_str:
                        continue
                    
                    # Parse invoice date - handle ISO format "2025-12-18T00:00:00"
                    try:
                        # Try ISO format first (e.g., "2025-12-18T00:00:00")
                        if 'T' in str(invoice_date_str):
                            invoice_date = datetime.fromisoformat(str(invoice_date_str).replace('Z', '+00:00')).date()
                        else:
                            # Try standard date formats
                            invoice_date = datetime.strptime(str(invoice_date_str).strip(), "%Y-%m-%d").date()
                    except:
                        try:
                            invoice_date = datetime.strptime(str(invoice_date_str).strip(), "%d/%m/%Y").date()
                        except:
                            logger.warning(f"⚠️ Could not parse invoice date: {invoice_date_str}")
                            continue
                    
                    # Get docID (integer) - this is what we need for the details API
                    doc_id = invoice.get("docID")
                    if not doc_id:
                        logger.warning(f"⚠️ Invoice {doc_num} has no docID")
                        continue
                    
                    # Ensure doc_id is an integer
                    try:
                        doc_id = int(doc_id)
                    except (ValueError, TypeError):
                        logger.warning(f"⚠️ Invoice {doc_num} has invalid docID: {doc_id}")
                        continue
                    
                    processed_count += 1
                    if processed_count % 5 == 0:
                        logger.info(f"⏳ Processing invoice {processed_count}/{len(invoices_sorted)}... (docID: {doc_id})")
                    
                    # Get invoice details using docID (integer)
                    details = self.get_supplier_invoice_details(branch_code, doc_id, company)
                    
                    if not details:
                        continue
                    
                    # Process each item in the invoice
                    # Note: We only need item_code and date, rest will be enriched from stock data
                    for item in details:
                        try:
                            item_code = item.get("dT_ItemCode", "").strip()
                            if not item_code:
                                continue
                            
                            # Get quantity - use pwQty if available (pieces), else dT_Quantity
                            quantity = float(item.get("pwQty", 0) or item.get("dT_Quantity", 0) or 0)
                            if quantity <= 0:
                                continue
                            
                            new_arrivals.append({
                                "item_code": item_code,
                                "item_name": item.get("dT_ItemName", "").strip(),
                                "quantity": quantity,  # Quantity in pieces
                                "document_date": invoice_date.isoformat(),
                                "document_number": doc_num,
                                "source_type": "Supplier Invoice",
                                "branch": branch_name,
                                "company": company,
                                # Additional fields for reference (will be enriched with stock data)
                                "unit_price": float(item.get("dT_Price", 0) or 0),
                                "total_amount": float(item.get("dT_Total", 0) or 0),
                                "supplier_id": item.get("hD2_SUPPLIERID", ""),
                                "supplier_name": item.get("hD2_SUPPLIERNAME", ""),
                                "reference": item.get("hD2_Reference", ""),
                                "done_by": item.get("hD2_Doneby", ""),
                                "document_status": item.get("hD2_Docstatus", "")
                            })
                        except Exception as e:
                            logger.warning(f"⚠️ Error processing invoice item: {e}")
                            import traceback
                            logger.debug(traceback.format_exc())
                            continue
                
                except Exception as e:
                    logger.warning(f"⚠️ Error processing invoice {doc_num}: {e}")
                    continue
            
            logger.info(f"✅ Found {len(new_arrivals)} new arrival items from {branch_name} (past {days} days)")
            return new_arrivals
            
        except Exception as e:
            logger.error(f"❌ Error fetching new arrivals: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

