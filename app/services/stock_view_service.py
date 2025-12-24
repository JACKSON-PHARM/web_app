"""
Stock View Service
Handles data queries and joins for stock view table
"""
import sqlite3
import pandas as pd
import logging
import os
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class StockViewService:
    """Service for querying stock view data with joins and lookups"""
    
    def __init__(self, db_path: str, app_root: str = None):
        self.db_path = db_path
        # For web app, use web_app root; for desktop, use provided app_root
        if app_root and os.path.exists(app_root):
            self.app_root = app_root
        else:
            # Try to find web_app root or parent root
            current_file = os.path.abspath(__file__)
            # web_app/app/services/stock_view_service.py -> web_app/
            web_app_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
            # Check if parent directory exists (for desktop app)
            parent_root = os.path.dirname(web_app_root)
            if os.path.exists(os.path.join(parent_root, "ui")) and os.path.exists(os.path.join(parent_root, "resources")):
                self.app_root = parent_root  # Desktop app context
            else:
                self.app_root = web_app_root  # Web app context
        
        self.inventory_analysis_path = os.path.join(self.app_root, "resources", "templates", "Inventory_Analysis.csv")
        # Also check for Excel file as fallback/primary source
        self.stock_view_excel_path = os.path.join(self.app_root, "resources", "templates", "stock_view_20251129_151405.xlsx")
        self._inventory_analysis_cache = None
        
        # Log initialization for debugging
        logger.info(f"StockViewService initialized:")
        logger.info(f"  - Database path: {self.db_path}")
        logger.info(f"  - Database exists: {os.path.exists(self.db_path)}")
        if os.path.exists(self.db_path):
            logger.info(f"  - Database size: {os.path.getsize(self.db_path) / (1024*1024):.2f} MB")
        logger.info(f"  - App root: {self.app_root}")
        logger.info(f"  - CSV path: {self.inventory_analysis_path} (exists: {os.path.exists(self.inventory_analysis_path)})")
        logger.info(f"  - Excel path: {self.stock_view_excel_path} (exists: {os.path.exists(self.stock_view_excel_path)})")
    
    def load_inventory_analysis(self) -> pd.DataFrame:
        """Load ABC class, AMC, and other analysis data from Inventory_Analysis.csv or stock_view Excel file"""
        if self._inventory_analysis_cache is not None:
            return self._inventory_analysis_cache
        
        try:
            # 1) Try CSV first (Inventory_Analysis.csv)
            if os.path.exists(self.inventory_analysis_path):
                try:
                    df = pd.read_csv(self.inventory_analysis_path)
                    # Cache it
                    self._inventory_analysis_cache = df
                    logger.info(f"Loaded {len(df)} items from Inventory_Analysis.csv")
                    return df
                except Exception as ex:
                    logger.warning(f"Failed to load CSV: {ex}")
            
            # 2) Fallback: Try Excel file (stock_view_20251129_151405.xlsx)
            if os.path.exists(self.stock_view_excel_path):
                try:
                    logger.info(f"Loading inventory analysis from Excel: {self.stock_view_excel_path}")
                    df = pd.read_excel(self.stock_view_excel_path)
                    logger.info(f"Excel file has {len(df)} rows and {len(df.columns)} columns")
                    logger.info(f"Columns: {list(df.columns)}")
                    
                    # Normalize column names (case-insensitive)
                    cols = {c.lower(): c for c in df.columns}
                    
                    # Map common column names
                    column_mapping = {}
                    if 'item_code' in cols or 'itemcode' in cols or 'item' in cols:
                        code_col = cols.get('item_code') or cols.get('itemcode') or cols.get('item')
                        column_mapping[code_col] = 'item_code'
                    
                    # Try to find ABC class column
                    if 'abc_class' in cols or 'abc' in cols or 'class' in cols:
                        abc_col = cols.get('abc_class') or cols.get('abc') or cols.get('class')
                        column_mapping[abc_col] = 'abc_class'
                    
                    # Try to find AMC columns
                    if 'adjusted_amc' in cols:
                        column_mapping[cols['adjusted_amc']] = 'adjusted_amc'
                    elif 'base_amc' in cols or 'amc' in cols:
                        amc_col = cols.get('base_amc') or cols.get('amc')
                        column_mapping[amc_col] = 'base_amc'
                    
                    # Try to find ideal_stock_pieces
                    if 'ideal_stock_pieces' in cols or 'ideal_stock' in cols:
                        ideal_col = cols.get('ideal_stock_pieces') or cols.get('ideal_stock')
                        column_mapping[ideal_col] = 'ideal_stock_pieces'
                    
                    # Try to find customer_appeal
                    if 'customer_appeal' in cols:
                        column_mapping[cols['customer_appeal']] = 'customer_appeal'
                    
                    # Try to find stock_recommendation
                    if 'stock_recommendation' in cols or 'stock_comment' in cols:
                        rec_col = cols.get('stock_recommendation') or cols.get('stock_comment')
                        column_mapping[rec_col] = 'stock_recommendation'
                    
                    # Rename columns
                    if column_mapping:
                        df = df.rename(columns=column_mapping)
                    
                    # Cache it
                    self._inventory_analysis_cache = df
                    logger.info(f"Loaded {len(df)} items from Excel file")
                    return df
                except Exception as ex:
                    logger.error(f"Error loading Excel file: {ex}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            logger.warning(f"Inventory analysis files not found. CSV: {self.inventory_analysis_path}, Excel: {self.stock_view_excel_path}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error loading inventory analysis: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return pd.DataFrame()
    
    def get_stock_view_data(self, branch_name: str, branch_company: str, 
                           source_branch_name: str, source_branch_company: str) -> pd.DataFrame:
        """
        Get stock view data with all joins and lookups
        
        Args:
            branch_name: Name of the branch to view stock for
            branch_company: Company of the branch
            source_branch_name: Name of the source/supplier branch
            source_branch_company: Company of the source branch
        
        Returns:
            DataFrame with all stock view columns
        """
        try:
            # Trim and normalize branch/company names to handle whitespace and case issues
            branch_name = branch_name.strip() if branch_name else ""
            branch_company = branch_company.strip() if branch_company else ""
            source_branch_name = source_branch_name.strip() if source_branch_name else ""
            source_branch_company = source_branch_company.strip() if source_branch_company else ""
            
            logger.info(f"Querying stock view - Branch: '{branch_name}' ({branch_company}), Source: '{source_branch_name}' ({source_branch_company})")
            
            # Log database connection attempt
            logger.info(f"Connecting to database: {self.db_path}")
            logger.info(f"Database file exists: {os.path.exists(self.db_path)}")
            if os.path.exists(self.db_path):
                logger.info(f"Database file size: {os.path.getsize(self.db_path) / (1024*1024):.2f} MB")
            
            conn = sqlite3.connect(self.db_path, timeout=5, check_same_thread=False)
            cursor = conn.cursor()
            
            # First, check if current_stock table exists and has data
            try:
                cursor.execute("SELECT COUNT(*) FROM current_stock")
                current_stock_count = cursor.fetchone()[0]
                logger.info(f"current_stock table has {current_stock_count} records")
                
                # Check if there's data for the selected branch (case-insensitive)
                cursor.execute("SELECT COUNT(*) FROM current_stock WHERE UPPER(TRIM(branch)) = UPPER(TRIM(?)) AND UPPER(TRIM(company)) = UPPER(TRIM(?))", 
                            (branch_name, branch_company))
                branch_stock_count = cursor.fetchone()[0]
                logger.info(f"Found {branch_stock_count} records for branch '{branch_name}' ({branch_company}) [case-insensitive match]")
                
                # Check available branches
                cursor.execute("SELECT DISTINCT branch, company, COUNT(*) as count FROM current_stock GROUP BY UPPER(TRIM(branch)), UPPER(TRIM(company)) ORDER BY count DESC LIMIT 20")
                available_branches = cursor.fetchall()
                logger.info(f"Available branches in database (with counts): {available_branches}")
                
                # If no exact match, try to find similar branch names
                if branch_stock_count == 0:
                    cursor.execute("SELECT DISTINCT branch, company, COUNT(*) as count FROM current_stock WHERE UPPER(TRIM(company)) = UPPER(TRIM(?)) GROUP BY branch, company ORDER BY count DESC LIMIT 10", (branch_company,))
                    similar_branches = cursor.fetchall()
                    if similar_branches:
                        logger.warning(f"No exact match for '{branch_name}', but found {len(similar_branches)} branches for company '{branch_company}': {similar_branches}")
                
                # Also check sales and stock_data tables
                try:
                    cursor.execute("SELECT COUNT(*) FROM sales WHERE company = ?", (branch_company,))
                    sales_count = cursor.fetchone()[0]
                    logger.info(f"sales table has {sales_count} records for company '{branch_company}'")
                except:
                    logger.warning("sales table not found or error accessing it")
                
                try:
                    cursor.execute("SELECT COUNT(*) FROM stock_data WHERE company_name = ?", (branch_company,))
                    stock_data_count = cursor.fetchone()[0]
                    logger.info(f"stock_data table has {stock_data_count} records for company '{branch_company}'")
                except:
                    logger.warning("stock_data table not found or error accessing it")
                
            except sqlite3.OperationalError as e:
                logger.error(f"Error checking current_stock table: {e}")
                import traceback
                logger.error(traceback.format_exc())
                current_stock_count = 0
                branch_stock_count = 0
            
            # Use desktop version's CTE-based query (simpler and more reliable)
            # Start with current_stock for the branch to ensure stock values are present
            query = """
            WITH branch_stock AS (
                SELECT 
                    item_code,
                    item_name,
                    stock_pieces as branch_stock,
                    pack_size,
                    unit_price,
                    stock_value
                FROM current_stock
                WHERE UPPER(TRIM(branch)) = UPPER(TRIM(?)) AND UPPER(TRIM(company)) = UPPER(TRIM(?))
            ),
            all_items AS (
                SELECT DISTINCT 
                    item_code,
                    MAX(item_name) as item_name
                FROM (
                    SELECT item_code, item_name FROM branch_stock
                    UNION
                    SELECT item_code, item_name FROM sales WHERE UPPER(TRIM(company)) = UPPER(TRIM(?))
                    UNION
                    SELECT item_code, item_name FROM stock_data WHERE UPPER(TRIM(company_name)) = UPPER(TRIM(?))
                )
                GROUP BY item_code
            ),
            source_stock AS (
                SELECT 
                    item_code,
                    stock_pieces as supplier_stock
                FROM current_stock
                WHERE UPPER(TRIM(branch)) = UPPER(TRIM(?)) AND UPPER(TRIM(company)) = UPPER(TRIM(?))
            ),
            -- Combined orders: Purchase orders + Branch orders + HQ Invoices
            combined_orders AS (
                -- Purchase orders
                SELECT 
                    item_code,
                    document_date,
                    document_number,
                    quantity,
                    company,
                    'PURCHASE' as order_type
                FROM purchase_orders
                WHERE UPPER(TRIM(branch)) = UPPER(TRIM(?)) AND UPPER(TRIM(company)) = UPPER(TRIM(?))
                
                UNION ALL
                
                -- Branch orders (where source_branch matches target branch - the branch that raised the order)
                SELECT 
                    item_code,
                    document_date,
                    document_number,
                    quantity,
                    company,
                    'BRANCH' as order_type
                FROM branch_orders
                WHERE UPPER(TRIM(source_branch)) = UPPER(TRIM(?)) AND UPPER(TRIM(company)) = UPPER(TRIM(?))
                
                UNION ALL
                
                -- HQ Invoices (from BABA DOGO HQ to this branch)
                SELECT 
                    item_code,
                    date as document_date,
                    invoice_number as document_number,
                    quantity,
                    'NILA' as company,  -- Default company for hq_invoices
                    'HQ_INVOICE' as order_type
                FROM hq_invoices
                WHERE UPPER(TRIM(branch)) = UPPER(TRIM(?))
            ),
            last_order AS (
                SELECT 
                    item_code,
                    MAX(document_date) as last_order_date
                FROM combined_orders
                GROUP BY item_code
            ),
            last_order_details AS (
                SELECT 
                    co.item_code,
                    co.document_number as last_order_doc,
                    SUM(co.quantity) as last_order_quantity
                FROM combined_orders co
                INNER JOIN last_order lo ON co.item_code = lo.item_code AND co.document_date = lo.last_order_date
                GROUP BY co.item_code, co.document_number
            ),
            last_supply AS (
                SELECT 
                    item_code,
                    MAX(document_date) as last_supply_date,
                    MAX(document_number) as last_supply_doc,
                    SUM(CASE WHEN document_date = (SELECT MAX(document_date) 
                                                   FROM supplier_invoices si2 
                                                   WHERE si2.item_code = supplier_invoices.item_code 
                                                   AND UPPER(TRIM(si2.branch)) = UPPER(TRIM(supplier_invoices.branch))
                                                   AND UPPER(TRIM(si2.company)) = UPPER(TRIM(supplier_invoices.company))
                                                   )
                             THEN units ELSE 0 END) as last_supply_quantity
                FROM supplier_invoices
                WHERE UPPER(TRIM(branch)) = UPPER(TRIM(?)) AND UPPER(TRIM(company)) = UPPER(TRIM(?))
                GROUP BY item_code
            ),
            last_hq_invoice AS (
                SELECT 
                    item_code,
                    MAX(date) as last_invoice_date,
                    MAX(invoice_number) as last_invoice_doc,
                    SUM(CASE WHEN date = (SELECT MAX(date) 
                                         FROM hq_invoices hi2 
                                         WHERE hi2.item_code = hq_invoices.item_code 
                                         AND UPPER(TRIM(hi2.branch)) = UPPER(TRIM(hq_invoices.branch))
                                         )
                                 THEN quantity ELSE 0 END) as last_invoice_quantity
                FROM hq_invoices
                WHERE UPPER(TRIM(branch)) = UPPER(TRIM(?))
                GROUP BY item_code
            ),
            last_grn AS (
                SELECT 
                    item_code,
                    MAX(document_date) as last_grn_date,
                    MAX(document_number) as last_grn_doc,
                    SUM(CASE WHEN document_date = (SELECT MAX(document_date) 
                                                   FROM goods_received_notes grn2 
                                                   WHERE grn2.item_code = goods_received_notes.item_code 
                                                   AND UPPER(TRIM(grn2.branch)) = UPPER(TRIM(goods_received_notes.branch))
                                                   AND UPPER(TRIM(grn2.company)) = UPPER(TRIM(goods_received_notes.company))
                                                   )
                             THEN quantity ELSE 0 END) as last_grn_quantity
                FROM goods_received_notes
                WHERE UPPER(TRIM(branch)) = UPPER(TRIM(?)) AND UPPER(TRIM(company)) = UPPER(TRIM(?))
                GROUP BY item_code
            ),
            hq_stock_data AS (
                SELECT 
                    item_code,
                    stock_pieces as hq_stock
                FROM current_stock
                WHERE UPPER(TRIM(branch)) = UPPER(TRIM('BABA DOGO HQ')) AND UPPER(TRIM(company)) = UPPER(TRIM(?))
            )
            SELECT 
                ai.item_code,
                ai.item_name,
                COALESCE(ss.supplier_stock, 0) as supplier_stock,
                COALESCE(bs.branch_stock, 0) as branch_stock,
                COALESCE(bs.pack_size, 1) as pack_size,
                COALESCE(bs.unit_price, 0) as unit_price,
                COALESCE(bs.stock_value, 0) as stock_value,
                lo.last_order_date,
                lod.last_order_doc,
                lod.last_order_quantity,
                hi.last_invoice_date,
                hi.last_invoice_doc,
                hi.last_invoice_quantity,
                ls.last_supply_date,
                ls.last_supply_doc,
                ls.last_supply_quantity,
                lg.last_grn_date,
                lg.last_grn_doc,
                lg.last_grn_quantity,
                hq.hq_stock
            FROM all_items ai
            LEFT JOIN branch_stock bs ON ai.item_code = bs.item_code
            LEFT JOIN source_stock ss ON ai.item_code = ss.item_code
            LEFT JOIN last_order lo ON ai.item_code = lo.item_code
            LEFT JOIN last_order_details lod ON ai.item_code = lod.item_code
            LEFT JOIN last_supply ls ON ai.item_code = ls.item_code
            LEFT JOIN last_hq_invoice hi ON ai.item_code = hi.item_code
            LEFT JOIN last_grn lg ON ai.item_code = lg.item_code
            LEFT JOIN hq_stock_data hq ON ai.item_code = hq.item_code
            ORDER BY ai.item_code
            LIMIT 1000
            """
            
            # Parameters for CTE query
            params = (
                branch_name, branch_company,  # branch_stock (first CTE)
                branch_company,  # all_items - sales
                branch_company,  # all_items - stock_data
                source_branch_name, source_branch_company,  # source_stock
                branch_name, branch_company,  # combined_orders - purchase_orders WHERE
                branch_name, branch_company,  # combined_orders - branch_orders WHERE
                branch_name,  # combined_orders - hq_invoices WHERE (no company column)
                branch_name, branch_company,  # last_supply (main WHERE)
                branch_name,  # last_hq_invoice (main WHERE - no company column)
                branch_name, branch_company,  # last_grn (main WHERE)
                branch_company  # hq_stock_data
            )
            
            logger.info(f"Executing query with params: branch={branch_name}, company={branch_company}")
            logger.info(f"Full params list: {params}")
            
            # Check if data exists in the tables before running the query
            try:
                cursor.execute("SELECT COUNT(*) FROM purchase_orders WHERE UPPER(TRIM(branch)) = UPPER(TRIM(?)) AND UPPER(TRIM(company)) = UPPER(TRIM(?))", 
                             (branch_name, branch_company))
                po_count = cursor.fetchone()[0]
                logger.info(f"📦 Purchase orders for '{branch_name}' ({branch_company}): {po_count} records")
                
                cursor.execute("SELECT COUNT(*) FROM branch_orders WHERE UPPER(TRIM(source_branch)) = UPPER(TRIM(?)) AND UPPER(TRIM(company)) = UPPER(TRIM(?))", 
                             (branch_name, branch_company))
                bo_count = cursor.fetchone()[0]
                logger.info(f"📦 Branch orders for '{branch_name}' ({branch_company}): {bo_count} records")
                
                cursor.execute("SELECT COUNT(*) FROM supplier_invoices WHERE UPPER(TRIM(branch)) = UPPER(TRIM(?)) AND UPPER(TRIM(company)) = UPPER(TRIM(?))", 
                             (branch_name, branch_company))
                si_count = cursor.fetchone()[0]
                logger.info(f"📦 Supplier invoices for '{branch_name}' ({branch_company}): {si_count} records")
                
                cursor.execute("SELECT COUNT(*) FROM hq_invoices WHERE UPPER(TRIM(branch)) = UPPER(TRIM(?))", 
                             (branch_name,))
                hi_count = cursor.fetchone()[0]
                logger.info(f"📦 HQ invoices for '{branch_name}' ({branch_company}): {hi_count} records")
                
                cursor.execute("SELECT COUNT(*) FROM goods_received_notes WHERE UPPER(TRIM(branch)) = UPPER(TRIM(?)) AND UPPER(TRIM(company)) = UPPER(TRIM(?))", 
                             (branch_name, branch_company))
                grn_count = cursor.fetchone()[0]
                logger.info(f"📦 GRN records for '{branch_name}' ({branch_company}): {grn_count} records")
                
                # If no data found, check what branches actually exist
                if po_count == 0:
                    cursor.execute("SELECT DISTINCT branch, company, COUNT(*) as cnt FROM purchase_orders GROUP BY branch, company ORDER BY cnt DESC LIMIT 5")
                    existing_po = cursor.fetchall()
                    logger.warning(f"⚠️ No purchase orders found. Existing branches: {existing_po}")
                
                if si_count == 0:
                    cursor.execute("SELECT DISTINCT branch, company, COUNT(*) as cnt FROM supplier_invoices GROUP BY branch, company ORDER BY cnt DESC LIMIT 5")
                    existing_si = cursor.fetchall()
                    logger.warning(f"⚠️ No supplier invoices found. Existing branches: {existing_si}")
                    
                if hi_count == 0:
                    cursor.execute("SELECT DISTINCT branch, COUNT(*) as cnt FROM hq_invoices GROUP BY branch ORDER BY cnt DESC LIMIT 5")
                    existing_hi = cursor.fetchall()
                    logger.warning(f"⚠️ No HQ invoices found. Existing branches: {existing_hi}")
            except Exception as e:
                logger.warning(f"Error checking data existence: {e}")
            
            # First, try a simple query to verify basic data exists
            try:
                simple_test = "SELECT COUNT(*) FROM current_stock WHERE UPPER(TRIM(branch)) = UPPER(TRIM(?)) AND UPPER(TRIM(company)) = UPPER(TRIM(?))"
                cursor.execute(simple_test, (branch_name, branch_company))
                simple_count = cursor.fetchone()[0]
                logger.info(f"Simple count query found {simple_count} records for '{branch_name}' ({branch_company})")
                
                if simple_count == 0:
                    # Check what branches actually exist
                    cursor.execute("SELECT DISTINCT branch, company, COUNT(*) as cnt FROM current_stock GROUP BY branch, company ORDER BY cnt DESC LIMIT 10")
                    existing = cursor.fetchall()
                    logger.warning(f"No records found for '{branch_name}' ({branch_company}). Existing branches: {existing}")
            except Exception as e:
                logger.error(f"Error in simple test: {e}")
            
            # Retry on locked database
            attempts = 3
            df = None
            query_error = None
            for attempt in range(attempts):
                try:
                    df = pd.read_sql_query(query, conn, params=params)
                    logger.info(f"Main query executed successfully, returned {len(df)} rows")
                    
                    # Log sample of order/supply/invoice data to verify it's being retrieved
                    if not df.empty:
                        sample_with_orders = df[df['last_order_date'].notna()].head(5)
                        if not sample_with_orders.empty:
                            logger.info(f"✅ Found {len(df[df['last_order_date'].notna()])} items with order data")
                            logger.info(f"Sample order data: {sample_with_orders[['item_code', 'last_order_date', 'last_order_quantity', 'last_order_doc']].to_dict('records')}")
                        else:
                            logger.warning(f"⚠️ No items with order data found. Total items: {len(df)}")
                        
                        sample_with_supplies = df[df['last_supply_date'].notna()].head(5)
                        if not sample_with_supplies.empty:
                            logger.info(f"✅ Found {len(df[df['last_supply_date'].notna()])} items with supply data")
                            logger.info(f"Sample supply data: {sample_with_supplies[['item_code', 'last_supply_date', 'last_supply_quantity', 'last_supply_doc']].to_dict('records')}")
                        else:
                            logger.warning(f"⚠️ No items with supply data found. Total items: {len(df)}")
                        
                        sample_with_invoices = df[df['last_invoice_date'].notna()].head(5)
                        if not sample_with_invoices.empty:
                            logger.info(f"✅ Found {len(df[df['last_invoice_date'].notna()])} items with invoice data")
                            logger.info(f"Sample invoice data: {sample_with_invoices[['item_code', 'last_invoice_date', 'last_invoice_quantity', 'last_invoice_doc']].to_dict('records')}")
                        else:
                            logger.warning(f"⚠️ No items with invoice data found. Total items: {len(df)}")
                    break
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e).lower() and attempt < attempts - 1:
                        logger.warning("Database locked, retrying...")
                        import time
                        time.sleep(0.5 * (attempt + 1))
                        continue
                    query_error = str(e)
                    logger.error(f"SQL error: {e}")
                    break
                except Exception as e:
                    query_error = str(e)
                    logger.error(f"Query execution error: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    break
            
            # If main query failed or returned empty, try simplified query
            if df is None or df.empty:
                if query_error:
                    logger.warning(f"Main query failed with error: {query_error}. Trying simplified query...")
                else:
                    logger.warning("Main query returned empty. Trying simplified query...")
                
                try:
                    # Simplified query without complex JOINs
                    simple_query = """
                    SELECT 
                        cs.item_code,
                        cs.item_name,
                        cs.stock_pieces as branch_stock,
                        cs.pack_size,
                        cs.unit_price,
                        cs.stock_value,
                        NULL as supplier_stock,
                        NULL as hq_stock,
                        NULL as last_order_date,
                        NULL as last_order_quantity,
                        NULL as last_order_doc,
                        NULL as last_supply_date,
                        NULL as last_supply_quantity,
                        NULL as last_supply_doc,
                        NULL as last_invoice_date,
                        NULL as last_invoice_quantity,
                        NULL as last_invoice_doc,
                        NULL as last_grn_date,
                        NULL as last_grn_quantity,
                        NULL as last_grn_doc
                    FROM current_stock cs
                    WHERE UPPER(TRIM(cs.branch)) = UPPER(TRIM(?)) AND UPPER(TRIM(cs.company)) = UPPER(TRIM(?))
                    LIMIT 1000
                    """
                    df = pd.read_sql_query(simple_query, conn, params=(branch_name, branch_company))
                    logger.info(f"Simplified query returned {len(df)} rows")
                    
                    if not df.empty:
                        logger.info("Using simplified query results (without JOINs)")
                except Exception as e:
                    logger.error(f"Simplified query also failed: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    df = pd.DataFrame()
            
            if df is None:
                logger.error("Query returned None")
                return pd.DataFrame()
            
            if df.empty:
                logger.warning(f"Query returned empty result. Branch: {branch_name}, Company: {branch_company}")
                logger.warning(f"Database path: {self.db_path}")
                logger.warning(f"Total records in current_stock: {current_stock_count}")
                logger.warning(f"Records for selected branch: {branch_stock_count}")
                
                # Try a simpler query without all the JOINs to see if basic data exists
                try:
                    logger.info("Attempting simplified query without JOINs...")
                    simple_query = """
                    SELECT DISTINCT
                        cs.item_code,
                        cs.item_name,
                        cs.stock_pieces as branch_stock,
                        cs.pack_size,
                        cs.unit_price,
                        cs.stock_value,
                        cs.company
                    FROM current_stock cs
                    WHERE UPPER(TRIM(cs.branch)) = UPPER(TRIM(?)) AND UPPER(TRIM(cs.company)) = UPPER(TRIM(?))
                    LIMIT 100
                    """
                    simple_df = pd.read_sql_query(simple_query, conn, params=(branch_name, branch_company))
                    logger.info(f"Simplified query returned {len(simple_df)} items")
                    
                    if not simple_df.empty:
                        logger.info(f"Found {len(simple_df)} items with simplified query - using this data")
                        # Use the simplified query result
                        df = simple_df
                        # Add missing columns with None/default values
                        for col in ['supplier_stock', 'hq_stock', 'last_order_date', 'last_order_quantity', 'last_order_doc',
                                   'last_supply_date', 'last_supply_quantity', 'last_supply_doc',
                                   'last_invoice_date', 'last_invoice_quantity', 'last_invoice_doc',
                                   'last_grn_date', 'last_grn_quantity', 'last_grn_doc']:
                            if col not in df.columns:
                                df[col] = None
                    else:
                        # Get list of branches that actually have data
                        branch_query = "SELECT DISTINCT branch, company, COUNT(*) as count FROM current_stock GROUP BY UPPER(TRIM(branch)), UPPER(TRIM(company)) ORDER BY count DESC LIMIT 20"
                        branch_df = pd.read_sql_query(branch_query, conn)
                        logger.info(f"Branches with stock data ({len(branch_df)} total):")
                        for _, row in branch_df.iterrows():
                            logger.info(f"  - {row['branch']} ({row['company']}): {row['count']} items")
                        
                        # If no data for selected branch, log available branches
                        if branch_stock_count == 0 and not branch_df.empty:
                            logger.warning(f"No stock data found for '{branch_name}' ({branch_company})")
                            logger.info(f"Available branches with data: {branch_df[['branch', 'company']].to_dict('records')}")
                except Exception as e:
                    logger.error(f"Error running diagnostic queries: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            else:
                logger.info(f"Query returned {len(df)} items")
            
            conn.close()
            
            # Add ABC class and ideal pieces from Inventory_Analysis.csv
            inventory_df = self.load_inventory_analysis()
            if not inventory_df.empty:
                # Match by item_code
                # Filter by branch if available
                branch_inventory = inventory_df[
                    (inventory_df['branch_name'] == branch_name) & 
                    (inventory_df['company_name'] == branch_company)
                ].copy()
                
                if branch_inventory.empty:
                    # Try without branch filter
                    branch_inventory = inventory_df[
                        inventory_df['company_name'] == branch_company
                    ].copy()
                
                if not branch_inventory.empty:
                    # Merge all procurement bot fields from Inventory_Analysis.csv
                    merge_cols = ['item_code', 'abc_class', 'ideal_stock_pieces']
                    
                    # Add AMC (use adjusted_amc if available, else base_amc)
                    if 'adjusted_amc' in branch_inventory.columns:
                        merge_cols.append('adjusted_amc')
                    elif 'base_amc' in branch_inventory.columns:
                        merge_cols.append('base_amc')
                    
                    # Add customer_appeal
                    if 'customer_appeal' in branch_inventory.columns:
                        merge_cols.append('customer_appeal')
                    
                    # Add stock_comment (stock_recommendation column)
                    if 'stock_recommendation' in branch_inventory.columns:
                        merge_cols.append('stock_recommendation')
                    
                    # Merge available columns
                    available_cols = [col for col in merge_cols if col in branch_inventory.columns]
                    if available_cols:
                        df = df.merge(
                            branch_inventory[available_cols].drop_duplicates('item_code'),
                            on='item_code',
                            how='left'
                        )
                        
                        # Rename columns for consistency
                        if 'adjusted_amc' in df.columns:
                            df['amc'] = df['adjusted_amc']
                        elif 'base_amc' in df.columns:
                            df['amc'] = df['base_amc']
                        
                        if 'stock_recommendation' in df.columns:
                            df['stock_comment'] = df['stock_recommendation']
                    else:
                        logger.warning("No matching columns found in Inventory_Analysis.csv")
                else:
                    logger.warning(f"No inventory analysis data found for {branch_name}")
                    # Initialize columns if they don't exist
                    if 'abc_class' not in df.columns:
                        df['abc_class'] = None
                    if 'ideal_stock_pieces' not in df.columns:
                        df['ideal_stock_pieces'] = None
                    if 'amc' not in df.columns:
                        df['amc'] = None
                    if 'customer_appeal' not in df.columns:
                        df['customer_appeal'] = None
                    if 'stock_comment' not in df.columns:
                        df['stock_comment'] = None
            else:
                # Initialize columns if CSV wasn't loaded
                if 'abc_class' not in df.columns:
                    df['abc_class'] = None
                if 'ideal_stock_pieces' not in df.columns:
                    df['ideal_stock_pieces'] = None
                if 'amc' not in df.columns:
                    df['amc'] = None
                if 'customer_appeal' not in df.columns:
                    df['customer_appeal'] = None
                if 'stock_comment' not in df.columns:
                    df['stock_comment'] = None
            
            # Fill NaN values (handle None separately for nullable columns)
            df['branch_stock'] = df['branch_stock'].fillna(0)
            df['supplier_stock'] = df['supplier_stock'].fillna(0)
            df['pack_size'] = df['pack_size'].fillna(1)
            df['unit_price'] = df['unit_price'].fillna(0)
            df['stock_value'] = df['stock_value'].fillna(0)
            
            # Initialize date columns if they don't exist (from JOINs)
            if 'last_order_date' not in df.columns:
                df['last_order_date'] = None
            if 'last_supply_date' not in df.columns:
                df['last_supply_date'] = None
            if 'last_invoice_date' not in df.columns:
                df['last_invoice_date'] = None
            if 'last_invoice_doc' not in df.columns:
                df['last_invoice_doc'] = None
            if 'last_grn_date' not in df.columns:
                df['last_grn_date'] = None
            if 'last_order_quantity' not in df.columns:
                df['last_order_quantity'] = None
            if 'last_supply_quantity' not in df.columns:
                df['last_supply_quantity'] = None
            if 'last_invoice_quantity' not in df.columns:
                df['last_invoice_quantity'] = None
            
            # Handle columns that may not exist if CSV wasn't loaded
            if 'abc_class' not in df.columns:
                df['abc_class'] = ''
            else:
                df['abc_class'] = df['abc_class'].fillna('')
            
            if 'ideal_stock_pieces' not in df.columns:
                df['ideal_stock_pieces'] = 0
            else:
                df['ideal_stock_pieces'] = df['ideal_stock_pieces'].fillna(0)
            
            df['hq_stock'] = df['hq_stock'].fillna(0).astype('float32')  # Use float32 to save memory
            
            # Handle AMC column (may not exist if CSV wasn't loaded)
            if 'amc' not in df.columns:
                df['amc'] = 0
            else:
                df['amc'] = df['amc'].fillna(0).astype('float32')
            
            if 'customer_appeal' not in df.columns:
                df['customer_appeal'] = 1.0
            else:
                df['customer_appeal'] = df['customer_appeal'].fillna(1.0).astype('float32')
            
            if 'stock_comment' not in df.columns:
                df['stock_comment'] = ''
            else:
                df['stock_comment'] = df['stock_comment'].fillna('')
            
            # Keep days_since_last_supply as nullable (don't fill)
            
            # Convert AMC from pieces to packs (for procurement bot compatibility)
            df['amc_packs'] = df.apply(
                lambda row: row['amc'] / row['pack_size'] if row['pack_size'] > 0 else 0,
                axis=1
            )
            
            # Calculate Stock Level: branch_stock_pieces / (ideal_stock_pieces / pack_size)
            # Convert both to packs for comparison:
            # - ideal_stock_packs = ideal_stock_pieces / pack_size
            # - branch_stock_packs = branch_stock_pieces / pack_size  
            # - stock_level = branch_stock_packs / ideal_stock_packs
            # IMPORTANT: Stock level should reference the selected branch, not other branches
            df['ideal_stock_packs'] = df.apply(
                lambda row: row['ideal_stock_pieces'] / row['pack_size'] if row['pack_size'] > 0 else 0,
                axis=1
            )
            df['branch_stock_packs'] = df.apply(
                lambda row: row['branch_stock'] / row['pack_size'] if row['pack_size'] > 0 else 0,
                axis=1
            )
            # Fixed stock_level calculation:
            # - If branch_stock is 0, stock_level should be 0 (not a high percentage)
            # - If ideal_stock_packs is 0 or very small (< 0.1), return 0 to avoid division by tiny numbers
            # - Cap at reasonable maximum (e.g., 500%) to avoid unrealistic values
            df['stock_level'] = df.apply(
                lambda row: (
                    0.0 if row['branch_stock_packs'] == 0  # No stock = 0%
                    else 0.0 if row['ideal_stock_packs'] < 0.1  # Avoid division by tiny numbers
                    else min((row['branch_stock_packs'] / row['ideal_stock_packs']), 5.0)  # Cap at 500%
                ),
                axis=1
            )
            df['stock_level_pct'] = df['stock_level']  # Keep for compatibility
            
            logger.info(f"Retrieved {len(df)} items for stock view")
            return df
            
        except sqlite3.OperationalError as e:
            logger.error(f"Database error getting stock view data: {e}")
            logger.error(f"Database path: {self.db_path}")
            logger.error(f"Branch: {branch_name}, Company: {branch_company}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error getting stock view data: {e}")
            logger.error(f"Database path: {self.db_path}")
            logger.error(f"Branch: {branch_name}, Company: {branch_company}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def search_stock_data(self, df: pd.DataFrame, search_term: str) -> pd.DataFrame:
        """
        Search stock data by item name or item code
        
        Args:
            df: DataFrame to search
            search_term: Search term (searches in item_code and item_name)
        
        Returns:
            Filtered DataFrame
        """
        if not search_term:
            return df
        
        search_term = search_term.lower()
        mask = (
            df['item_code'].str.lower().str.contains(search_term, na=False) |
            df['item_name'].str.lower().str.contains(search_term, na=False)
        )
        return df[mask].copy()

