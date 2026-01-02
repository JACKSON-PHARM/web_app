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
            token = self.credential_manager.get_valid_token(self.company)
            if not token:
                # Try to get token using credentials
                creds = self.credential_manager.get_credentials(self.company)
                if creds:
                    session = self.get_session()
                    auth_url = f"{self.base_url}/api/auth/login"
                    response = session.post(auth_url, json={
                        'username': creds.get('username'),
                        'password': creds.get('password')
                    }, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        return data.get('access_token') or data.get('token')
            return token
        except Exception as e:
            logger.error(f"Error getting token: {e}")
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
    
    def create_branch_order(self, items_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Create branch order via API
        
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
            
            # Get target branch code
            target_branch_code = None
            if self.branch_to_code:
                # Extract numeric part if needed
                if isinstance(self.branch_to_code, str) and self.branch_to_code.startswith('BR'):
                    try:
                        target_branch_code = int(self.branch_to_code.replace('BR', ''))
                    except:
                        target_branch_code = int(self.branch_to_code) if self.branch_to_code.isdigit() else None
                else:
                    target_branch_code = int(self.branch_to_code) if str(self.branch_to_code).isdigit() else None
            
            if not target_branch_code:
                return {
                    'success': False,
                    'message': f'Invalid target branch code: {self.branch_to_code}'
                }
            
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
                "hD2_SenderBranch": self.branch_code,  # Source branch (where order is coming from)
                "hD2_ReceiverBranch": target_branch_code,  # Target branch (where order is going to)
                "hD2_Reference": "",
                "hD2_Comments": f"Created via PharmaStock Web App - Order to {self.branch_to_name}",
                "hD2_Doneby": getattr(self.credential_manager, 'username', 'System'),
                "details": order_items
            }
            
            # Create order via API
            url = f"{self.base_url}/api/BranchOrders/CreateBranchOrder"
            response = session.post(url, json=order_data, headers=headers, timeout=30)
            
            if response.status_code in [200, 201]:
                result = response.json()
                order_number = result.get('docNumber') or result.get('orderNumber') or 'N/A'
                self.order_doc_number = order_number
                
                logger.info(f"✅ Branch order created: {order_number} (from {self.branch_name} to {self.branch_to_name})")
                return {
                    'success': True,
                    'message': f'Branch order created successfully',
                    'order_number': order_number,
                    'processed_count': len(order_items)
                }
            else:
                error_msg = response.text or f"HTTP {response.status_code}"
                logger.error(f"❌ Branch order creation failed: {error_msg}")
                return {
                    'success': False,
                    'message': f'Failed to create branch order: {error_msg}'
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

