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
        
        # In-memory cache for resolved items: (item_code, branch_code, stock_type) -> item_data
        self._item_cache: Dict[tuple, Dict[str, Any]] = {}
        
        logger.info(f"Initialized procurement bot: mode={order_mode}, branch={branch_name}, items={len(stock_view_df)}")
    
    def prepare_data(self) -> pd.DataFrame:
        """
        Prepare data for ordering
        
        Returns:
            Prepared DataFrame
        """
        df = self.stock_view_df.copy()
        
        # Ensure required columns exist
        # Note: amc is now ideal_stock_pieces (in pieces), need to convert to packs for order quantity
        if 'order_quantity' not in df.columns:
            if 'custom_order_quantity' in df.columns:
                # custom_order_quantity is already in packs (from UI)
                df['order_quantity'] = df['custom_order_quantity'].fillna(1)
            elif 'amc' in df.columns or 'amc_pieces' in df.columns:
                # ideal_stock_pieces is in pieces - convert to packs for order quantity
                amc_pieces = df.get('amc', df.get('amc_pieces', 1))
                pack_size = df.get('pack_size', 1)
                # Convert pieces to packs: order_quantity = amc_pieces / pack_size
                df['order_quantity'] = (pd.to_numeric(amc_pieces, errors='coerce') / 
                                       pd.to_numeric(pack_size, errors='coerce').replace(0, 1)).fillna(1)
            else:
                df['order_quantity'] = 1
        
        # Ensure order_quantity is numeric and in packs
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
            
            # STEP 1: Resolve ALL items from CoreBase API FIRST (before building payload)
            # This ensures we have authoritative metadata (price, tax, pack size)
            resolved_items = {}
            failed_items = []
            
            logger.info(f"🔍 Resolving {len(items_df)} items from CoreBase API...")
            for idx, (_, row) in enumerate(items_df.iterrows(), 1):
                item_code = str(row.get('item_code', '')).strip()
                
                if not item_code:
                    failed_items.append({
                        'item_code': '',
                        'reason': 'Empty item code'
                    })
                    continue
                
                try:
                    # Resolve item from CoreBase API (stock_type=0 for purchase order)
                    item_data = self.resolve_item_from_corebase(
                        item_code=item_code,
                        branch_code=self.branch_code,
                        stock_type=0  # 0 for purchase order
                    )
                    resolved_items[item_code] = item_data
                    logger.debug(f"✅ Resolved item {idx}/{len(items_df)}: {item_code}")
                except ValueError as e:
                    # Item resolution failed (missing, network error after retries, etc.)
                    error_msg = str(e)
                    logger.error(f"❌ Failed to resolve item {item_code}: {error_msg}")
                    failed_items.append({
                        'item_code': item_code,
                        'reason': error_msg
                    })
                except Exception as e:
                    # Unexpected error
                    error_msg = f"Unexpected error: {str(e)}"
                    logger.error(f"❌ Unexpected error resolving item {item_code}: {error_msg}")
                    failed_items.append({
                        'item_code': item_code,
                        'reason': error_msg
                    })
            
            # FAILURE STRATEGY: Stop order creation if ANY item failed
            if failed_items:
                failed_codes = [item['item_code'] for item in failed_items]
                reasons = [f"{item['item_code']}: {item['reason']}" for item in failed_items]
                return {
                    'success': False,
                    'message': f'Failed to resolve {len(failed_items)} item(s) from CoreBase API',
                    'failed_items': failed_items,
                    'failed_item_codes': failed_codes,
                    'failure_reasons': reasons
                }
            
            if not resolved_items:
                return {
                    'success': False,
                    'message': 'No items could be resolved from CoreBase API'
                }
            
            logger.info(f"✅ Successfully resolved {len(resolved_items)} items from CoreBase API")
            
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
            
            # STEP 2: Build order payload using resolved items
            # Quantities come from stock view, metadata comes from CoreBase API
            item_list = []
            total_excl = 0
            now = datetime.now()
            
            for idx, (_, row) in enumerate(items_df.iterrows(), 1):
                item_code = str(row.get('item_code', '')).strip()
                
                if item_code not in resolved_items:
                    # Should not happen if resolution passed, but check anyway
                    logger.error(f"❌ Item {item_code} not in resolved items - skipping")
                    continue
                
                item_data = resolved_items[item_code]
                
                # Extract quantities from stock view (ONLY source for quantities)
                quantity_packs = float(row.get('order_quantity', 0))  # Already in packs from stock view
                amc_pieces = float(row.get('amc', row.get('amc_pieces', 0)))  # From stock view
                
                # Extract metadata from CoreBase API (ONLY source for metadata)
                # Price: use avgCost or lastnitcost
                trade_price = item_data.get('avgCost') or item_data.get('lastnitcost')
                if trade_price is None:
                    raise ValueError(f"Item {item_code} missing price (avgCost/lastnitcost) in CoreBase API response")
                trade_price = self._parse_numeric_value(trade_price, f"price for item {item_code}")
                
                # Pack size: use pkz
                pack_size = item_data.get('pkz')
                if pack_size is None:
                    raise ValueError(f"Item {item_code} missing pack size (pkz) in CoreBase API response")
                pack_size = self._parse_numeric_value(pack_size, f"pkz for item {item_code}")
                
                # Tax information: use API fields
                tax_code = item_data.get('taX_CODE') or item_data.get('tax_CODE') or item_data.get('taxCode')
                if tax_code is None:
                    raise ValueError(f"Item {item_code} missing tax code (taX_CODE/tax_CODE/taxCode) in CoreBase API response")
                tax_code = str(tax_code)
                
                tax_perc = item_data.get('taxPerc') or item_data.get('tax_perc')
                if tax_perc is None:
                    raise ValueError(f"Item {item_code} missing tax percentage (taxPerc/tax_perc) in CoreBase API response")
                tax_perc = self._parse_numeric_value(tax_perc, f"tax percentage for item {item_code}")
                
                # Discount: use API field if available, otherwise 0 (NO DEFAULT)
                discount_raw = item_data.get('discount', 0)
                discount = self._parse_numeric_value(discount_raw, f"discount for item {item_code}") if discount_raw is not None and discount_raw != 0 else 0.0
                
                # Convert quantities using pack size from API
                amc_packs = (amc_pieces / pack_size) if pack_size > 0 else 0
                
                # Ensure quantity is at least 1 (API requires quantity >= 1)
                qty = max(1, int(round(quantity_packs)))
                if quantity_packs < 1:
                    logger.warning(f"⚠️ Item {item_code} has quantity {quantity_packs} < 1, rounding up to 1")
                
                # Calculate totals
                total = qty * trade_price
                total_excl += total
                
                # Create informative comment
                comment = (
                    f"Auto-Order | Ideal Stock: {amc_pieces:.0f} pieces ({amc_packs:.1f} packs) | "
                    f"Stock: {row.get('branch_stock', 0)} pieces | Class: {row.get('abc_class', 'N/A')}"
                )
                
                item_list.append({
                    "itemCode": item_code,
                    "itemName": str(row.get('item_name', item_data.get('itemName', 'Unknown'))).strip(),
                    "saleQty": f"{qty}W0P",
                    "avgSale": f"{amc_packs:.1f}W0P",  # AMC in packs for API
                    "reqQty": f"{qty}W0P",
                    "inStore": "0W0P",
                    "var": f"{qty}W0P",
                    "ordQty": f"{qty}W0P",
                    "getsel": 1,
                    "lastPrice": trade_price,
                    "suppCode": self.supplier_code,
                    "suppName": self.supplier_name,
                    "packqty": int(pack_size),  # From API
                    "ordQtyValue": float(qty),
                    "tradeprice": trade_price,  # From API
                    "comments": comment,
                    "tableData": {"id": idx},
                    "dT_Vat": tax_code,  # From API
                    "dT_Disc": discount,  # From API (0 if not provided)
                    "dT_Bonus": 0.0,
                    "dT_Unit": 1.0,
                    "dT_PW": "W",
                    "dT_Total": total,
                    "dT_Nett": total * (1 - discount)
                })
            
            if not item_list:
                return {
                    'success': False,
                    'message': 'No valid items to order'
                }
            
            # Calculate totals (using discounts from API, not defaults)
            total_discount = sum((item['dT_Total'] * item['dT_Disc']) for item in item_list)
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
    
    def _parse_numeric_value(self, value: Any, field_name: str = "value") -> float:
        """
        Parse numeric value from API response.
        Handles both numeric values and formatted strings like "456W0P" (pack/whole format).
        
        Format: "XWYP" where:
        - X = whole packs/units
        - W = literal "W"
        - Y = pieces (partial)
        - P = literal "P"
        
        Args:
            value: Value to parse (can be numeric, string, or formatted string)
            field_name: Field name for error messages
            
        Returns:
            Float value
            
        Raises:
            ValueError: If value cannot be parsed
        """
        if value is None:
            raise ValueError(f"Value is None for field {field_name}")
        
        # If already numeric, return as float
        if isinstance(value, (int, float)):
            return float(value)
        
        # If string, check if it's in "XWYP" format
        if isinstance(value, str):
            value = value.strip()
            
            # Try to parse "XWYP" format (e.g., "456W0P", "0W0P")
            if 'W' in value and value.endswith('P'):
                try:
                    # Extract the number before "W"
                    parts = value.split('W')
                    if len(parts) >= 1:
                        whole_part = parts[0]
                        # Extract numeric part (might have leading/trailing spaces)
                        numeric_str = ''.join(c for c in whole_part if c.isdigit() or c == '.' or c == '-')
                        if numeric_str:
                            return float(numeric_str)
                except (ValueError, IndexError):
                    pass
            
            # Try direct float conversion
            try:
                return float(value)
            except ValueError:
                raise ValueError(f"Cannot parse {field_name} value '{value}' as numeric (expected number or 'XWYP' format)")
        
        # Try to convert to float directly
        try:
            return float(value)
        except (ValueError, TypeError):
            raise ValueError(f"Cannot parse {field_name} value '{value}' (type: {type(value).__name__}) as numeric")
    
    def resolve_item_from_corebase(
        self,
        *,
        item_code: str,
        branch_code: int,
        stock_type: int,
    ) -> Dict[str, Any]:
        """
        Resolve item metadata from CoreBase API using GetExistingStock endpoint.
        
        This is the AUTHORITATIVE source for all item metadata:
        - Price (avgCost, lastnitcost)
        - Pack size (pkz)
        - Tax information (taX_CODE, taxPerc, taxType, inclusive)
        - All other item flags and metadata
        
        CRITICAL: Stock View provides QUANTITIES ONLY. This API provides ALL metadata.
        
        Args:
            item_code: Item code (exact match, no fuzzy)
            branch_code: Branch code (numeric)
            stock_type: Stock type (1 for branch order, 0 for purchase order)
            
        Returns:
            Dictionary with item metadata from CoreBase API
            
        Raises:
            ValueError: If item not found, multiple items returned, or API error after retries
            requests.exceptions.RequestException: If network error persists after retries
        """
        import time
        
        # Check cache first
        cache_key = (item_code, branch_code, stock_type)
        if cache_key in self._item_cache:
            logger.debug(f"✅ Item {item_code} (bcode={branch_code}, stockType={stock_type}) found in cache")
            return self._item_cache[cache_key]
        
        token = self.get_token()
        if not token:
            raise ValueError(f"Failed to get authentication token for item {item_code}")
        
        session = self.get_session()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        database_name = self._get_database_name(self.company)
        url = f"{self.base_url}/api/BranchOrders/GetExistingStock"
        
        params = {
            "itemName": item_code,  # Exact match, no fuzzy
            "bcode": branch_code,
            "stockType": stock_type,  # 1 for branch order, 0 for purchase order
            "dataBaseName": database_name
        }
        
        # Retry logic with exponential backoff
        max_retries = 3
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"🔍 Resolving item {item_code} (attempt {attempt + 1}/{max_retries})...")
                response = session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=30,
                    verify=False
                )
                
                # Handle HTTP errors
                if response.status_code >= 500:
                    # Server error - retry
                    error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.warning(f"⚠️ Server error resolving item {item_code} (attempt {attempt + 1}): {error_msg}")
                    if attempt < max_retries - 1:
                        backoff_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                        logger.info(f"⏳ Retrying in {backoff_time}s...")
                        time.sleep(backoff_time)
                        continue
                    else:
                        raise ValueError(f"Server error after {max_retries} attempts: {error_msg}")
                
                if response.status_code == 404:
                    # Item not found - don't retry, this is a real missing item
                    raise ValueError(f"Item {item_code} not found in CoreBase API (HTTP 404)")
                
                if response.status_code not in [200, 201]:
                    # Other HTTP errors - retry
                    error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.warning(f"⚠️ HTTP error resolving item {item_code} (attempt {attempt + 1}): {error_msg}")
                    if attempt < max_retries - 1:
                        backoff_time = 2 ** attempt
                        logger.info(f"⏳ Retrying in {backoff_time}s...")
                        time.sleep(backoff_time)
                        continue
                    else:
                        raise ValueError(f"HTTP error after {max_retries} attempts: {error_msg}")
                
                # Parse response
                try:
                    data = response.json()
                except ValueError as e:
                    error_msg = f"Invalid JSON response: {response.text[:200]}"
                    logger.error(f"❌ {error_msg}")
                    if attempt < max_retries - 1:
                        backoff_time = 2 ** attempt
                        time.sleep(backoff_time)
                        continue
                    else:
                        raise ValueError(error_msg)
                
                # Validate response
                if not data:
                    # Empty response after retries - item truly missing
                    raise ValueError(f"Item {item_code} not found: empty response from CoreBase API")
                
                # Handle list response
                if isinstance(data, list):
                    if len(data) == 0:
                        raise ValueError(f"Item {item_code} not found: empty list from CoreBase API")
                    elif len(data) > 1:
                        raise ValueError(f"Item {item_code} returned multiple items ({len(data)}): conflict in CoreBase API")
                    # Single item in list - extract it
                    item_data = data[0]
                elif isinstance(data, dict):
                    item_data = data
                else:
                    raise ValueError(f"Unexpected response type for item {item_code}: {type(data)}")
                
                # Validate item_data is a dict
                if not isinstance(item_data, dict):
                    raise ValueError(f"Item {item_code} response is not a dictionary: {type(item_data)}")
                
                # Cache the result
                self._item_cache[cache_key] = item_data
                logger.debug(f"✅ Resolved item {item_code}: cached for reuse")
                
                return item_data
                
            except requests.exceptions.Timeout as e:
                last_exception = e
                logger.warning(f"⚠️ Timeout resolving item {item_code} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    backoff_time = 2 ** attempt
                    logger.info(f"⏳ Retrying in {backoff_time}s...")
                    time.sleep(backoff_time)
                    continue
                    
            except requests.exceptions.ConnectionError as e:
                last_exception = e
                logger.warning(f"⚠️ Connection error resolving item {item_code} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    backoff_time = 2 ** attempt
                    logger.info(f"⏳ Retrying in {backoff_time}s...")
                    time.sleep(backoff_time)
                    continue
                    
            except ValueError:
                # Don't retry ValueError - these are business logic errors (missing item, etc.)
                raise
                
            except Exception as e:
                last_exception = e
                logger.warning(f"⚠️ Error resolving item {item_code} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    backoff_time = 2 ** attempt
                    logger.info(f"⏳ Retrying in {backoff_time}s...")
                    time.sleep(backoff_time)
                    continue
        
        # All retries exhausted
        if last_exception:
            raise ValueError(f"Failed to resolve item {item_code} after {max_retries} attempts: {last_exception}")
        else:
            raise ValueError(f"Failed to resolve item {item_code} after {max_retries} attempts: unknown error")
    
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
            
            # Get source branch code as numeric for API calls
            source_branch_code_numeric = None
            if self.branch_to_code:
                if isinstance(self.branch_to_code, str) and self.branch_to_code.startswith('BR'):
                    try:
                        source_branch_code_numeric = int(self.branch_to_code.replace('BR', ''))
                    except:
                        pass
                elif isinstance(self.branch_to_code, (int, str)):
                    try:
                        source_branch_code_numeric = int(self.branch_to_code)
                    except:
                        pass
            
            if not source_branch_code_numeric:
                return {
                    'success': False,
                    'message': f'Invalid source branch code: {self.branch_to_code} (cannot determine numeric code)'
                }
            
            # STEP 1: Resolve ALL items from CoreBase API FIRST (before processing)
            # This ensures we have authoritative metadata (price, tax, pack size, stock)
            resolved_items = {}
            failed_items = []
            
            logger.info(f"🔍 Resolving {len(items_df)} items from CoreBase API for branch order...")
            for idx, (_, row) in enumerate(items_df.iterrows(), 1):
                item_code = str(row.get('item_code', '')).strip()
                requested_quantity_packs = float(row.get('order_quantity', 0))
                
                if not item_code:
                    failed_items.append({
                        'item_code': '',
                        'reason': 'Empty item code'
                    })
                    continue
                
                if requested_quantity_packs <= 0:
                    failed_items.append({
                        'item_code': item_code,
                        'reason': f'Invalid quantity: {requested_quantity_packs}'
                    })
                    continue
                
                try:
                    # Resolve item from CoreBase API (stock_type=1 for branch order)
                    # Use SOURCE branch code (where stock comes FROM)
                    item_data = self.resolve_item_from_corebase(
                        item_code=item_code,
                        branch_code=source_branch_code_numeric,  # Source branch (where stock comes FROM)
                        stock_type=1  # 1 for branch order
                    )
                    
                    # Validate stock availability
                    # Get pack size first (needed for stock conversion)
                    pack_size = item_data.get('pkz')
                    if pack_size is None:
                        raise ValueError(f"Item {item_code} missing pack size (pkz) in CoreBase API response")
                    pack_size = self._parse_numeric_value(pack_size, f"pkz for item {item_code}")
                    
                    # Get stock value (might be in "XWYP" format or numeric)
                    total_stock_raw = item_data.get('totalStockUnits') or item_data.get('totalStock') or item_data.get('stock') or item_data.get('calcQty')
                    if total_stock_raw is None:
                        raise ValueError(f"Item {item_code} missing stock information (totalStockUnits/totalStock/stock/calcQty) in CoreBase API response")
                    
                    # Parse stock value (handles "XWYP" format)
                    total_stock_value = self._parse_numeric_value(total_stock_raw, f"stock for item {item_code}")
                    
                    # If stock is in packs (from "XWYP" format), convert to units
                    # Note: API might return stock in pieces already, so we check the format
                    # If it was in "XWYP" format, it's likely in packs, so convert to units
                    if isinstance(total_stock_raw, str) and 'W' in total_stock_raw and total_stock_raw.endswith('P'):
                        # Value is in packs, convert to units (pieces)
                        total_stock_units = total_stock_value * pack_size
                    else:
                        # Value is already in units (pieces)
                        total_stock_units = total_stock_value
                    
                    # Convert requested quantity to units
                    requested_units = requested_quantity_packs * pack_size
                    
                    # Validate stock availability
                    if total_stock_units < requested_units:
                        raise ValueError(f"Item {item_code} insufficient stock: requested {requested_units} units ({requested_quantity_packs} packs), available {total_stock_units} units")
                    
                    resolved_items[item_code] = item_data
                    logger.debug(f"✅ Resolved item {idx}/{len(items_df)}: {item_code} (stock: {total_stock_units} units, requested: {requested_units} units)")
                except ValueError as e:
                    # Item resolution or validation failed
                    error_msg = str(e)
                    logger.error(f"❌ Failed to resolve/validate item {item_code}: {error_msg}")
                    failed_items.append({
                        'item_code': item_code,
                        'reason': error_msg
                    })
                except Exception as e:
                    # Unexpected error
                    error_msg = f"Unexpected error: {str(e)}"
                    logger.error(f"❌ Unexpected error resolving item {item_code}: {error_msg}")
                    failed_items.append({
                        'item_code': item_code,
                        'reason': error_msg
                    })
            
            # FAILURE STRATEGY: Stop order creation if ANY item failed
            if failed_items:
                failed_codes = [item['item_code'] for item in failed_items]
                reasons = [f"{item['item_code']}: {item['reason']}" for item in failed_items]
                return {
                    'success': False,
                    'message': f'Failed to resolve/validate {len(failed_items)} item(s) from CoreBase API',
                    'failed_items': failed_items,
                    'failed_item_codes': failed_codes,
                    'failure_reasons': reasons
                }
            
            if not resolved_items:
                return {
                    'success': False,
                    'message': 'No items could be resolved from CoreBase API'
                }
            
            logger.info(f"✅ Successfully resolved {len(resolved_items)} items from CoreBase API")
            
            # STEP 2: Build valid items list using resolved data
            valid_items = []
            for _, row in items_df.iterrows():
                item_code = str(row.get('item_code', '')).strip()
                
                if item_code not in resolved_items:
                    # Should not happen if resolution passed, but check anyway
                    logger.error(f"❌ Item {item_code} not in resolved items - skipping")
                    continue
                
                item_data = resolved_items[item_code]
                quantity_packs = float(row.get('order_quantity', 0))
                
                # Extract metadata from CoreBase API
                # Price: use retailUnit
                retail_unit_price = item_data.get('retailUnit') or item_data.get('retail_unit')
                if retail_unit_price is None:
                    raise ValueError(f"Item {item_code} missing price (retailUnit/retail_unit) in CoreBase API response")
                retail_unit_price = self._parse_numeric_value(retail_unit_price, f"price for item {item_code}")
                
                # Pack size: use pkz
                pack_size = item_data.get('pkz')
                if pack_size is None:
                    raise ValueError(f"Item {item_code} missing pack size (pkz) in CoreBase API response")
                pack_size = self._parse_numeric_value(pack_size, f"pkz for item {item_code}")
                
                # Tax code: use API field
                tax_code = item_data.get('taX_CODE') or item_data.get('tax_CODE') or item_data.get('taxCode')
                if tax_code is None:
                    raise ValueError(f"Item {item_code} missing tax code (taX_CODE/tax_CODE/taxCode) in CoreBase API response")
                tax_code = str(tax_code)
                
                valid_items.append({
                    'item_code': item_code,
                    'item_name': str(row.get('item_name', item_data.get('itemName', 'Unknown'))).strip(),
                    'quantity': quantity_packs,
                    'pack_size': pack_size,  # From API
                    'unit_price': retail_unit_price,  # From API
                    'tax_code': tax_code  # From API
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
                        "itmpackqty": int(item['pack_size']),  # Pack size from API (pkz)
                        "itmpartwhole": "W",  # Part/whole (W = whole)
                        "itmprice": float(item['unit_price']),  # Price from API (retailUnit)
                        "itmqty": str(quantity_packs),  # Quantity in packs as string
                        "itmtax": item['tax_code'],  # Tax code from API
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

