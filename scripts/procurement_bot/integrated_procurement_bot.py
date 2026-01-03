"""
Integrated Procurement Bot
Creates Purchase Orders and Branch Orders via API
"""
import os
import sys
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3

# Disable SSL warnings (API uses self-signed certificates)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Add app root to path
app_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if app_root not in sys.path:
    sys.path.insert(0, app_root)

logger = logging.getLogger(__name__)


class IntegratedProcurementBot:
    """
    Integrated Procurement Bot for creating orders via API
    """
    
    def __init__(self, stock_view_df: pd.DataFrame, branch_name: str, branch_code: int,
                 company: str, credential_manager, order_mode: str = "purchase_order",
                 branch_to_name: Optional[str] = None, branch_to_code: Optional[str] = None,
                 manual_selection: bool = True, supplier_code: Optional[str] = None,
                 supplier_name: Optional[str] = None):
        """
        Initialize procurement bot
        
        Args:
            stock_view_df: DataFrame with items to order
            branch_name: Branch name making the order
            branch_code: Branch code (numeric)
            company: Company name (NILA or DAIMA)
            credential_manager: Credential manager instance
            order_mode: "purchase_order" or "branch_order"
            branch_to_name: Target branch name (for branch orders)
            branch_to_code: Target branch code (for branch orders)
            manual_selection: Whether items were manually selected
            supplier_code: Supplier code (for purchase orders)
            supplier_name: Supplier name (for purchase orders)
        """
        self.stock_view_df = stock_view_df.copy()
        self.branch_name = branch_name
        self.branch_code = branch_code
        self.company = company
        self.credential_manager = credential_manager
        self.order_mode = order_mode
        self.branch_to_name = branch_to_name
        self.branch_to_code = branch_to_code
        self.manual_selection = manual_selection
        self.supplier_code = supplier_code
        self.supplier_name = supplier_name
        self.base_url = getattr(credential_manager, 'base_url', 'https://corebasebackendnila.co.ke:5019')
        self.order_doc_number = None
        
        logger.info(f"Initialized procurement bot: mode={order_mode}, branch={branch_name}, items={len(stock_view_df)}")
    
    def prepare_data(self) -> pd.DataFrame:
        """
        Prepare data for ordering
        
        Returns:
            Prepared DataFrame
        """
        df = self.stock_view_df.copy()
        
        # Ensure required columns exist
        if 'order_quantity' not in df.columns:
            if 'custom_order_quantity' in df.columns:
                df['order_quantity'] = df['custom_order_quantity'].fillna(df.get('amc', 1))
            elif 'amc' in df.columns:
                df['order_quantity'] = df['amc'].fillna(1)
            else:
                df['order_quantity'] = 1
        
        # Ensure order_quantity is numeric
        df['order_quantity'] = pd.to_numeric(df['order_quantity'], errors='coerce').fillna(1)
        
        # Filter out items with zero or negative quantities
        df = df[df['order_quantity'] > 0].copy()
        
        logger.info(f"Prepared {len(df)} items for ordering")
        return df
    
    def select_items(self, prepared_df: pd.DataFrame) -> pd.DataFrame:
        """
        Select items for ordering (for auto-selection mode)
        
        Args:
            prepared_df: Prepared DataFrame
            
        Returns:
            Selected items DataFrame
        """
        # For manual selection, this is not used
        # For auto-selection, return all prepared items
        return prepared_df.copy()
    
    def get_session(self) -> requests.Session:
        """Get requests session with retry strategy"""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session
    
    def get_token(self) -> Optional[str]:
        """Get authentication token"""
        try:
            # Use the company for authentication (this is the procurement company selected by user)
            auth_company = self.company
            logger.info(f"🔐 Getting token for company: {auth_company}")
            
            # First try to get token from credential manager
            token = self.credential_manager.get_valid_token(auth_company)
            if token:
                logger.info(f"✅ Got token from credential manager cache")
                return token
            
            # If no cached token, get credentials and authenticate
            logger.info(f"🔐 No cached token, authenticating with API for company: {auth_company}...")
            creds = self.credential_manager.get_credentials(auth_company)
            if not creds:
                logger.error(f"❌ No credentials found for company: {self.company}")
                return None
            
            username = creds.get('username')
            password = creds.get('password')
            base_url = creds.get('base_url', self.base_url)
            
            if not username or not password:
                logger.error(f"❌ Missing username or password for company: {self.company}")
                return None
            
            logger.info(f"🔐 Authenticating user: {username} with API: {base_url}")
            session = self.get_session()
            # Use /Auth endpoint (not /api/auth/login) with userName/password format
            auth_url = f"{base_url}/Auth"
            
            try:
                response = session.post(auth_url, json={
                    'userName': username,  # Note: userName (camelCase), not username
                    'password': password
                }, timeout=15, verify=False)
                
                logger.info(f"🔐 Auth response status: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        # API returns 'token', not 'access_token'
                        token = data.get('token')
                        if token:
                            logger.info(f"✅ Successfully authenticated, got token")
                            return token
                        else:
                            logger.error(f"❌ No token in response: {data}")
                            return None
                    except ValueError as e:
                        # Response is not JSON
                        logger.error(f"❌ Response is not JSON: {response.text[:200]}")
                        return None
                else:
                    error_text = response.text[:500] if response.text else "No error message"
                    logger.error(f"❌ Authentication failed: HTTP {response.status_code} - {error_text}")
                    return None
                    
            except requests.exceptions.Timeout:
                logger.error(f"❌ Authentication request timed out")
                return None
            except requests.exceptions.ConnectionError as e:
                logger.error(f"❌ Connection error during authentication: {e}")
                return None
            except Exception as e:
                logger.error(f"❌ Error during authentication request: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return None
                
        except Exception as e:
            logger.error(f"❌ Error getting token: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def create_purchase_order(self, items_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Create purchase order via API using MakePurchaseOrderHybridV2 endpoint
        Matches the payload structure from the standalone procurement script
        
        Args:
            items_df: DataFrame with items to order
            
        Returns:
            Result dictionary
        """
        try:
            token = self.get_token()
            if not token:
                return {
                    'success': False,
                    'message': 'Failed to get authentication token'
                }
            
            session = self.get_session()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Origin": "https://phamacoreonline.co.ke:5100",
                "Referer": "https://phamacoreonline.co.ke:5100/",
                "Accept": "application/json"
            }
            
            # Default values matching standalone script
            DEFAULT_ITEM_PRICE = 100.00
            DEFAULT_VAT_CODE = "00"
            DEFAULT_DISCOUNT = 0.01  # 1%
            
            # Ensure branch code is valid (cannot be 0)
            if not self.branch_code or self.branch_code == 0:
                return {
                    'success': False,
                    'message': f'Invalid branch code: {self.branch_code}. Branch code cannot be 0.'
                }
            
            # Ensure supplier code and name are provided
            if not self.supplier_code or not self.supplier_name:
                return {
                    'success': False,
                    'message': 'Supplier code and name are required for purchase orders'
                }
            
            # Initialize or reuse order document number
            if not self.order_doc_number:
                # Try to get existing order for today
                try:
                    today = datetime.now().strftime("%d/%m/%Y")
                    get_orders_url = f"{self.base_url}/api/PurchaseOrder/GetPurchaseOrders"
                    get_orders_params = {
                        "bcode": self.branch_code,
                        "startDate": today,
                        "endDate": today
                    }
                    get_orders_response = session.get(
                        get_orders_url,
                        params=get_orders_params,
                        headers=headers,
                        timeout=30,
                        verify=False
                    )
                    
                    if get_orders_response.status_code == 200:
                        orders = get_orders_response.json()
                        # Handle both list and dict responses
                        if orders:
                            if isinstance(orders, list) and len(orders) > 0:
                                # If it's a list, get first element
                                first_order = orders[0]
                                if isinstance(first_order, dict):
                                    self.order_doc_number = str(first_order.get("docNumber", ""))
                                else:
                                    self.order_doc_number = str(first_order) if first_order else ""
                            elif isinstance(orders, dict):
                                # If it's a dict, try to get docNumber directly
                                self.order_doc_number = str(orders.get("docNumber", ""))
                            
                            if self.order_doc_number:
                                logger.info(f"Reusing existing order: {self.order_doc_number}")
                    
                    if not self.order_doc_number:
                        # Generate new order number
                        import random
                        self.order_doc_number = f"P{datetime.now().strftime('%m%d')}{random.randint(1000, 9999)}"
                        logger.info(f"Creating new order: {self.order_doc_number}")
                except Exception as e:
                    logger.warning(f"Could not check for existing orders, creating new: {e}")
                    import random
                    self.order_doc_number = f"P{datetime.now().strftime('%m%d')}{random.randint(1000, 9999)}"
            
            # Prepare order items in the format expected by MakePurchaseOrderHybridV2
            item_list = []
            total_excl = 0
            now = datetime.now()
            
            for idx, (_, row) in enumerate(items_df.iterrows(), 1):
                item_code = str(row.get('item_code', '')).strip()
                item_name = str(row.get('item_name', 'Unknown')).strip()
                quantity = float(row.get('order_quantity', 0))
                unit_price = float(row.get('unit_price', 0))
                amc = float(row.get('amc', 0))
                
                # Ensure quantity is at least 1 (API requires quantity >= 1)
                qty = max(1, int(round(quantity)))
                if quantity < 1:
                    logger.warning(f"⚠️ Item {item_code} has quantity {quantity} < 1, rounding up to 1")
                
                if not item_code:
                    logger.warning(f"⚠️ Skipping item with empty item_code")
                    continue
                
                # Use default price if unit_price is 0 or missing
                if unit_price <= 0:
                    unit_price = DEFAULT_ITEM_PRICE
                    logger.info(f"⚠️ Item {item_code} has no price, using default price: {DEFAULT_ITEM_PRICE}")
                
                total = qty * unit_price
                total_excl += total
                
                # Create informative comment
                comment = (
                    f"Auto-Order | AMC: {amc:.1f} | Stock: {row.get('branch_stock', 0)} | "
                    f"Class: {row.get('abc_class', 'N/A')}"
                )
                
                item_list.append({
                    "itemCode": item_code,
                    "itemName": item_name,
                    "saleQty": f"{qty}W0P",
                    "avgSale": f"{amc:.1f}W0P",
                    "reqQty": f"{qty}W0P",
                    "inStore": "0W0P",
                    "var": f"{qty}W0P",
                    "ordQty": f"{qty}W0P",
                    "getsel": 1,
                    "lastPrice": unit_price,
                    "suppCode": self.supplier_code,
                    "suppName": self.supplier_name,
                    "packqty": 1,
                    "ordQtyValue": float(qty),
                    "tradeprice": unit_price,
                    "comments": comment,
                    "tableData": {"id": idx},
                    "dT_Vat": DEFAULT_VAT_CODE,
                    "dT_Disc": DEFAULT_DISCOUNT,
                    "dT_Bonus": 0.0,
                    "dT_Unit": 1.0,
                    "dT_PW": "W",
                    "dT_Total": total,
                    "dT_Nett": total * (1 - DEFAULT_DISCOUNT)
                })
            
            if not item_list:
                return {
                    'success': False,
                    'message': 'No valid items to order'
                }
            
            # Calculate totals
            total_discount = total_excl * DEFAULT_DISCOUNT
            total_nett = total_excl - total_discount
            
            # Prepare payload matching standalone script structure
            payload = {
                "data": [{
                    "dochybridneo": 1,
                    "bcode": int(self.branch_code),  # Branch code (cannot be 0)
                    "supCode": self.supplier_code,  # Supplier code
                    "docNumber": self.order_doc_number,
                    "itemList": item_list,
                    "hD1_DocNum": self.order_doc_number,
                    "hD2_Date": now.strftime("%Y-%m-%dT%H:%M:%S"),
                    "hD2_Expdeliv": (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S"),
                    "suppName": self.supplier_name,
                    "hD2_Comments": f"Auto-generated order | {len(item_list)} items | {now.strftime('%d/%m/%Y %H:%M')}",
                    "hD2_Doneby": getattr(self.credential_manager, 'username', 'System'),
                    "summ_Excl": total_excl,
                    "summ_Nett": total_nett,
                    "summ_Disc": total_discount,
                    "summ_Total": total_excl
                }]
            }
            
            logger.info(f"Generated payload for {len(item_list)} items | Total value: {total_excl:.2f}")
            
            # Create order via API using MakePurchaseOrderHybridV2 endpoint
            url = f"{self.base_url}/api/PurchaseOrder/MakePurchaseOrderHybridV2"
            response = session.post(url, json=payload, headers=headers, timeout=60, verify=False)
            
            if response.status_code in [200, 201]:
                try:
                    result = response.json()
                    order_number = self.order_doc_number  # Default to our generated number
                    
                    # Handle different response formats
                    if isinstance(result, dict):
                        # If response is a dict, try to extract order number
                        order_number = result.get('docNumber') or result.get('orderNumber') or result.get('doc_number') or self.order_doc_number
                    elif isinstance(result, list) and len(result) > 0:
                        # If response is a list, get first element
                        first_item = result[0]
                        if isinstance(first_item, dict):
                            order_number = first_item.get('docNumber') or first_item.get('orderNumber') or first_item.get('doc_number') or self.order_doc_number
                        else:
                            order_number = str(first_item) if first_item else self.order_doc_number
                    
                    self.order_doc_number = order_number
                    
                    logger.info(f"✅ Purchase order created: {order_number}")
                    return {
                        'success': True,
                        'message': f'Purchase order created successfully',
                        'order_number': order_number,
                        'processed_count': len(item_list)
                    }
                except ValueError as e:
                    # Response might not be JSON, but status is 200/201
                    logger.warning(f"Response is not JSON (status {response.status_code}): {e}")
                    logger.info(f"✅ Purchase order created (non-JSON response): {self.order_doc_number}")
                    return {
                        'success': True,
                        'message': f'Purchase order created successfully',
                        'order_number': self.order_doc_number,
                        'processed_count': len(item_list)
                    }
                except Exception as e:
                    # Any other error parsing response, but status is 200/201 so assume success
                    logger.warning(f"Error parsing response but status is {response.status_code}: {e}")
                    logger.info(f"✅ Purchase order created (response parse error): {self.order_doc_number}")
                    return {
                        'success': True,
                        'message': f'Purchase order created successfully',
                        'order_number': self.order_doc_number,
                        'processed_count': len(item_list)
                    }
            else:
                error_msg = response.text or f"HTTP {response.status_code}"
                logger.error(f"❌ Purchase order creation failed: {error_msg}")
                
                # Try to parse error details
                try:
                    error_json = response.json()
                    # Handle both dict and list error responses
                    if isinstance(error_json, dict):
                        errors = error_json.get('errors', {})
                        if errors:
                            error_details = []
                            for field, messages in errors.items():
                                if isinstance(messages, list):
                                    error_details.extend([f"{field}: {msg}" for msg in messages])
                                else:
                                    error_details.append(f"{field}: {messages}")
                            error_msg = " | ".join(error_details)
                        # Also check for direct error message
                        if 'message' in error_json:
                            error_msg = error_json.get('message', error_msg)
                        if 'title' in error_json:
                            error_msg = f"{error_json.get('title', '')}: {error_msg}"
                    elif isinstance(error_json, list) and len(error_json) > 0:
                        # If error is a list, try to extract messages
                        error_details = []
                        for item in error_json:
                            if isinstance(item, dict):
                                if 'message' in item:
                                    error_details.append(item['message'])
                                elif 'error' in item:
                                    error_details.append(item['error'])
                            else:
                                error_details.append(str(item))
                        if error_details:
                            error_msg = " | ".join(error_details)
                except Exception as parse_error:
                    logger.debug(f"Could not parse error response: {parse_error}")
                    pass
                
                return {
                    'success': False,
                    'message': f'Failed to create purchase order: {error_msg}'
                }
                
        except Exception as e:
            logger.error(f"❌ Error creating purchase order: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'message': f'Error creating purchase order: {str(e)}'
            }
    
    def _get_database_name(self, company: str) -> str:
        """Get database name for company"""
        database_names = {
            'NILA': 'PNLCUS0005DB',
            'DAIMA': 'P0757DB'
        }
        return database_names.get(company.upper(), 'PNLCUS0005DB')
    
    def create_branch_order(self, items_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Create branch order via API
        Branch orders are created item-by-item:
        - First item creates the order (bdocid=0)
        - Subsequent items use the returned bdocid and bdocnumber
        
        Args:
            items_df: DataFrame with items to order
            
        Returns:
            Result dictionary
        """
        try:
            token = self.get_token()
            if not token:
                return {
                    'success': False,
                    'message': 'Failed to get authentication token'
                }
            
            session = self.get_session()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            # For branch orders:
            # - self.branch_code = TARGET branch code (where order is CREATED) - used as bcode
            # - self.branch_to_code = SOURCE branch code (where stock comes FROM) - used as branchToCode
            # Get source branch code (as string like "BR001") for branchToCode
            source_branch_code_str = None
            if self.branch_to_code:
                if isinstance(self.branch_to_code, str):
                    if self.branch_to_code.startswith('BR'):
                        source_branch_code_str = self.branch_to_code
                    else:
                        # Convert numeric to BR format
                        try:
                            num = int(self.branch_to_code)
                            source_branch_code_str = f"BR{num:03d}"
                        except:
                            source_branch_code_str = self.branch_to_code
                else:
                    # Convert numeric to BR format
                    try:
                        num = int(self.branch_to_code)
                        source_branch_code_str = f"BR{num:03d}"
                    except:
                        source_branch_code_str = str(self.branch_to_code)
            
            if not source_branch_code_str:
                return {
                    'success': False,
                    'message': f'Invalid source branch code: {self.branch_to_code}'
                }
            
            # Get database name based on company
            database_name = self._get_database_name(self.company)
            
            # Get current date in DD/MM/YYYY format
            today = datetime.now()
            date_str = today.strftime("%d/%m/%Y")
            
            # Filter valid items
            # Default price to use when unit_price is 0 or missing
            DEFAULT_ITEM_PRICE = 5.0
            
            valid_items = []
            for _, row in items_df.iterrows():
                item_code = str(row.get('item_code', '')).strip()
                quantity = float(row.get('order_quantity', 0))
                unit_price = float(row.get('unit_price', 0))
                
                if not item_code or quantity <= 0:
                    continue
                
                # Use default price if unit_price is 0 or missing
                if unit_price <= 0:
                    unit_price = DEFAULT_ITEM_PRICE
                    logger.info(f"⚠️ Item {item_code} has no price, using default price: {DEFAULT_ITEM_PRICE}")
                
                valid_items.append({
                    'item_code': item_code,
                    'item_name': str(row.get('item_name', '')).strip(),
                    'quantity': quantity,
                    'pack_size': float(row.get('pack_size', 1)),
                    'unit_price': unit_price
                })
            
            if not valid_items:
                return {
                    'success': False,
                    'message': 'No valid items to order'
                }
            
            # Process items in batches of 10 per order
            MAX_ITEMS_PER_ORDER = 10
            processed_count = 0
            all_order_numbers = []
            
            # Split items into batches of max 10 items per order
            item_batches = []
            for i in range(0, len(valid_items), MAX_ITEMS_PER_ORDER):
                item_batches.append(valid_items[i:i + MAX_ITEMS_PER_ORDER])
            
            logger.info(f"📦 Processing {len(valid_items)} items in {len(item_batches)} order(s) (max {MAX_ITEMS_PER_ORDER} items per order)")
            
            # Process each batch as a separate order
            for batch_idx, batch_items in enumerate(item_batches):
                # Initialize order document IDs for this batch (will be set after first item)
                bdocid = 0
                bdocnumber = ""
                batch_processed = 0
                
                logger.info(f"📋 Creating order {batch_idx + 1}/{len(item_batches)} with {len(batch_items)} items")
                
                # Process items one by one within this batch
                for idx, item in enumerate(batch_items):
                    # Prepare item payload
                    # Note: Quantity should be in packs (already in packs from AMC)
                    # Ensure quantity is at least 1 (API requires quantity >= 1)
                    quantity_packs = max(1, int(round(item['quantity'])))
                    if item['quantity'] < 1:
                        logger.warning(f"⚠️ Item {item['item_code']} has quantity {item['quantity']} < 1, rounding up to 1")
                    
                    # Log current order state before making request
                    if idx == 0:
                        logger.info(f"📝 Creating NEW order for item {idx + 1} (bdocid=0, bdocnumber='')")
                    else:
                        logger.info(f"📝 Adding item {idx + 1} to EXISTING order (bdocid={bdocid}, bdocnumber={bdocnumber})")
                    
                    item_payload = {
                        "bcode": int(self.branch_code),  # TARGET branch code (where order is CREATED) - numeric, e.g., 18
                        "branchToCode": source_branch_code_str,  # SOURCE branch code (where stock comes FROM) - e.g., "BR001"
                        "boddate": date_str,  # Order date (DD/MM/YYYY)
                        "boddeldate": date_str,  # Delivery date (DD/MM/YYYY)
                        "bodsuppref": "",  # Supplier reference (empty for branch orders)
                        "bodcomments": "URGENT",  # Comments
                        "bodpayterms": "0 DAYS",  # Payment terms
                        "defpw": "W",  # Default pack/whole (W = whole)
                        "itmcode": item['item_code'],
                        "itmname": item['item_name'],
                        "itmpackqty": int(item['pack_size']),  # Pack size (e.g., 1, 50)
                        "itmpartwhole": "W",  # Part/whole (W = whole)
                        "itmprice": float(item['unit_price']),
                        "itmqty": str(quantity_packs),  # Quantity in packs as string
                        "itmtax": "07",  # Tax code
                        "itmlinedisc": 0  # Line discount (numeric)
                    }
                    
                    # Prepare URL with query parameters
                    # For first item: bdocid=0, bdocnumber="" (creates new order)
                    # For subsequent items: use bdocid and bdocnumber from first item's response
                    url_params = {
                        "bdocid": bdocid,
                        "bdocnumber": bdocnumber,
                        "bdocdetid": 0,
                        "dataBaseName": database_name
                    }
                    
                    logger.debug(f"   URL params for item {idx + 1}: bdocid={bdocid}, bdocnumber='{bdocnumber}'")
                    
                    url = f"{self.base_url}/api/BranchOrders/CreateBranchOrder"
                    
                    logger.info(f"📦 Adding item {idx + 1}/{len(batch_items)} to order {batch_idx + 1}: {item['item_code']} (qty: {item['quantity']})")
                    logger.debug(f"   URL params: {url_params}")
                    logger.debug(f"   Payload: {item_payload}")
                    
                    # Make API request (disable SSL verification for self-signed certificates)
                    response = session.post(url, json=item_payload, params=url_params, headers=headers, timeout=30, verify=False)
                    
                    logger.info(f"   Response status: {response.status_code}")
                    logger.info(f"   Request URL params: bdocid={bdocid}, bdocnumber={bdocnumber}")
                    
                    if response.status_code in [200, 201]:
                        try:
                            result = response.json()
                            logger.info(f"   Response JSON: {result}")
                            logger.debug(f"   Full response: {result}")
                            
                            # Extract bdocid and bdocnumber from response
                            # API returns: {'documentId': 18019776, 'docNumber': 'AOD18019776', 'bdocdetid': 584904}
                            # documentId = bdocid, docNumber = bdocnumber
                            extracted_bdocid = result.get('documentId') or result.get('bdocid') or result.get('id') or result.get('orderId') or result.get('docId') or 0
                            extracted_bdocnumber = result.get('docNumber') or result.get('bdocnumber') or result.get('docNumber') or result.get('orderNumber') or result.get('number') or ""
                            
                            # If response is a dict with nested data, try to extract
                            if isinstance(result, dict):
                                # Check for nested structure
                                if 'data' in result:
                                    data = result['data']
                                    extracted_bdocid = data.get('documentId') or data.get('bdocid') or data.get('id') or extracted_bdocid
                                    extracted_bdocnumber = data.get('docNumber') or data.get('bdocnumber') or data.get('docNumber') or extracted_bdocnumber
                            
                            # For first item, use extracted values to create the order
                            if idx == 0:
                                if extracted_bdocid and extracted_bdocnumber:
                                    bdocid = int(extracted_bdocid) if extracted_bdocid else 0
                                    bdocnumber = str(extracted_bdocnumber)
                                    logger.info(f"✅ Branch order {batch_idx + 1} created: ID={bdocid}, Number={bdocnumber}")
                                    all_order_numbers.append(bdocnumber)
                                    if batch_idx == 0:
                                        self.order_doc_number = bdocnumber  # Store first order number
                                    
                                    # Verify order was created by GETting it
                                    try:
                                        logger.info(f"🔍 Verifying order {bdocnumber} (ID: {bdocid})...")
                                        verify_url = f"{self.base_url}/api/BranchOrders/GetBranchOrder"
                                        verify_params = {
                                            "bcode": int(self.branch_code),
                                            "ordernum": bdocid,  # Use numeric bdocid
                                            "dataBaseName": database_name
                                        }
                                        verify_response = session.get(verify_url, params=verify_params, headers=headers, timeout=30, verify=False)
                                        if verify_response.status_code == 200:
                                            verify_data = verify_response.json()
                                            if isinstance(verify_data, list) and len(verify_data) > 0:
                                                # Extract bdocid from line_ID2 if available
                                                first_line = verify_data[0]
                                                verified_bdocid = first_line.get('line_ID2') or bdocid
                                                verified_bdocnumber = first_line.get('hD2_DocNum') or bdocnumber
                                                logger.info(f"✅ Order verified: ID={verified_bdocid}, Number={verified_bdocnumber}")
                                                # Update to use verified values
                                                bdocid = int(verified_bdocid) if verified_bdocid else bdocid
                                                bdocnumber = str(verified_bdocnumber) if verified_bdocnumber else bdocnumber
                                            else:
                                                logger.warning(f"⚠️ Order verification returned empty array")
                                        else:
                                            logger.warning(f"⚠️ Order verification failed: HTTP {verify_response.status_code}")
                                    except Exception as verify_error:
                                        logger.warning(f"⚠️ Could not verify order (non-fatal): {verify_error}")
                                else:
                                    # Try to extract from response text or check if response indicates success
                                    logger.warning(f"⚠️ Order created but documentId/docNumber not in response JSON")
                                    logger.warning(f"   Response type: {type(result)}")
                                    logger.warning(f"   Response keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
                                    logger.warning(f"   Full response: {result}")
                                    logger.warning(f"   Response text (first 500 chars): {response.text[:500] if hasattr(response, 'text') else 'N/A'}")
                                    
                                    # If response is just a success indicator, we might need to check response URL or headers
                                    # But for now, if we don't get order details, we can't continue
                                    if not bdocid or not bdocnumber:
                                        logger.error(f"❌ Cannot continue adding items - no order ID/number from first item response")
                                        logger.error(f"   This means subsequent items cannot be added to the same order")
                                        return {
                                            'success': False,
                                            'message': f'Failed to get order ID/number from first item response. Response: {result}'
                                        }
                            else:
                                # For subsequent items, GET the order first to verify it exists and get correct bdocid
                                try:
                                    logger.info(f"🔍 Getting order details for {bdocnumber} (ID: {bdocid}) before adding item {idx + 1}...")
                                    get_order_url = f"{self.base_url}/api/BranchOrders/GetBranchOrder"
                                    get_order_params = {
                                        "bcode": int(self.branch_code),
                                        "ordernum": bdocid,  # Use numeric bdocid
                                        "dataBaseName": database_name
                                    }
                                    get_order_response = session.get(get_order_url, params=get_order_params, headers=headers, timeout=30, verify=False)
                                    if get_order_response.status_code == 200:
                                        order_data = get_order_response.json()
                                        if isinstance(order_data, list) and len(order_data) > 0:
                                            # Extract bdocid from line_ID2 and docNumber from hD2_DocNum
                                            first_line = order_data[0]
                                            verified_bdocid = first_line.get('line_ID2') or bdocid
                                            verified_bdocnumber = first_line.get('hD2_DocNum') or bdocnumber
                                            logger.info(f"✅ Order retrieved: ID={verified_bdocid}, Number={verified_bdocnumber}, Items in order: {len(order_data)}")
                                            # Update to use verified values
                                            bdocid = int(verified_bdocid) if verified_bdocid else bdocid
                                            bdocnumber = str(verified_bdocnumber) if verified_bdocnumber else bdocnumber
                                        else:
                                            logger.warning(f"⚠️ Order GET returned empty array, using existing bdocid/bdocnumber")
                                    else:
                                        logger.warning(f"⚠️ Order GET failed: HTTP {get_order_response.status_code}, using existing bdocid/bdocnumber")
                                except Exception as get_error:
                                    logger.warning(f"⚠️ Could not GET order before adding item (non-fatal): {get_error}")
                                
                                # Verify we're using the same order
                                if extracted_bdocid and extracted_bdocnumber:
                                    # Verify it matches our current order (should be the same)
                                    if extracted_bdocid != bdocid or extracted_bdocnumber != bdocnumber:
                                        logger.warning(f"⚠️ Response order ID/number differs from expected: got {extracted_bdocid}/{extracted_bdocnumber}, expected {bdocid}/{bdocnumber}")
                                logger.info(f"✅ Item {idx + 1} added to order {bdocnumber}")
                            
                            batch_processed += 1
                            processed_count += 1
                            
                        except ValueError as e:
                            logger.error(f"❌ Failed to parse response JSON: {e}")
                            logger.error(f"   Response text: {response.text[:500]}")
                            return {
                                'success': False,
                                'message': f'Failed to parse API response: {str(e)}'
                            }
                    else:
                        error_text = response.text[:500] if response.text else "No error message"
                        logger.error(f"❌ Failed to add item {idx + 1} to order {batch_idx + 1}: HTTP {response.status_code} - {error_text}")
                        return {
                            'success': False,
                            'message': f'Failed to add item {idx + 1} to branch order {batch_idx + 1}: HTTP {response.status_code} - {error_text}'
                        }
                
                # Batch completed
                logger.info(f"✅ Order {batch_idx + 1} completed: {batch_processed} items added (Order: {bdocnumber})")
            
            # All items processed successfully
            logger.info(f"✅ All branch orders completed: {processed_count} items in {len(item_batches)} order(s)")
            return {
                'success': True,
                'message': f'Branch order(s) created successfully',
                'order_number': all_order_numbers[0] if all_order_numbers else 'N/A',
                'order_numbers': all_order_numbers,  # Return all order numbers
                'processed_count': processed_count,
                'total_orders': len(item_batches)
            }
                
        except Exception as e:
            logger.error(f"❌ Error creating branch order: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'message': f'Error creating branch order: {str(e)}'
            }
    
    def process(self) -> Dict[str, Any]:
        """
        Process order creation
        
        Returns:
            Result dictionary with success status, message, order_number, and processed_count
        """
        # Prepare data
        prepared_df = self.prepare_data()
        
        if prepared_df.empty:
            return {
                'success': False,
                'message': 'No items to process'
            }
        
        # Select items (for auto-selection, this filters; for manual, returns all)
        if not self.manual_selection:
            selected_df = self.select_items(prepared_df)
        else:
            selected_df = prepared_df.copy()
        
        if selected_df.empty:
            return {
                'success': False,
                'message': 'No items selected for ordering'
            }
        
        # Create order based on mode
        if self.order_mode == "purchase_order":
            if not self.supplier_code or not self.supplier_name:
                return {
                    'success': False,
                    'message': 'Supplier code and name are required for purchase orders'
                }
            return self.create_purchase_order(selected_df)
        elif self.order_mode == "branch_order":
            if not self.branch_to_name or not self.branch_to_code:
                return {
                    'success': False,
                    'message': 'Target branch name and code are required for branch orders'
                }
            return self.create_branch_order(selected_df)
        else:
            return {
                'success': False,
                'message': f'Unknown order mode: {self.order_mode}'
            }

