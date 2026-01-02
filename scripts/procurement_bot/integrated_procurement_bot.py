"""
Integrated Procurement Bot
Creates Purchase Orders and Branch Orders via API
"""
import os
import sys
import pandas as pd
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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
            auth_url = f"{base_url}/api/auth/login"
            
            try:
                response = session.post(auth_url, json={
                    'username': username,
                    'password': password
                }, timeout=15)
                
                logger.info(f"🔐 Auth response status: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        token = data.get('access_token') or data.get('token')
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
        Create purchase order via API
        
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
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            
            # Prepare order items
            order_items = []
            for _, row in items_df.iterrows():
                item_code = str(row.get('item_code', '')).strip()
                quantity = float(row.get('order_quantity', 0))
                
                if not item_code or quantity <= 0:
                    continue
                
                order_items.append({
                    "dT_ItemCode": item_code,
                    "dT_Quantity": quantity,
                    "dT_Price": float(row.get('unit_price', 0)),
                    "dT_Total": float(row.get('unit_price', 0)) * quantity
                })
            
            if not order_items:
                return {
                    'success': False,
                    'message': 'No valid items to order'
                }
            
            # Prepare order header
            order_data = {
                "hD2_BranchCode": self.branch_code,
                "hD2_SupplierCode": self.supplier_code or "",
                "hD2_SupplierName": self.supplier_name or "",
                "hD2_Reference": "",
                "hD2_Comments": f"Created via PharmaStock Web App",
                "hD2_Doneby": getattr(self.credential_manager, 'username', 'System'),
                "details": order_items
            }
            
            # Create order via API
            url = f"{self.base_url}/api/PurchaseOrder/CreatePurchaseOrder"
            response = session.post(url, json=order_data, headers=headers, timeout=30)
            
            if response.status_code in [200, 201]:
                result = response.json()
                order_number = result.get('docNumber') or result.get('orderNumber') or 'N/A'
                self.order_doc_number = order_number
                
                logger.info(f"✅ Purchase order created: {order_number}")
                return {
                    'success': True,
                    'message': f'Purchase order created successfully',
                    'order_number': order_number,
                    'processed_count': len(order_items)
                }
            else:
                error_msg = response.text or f"HTTP {response.status_code}"
                logger.error(f"❌ Purchase order creation failed: {error_msg}")
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
            
            # Get target branch code (as string like "BR001")
            target_branch_code_str = None
            if self.branch_to_code:
                if isinstance(self.branch_to_code, str):
                    if self.branch_to_code.startswith('BR'):
                        target_branch_code_str = self.branch_to_code
                    else:
                        # Convert numeric to BR format
                        try:
                            num = int(self.branch_to_code)
                            target_branch_code_str = f"BR{num:03d}"
                        except:
                            target_branch_code_str = self.branch_to_code
                else:
                    # Convert numeric to BR format
                    try:
                        num = int(self.branch_to_code)
                        target_branch_code_str = f"BR{num:03d}"
                    except:
                        target_branch_code_str = str(self.branch_to_code)
            
            if not target_branch_code_str:
                return {
                    'success': False,
                    'message': f'Invalid target branch code: {self.branch_to_code}'
                }
            
            # Get database name based on company
            database_name = self._get_database_name(self.company)
            
            # Get current date in DD/MM/YYYY format
            today = datetime.now()
            date_str = today.strftime("%d/%m/%Y")
            
            # Filter valid items
            valid_items = []
            for _, row in items_df.iterrows():
                item_code = str(row.get('item_code', '')).strip()
                quantity = float(row.get('order_quantity', 0))
                
                if not item_code or quantity <= 0:
                    continue
                
                valid_items.append({
                    'item_code': item_code,
                    'item_name': str(row.get('item_name', '')).strip(),
                    'quantity': quantity,
                    'pack_size': float(row.get('pack_size', 1)),
                    'unit_price': float(row.get('unit_price', 0))
                })
            
            if not valid_items:
                return {
                    'success': False,
                    'message': 'No valid items to order'
                }
            
            # Initialize order document IDs (will be set after first item)
            bdocid = 0
            bdocnumber = ""
            processed_count = 0
            
            # Process items one by one
            for idx, item in enumerate(valid_items):
                # Prepare item payload
                # Note: Quantity should be in packs (already in packs from AMC)
                quantity_packs = int(round(item['quantity']))
                
                item_payload = {
                    "bcode": int(self.branch_code),  # Source branch code (numeric, e.g., 18)
                    "branchToCode": target_branch_code_str,  # Target branch code (e.g., "BR001")
                    "boddate": date_str,  # Order date (DD/MM/YYYY)
                    "boddeldate": date_str,  # Delivery date (DD/MM/YYYY)
                    "bodsuppref": "",  # Supplier reference (empty for branch orders)
                    "bodcomments": "Created via PharmaStock Web App",  # Comments
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
                url_params = {
                    "bdocid": bdocid,
                    "bdocnumber": bdocnumber,
                    "bdocdetid": 0,
                    "dataBaseName": database_name
                }
                
                url = f"{self.base_url}/api/BranchOrders/CreateBranchOrder"
                
                logger.info(f"📦 Adding item {idx + 1}/{len(valid_items)} to branch order: {item['item_code']} (qty: {item['quantity']})")
                logger.debug(f"   URL params: {url_params}")
                logger.debug(f"   Payload: {item_payload}")
                
                # Make API request
                response = session.post(url, json=item_payload, params=url_params, headers=headers, timeout=30)
                
                logger.info(f"   Response status: {response.status_code}")
                
                if response.status_code in [200, 201]:
                    try:
                        result = response.json()
                        logger.debug(f"   Response: {result}")
                        
                        # Extract bdocid and bdocnumber from response (for subsequent items)
                        if idx == 0:
                            # First item - get order ID and number from response
                            # Try multiple possible response formats
                            bdocid = result.get('bdocid') or result.get('id') or result.get('orderId') or result.get('docId') or 0
                            bdocnumber = result.get('bdocnumber') or result.get('docNumber') or result.get('orderNumber') or result.get('number') or ""
                            
                            # If response is a dict with nested data, try to extract
                            if isinstance(result, dict):
                                # Check for nested structure
                                if 'data' in result:
                                    data = result['data']
                                    bdocid = data.get('bdocid') or data.get('id') or bdocid
                                    bdocnumber = data.get('bdocnumber') or data.get('docNumber') or bdocnumber
                            
                            if bdocid and bdocnumber:
                                logger.info(f"✅ Branch order created: ID={bdocid}, Number={bdocnumber}")
                                self.order_doc_number = bdocnumber
                            else:
                                logger.warning(f"⚠️ Order created but bdocid/bdocnumber not in response: {result}")
                                logger.warning(f"   Full response keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
                                # Continue anyway - API might return order details in a different way
                        
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
                    logger.error(f"❌ Failed to add item {idx + 1}: HTTP {response.status_code} - {error_text}")
                    return {
                        'success': False,
                        'message': f'Failed to add item {idx + 1} to branch order: HTTP {response.status_code} - {error_text}'
                    }
            
            # All items processed successfully
            logger.info(f"✅ Branch order completed: {processed_count} items added (Order: {bdocnumber})")
            return {
                'success': True,
                'message': f'Branch order created successfully',
                'order_number': bdocnumber or 'N/A',
                'processed_count': processed_count
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

