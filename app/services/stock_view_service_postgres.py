"""
Stock View Service for PostgreSQL/Supabase
Handles data queries and joins for stock view table using PostgreSQL
"""
import pandas as pd
import logging
from typing import Optional
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

class StockViewServicePostgres:
    """Service for querying stock view data with joins and lookups using PostgreSQL"""
    
    def __init__(self, db_manager):
        """Initialize with PostgreSQL database manager"""
        self.db_manager = db_manager
        self._inventory_analysis_cache = None
        
        logger.info("StockViewServicePostgres initialized with PostgreSQL database manager")
    
    def load_inventory_analysis(self) -> pd.DataFrame:
        """Load ABC class, AMC, and other analysis data from inventory_analysis_new table"""
        if self._inventory_analysis_cache is not None:
            logger.debug("Using cached inventory analysis")
            return self._inventory_analysis_cache
        
        try:
            logger.info("Loading inventory analysis from database...")
            # Try to load from inventory_analysis_new table
            conn = self.db_manager.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Check which table exists
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('inventory_analysis_new', 'inventory_analysis')
                ORDER BY CASE WHEN table_name = 'inventory_analysis_new' THEN 1 ELSE 2 END
                LIMIT 1
            """)
            result = cursor.fetchone()
            table_name = result['table_name'] if result else None
            
            if table_name:
                logger.info(f"Loading inventory analysis from {table_name} table")
                # Get all columns from the table
                cursor.execute(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                """, (table_name,))
                columns = [row['column_name'] for row in cursor.fetchall()]
                
                # Build SELECT query - only get essential columns for performance
                essential_cols = ['item_code', 'company_name', 'branch_name', 'abc_class', 
                                 'adjusted_amc', 'base_amc', 'ideal_stock_pieces', 
                                 'customer_appeal', 'stock_recommendation']
                available_essential = [col for col in essential_cols if col in columns]
                if not available_essential:
                    # Fallback: get item_code and any other columns that exist
                    select_cols = 'item_code'
                    for col in ['company_name', 'branch_name', 'abc_class', 'adjusted_amc', 'base_amc']:
                        if col in columns:
                            select_cols += f', {col}'
                else:
                    select_cols = ', '.join(available_essential)
                
                # Limit rows to improve performance - filter by company if possible
                query = f"SELECT {select_cols} FROM {table_name} LIMIT 100000"
                logger.info(f"Executing inventory analysis query (limited to 100k rows, essential columns only)...")
                cursor.execute(query)
                results = cursor.fetchall()
                
                if results:
                    df = pd.DataFrame(results)
                    self._inventory_analysis_cache = df
                    logger.info(f"✅ Loaded {len(df)} items from {table_name} table")
                    cursor.close()
                    self.db_manager.put_connection(conn)
                    return df
            
            cursor.close()
            self.db_manager.put_connection(conn)
            
            logger.warning("No inventory_analysis table found")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error loading inventory analysis: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return pd.DataFrame()
    
    def get_stock_view_data(self, branch_name: str, branch_company: str, 
                           source_branch_name: str, source_branch_company: str) -> pd.DataFrame:
        """
        Get stock view data with all joins and lookups using PostgreSQL
        
        Args:
            branch_name: Name of the branch to view stock for
            branch_company: Company of the branch
            source_branch_name: Name of the source/supplier branch
            source_branch_company: Company of the source branch
        
        Returns:
            DataFrame with all stock view columns
        """
        conn = None
        cursor = None
        try:
            branch_name = branch_name.strip() if branch_name else ""
            branch_company = branch_company.strip() if branch_company else ""
            source_branch_name = source_branch_name.strip() if source_branch_name else ""
            source_branch_company = source_branch_company.strip() if source_branch_company else ""
            
            logger.info(f"Querying stock view - Branch: '{branch_name}' ({branch_company}), Source: '{source_branch_name}' ({source_branch_company})")
            
            conn = self.db_manager.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # First verify branch exists and has data
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM current_stock 
                WHERE UPPER(TRIM(branch)) = UPPER(TRIM(%s)) 
                AND UPPER(TRIM(company)) = UPPER(TRIM(%s))
            """, (branch_name, branch_company))
            branch_check = cursor.fetchone()
            branch_count = branch_check['count'] if branch_check else 0
            logger.info(f"Branch '{branch_name}' ({branch_company}) has {branch_count} records in current_stock")
            
            if branch_count == 0:
                logger.warning(f"No stock data found for branch '{branch_name}' ({branch_company})")
                cursor.close()
                self.db_manager.put_connection(conn)
                return pd.DataFrame()
            
            # Simplified query: Start with unique item codes, then left join all data
            # Step 1: Get all unique item codes for the company
            query = """
            WITH unique_items AS (
                SELECT DISTINCT 
                    item_code,
                    MAX(item_name) as item_name
                FROM current_stock
                WHERE UPPER(TRIM(company)) = UPPER(TRIM(%s))
                GROUP BY item_code
            ),
            target_branch_stock AS (
                SELECT 
                    item_code,
                    item_name,
                    stock_pieces as branch_stock,
                    pack_size,
                    unit_price,
                    stock_value
                FROM current_stock
                WHERE UPPER(TRIM(branch)) = UPPER(TRIM(%s)) 
                AND UPPER(TRIM(company)) = UPPER(TRIM(%s))
            ),
            source_branch_stock AS (
                SELECT 
                    item_code,
                    stock_pieces as supplier_stock
                FROM current_stock
                WHERE UPPER(TRIM(branch)) = UPPER(TRIM(%s)) 
                AND UPPER(TRIM(company)) = UPPER(TRIM(%s))
            ),
            last_order_info AS (
                SELECT 
                    item_code,
                    MAX(document_date) as last_order_date
                FROM (
                    SELECT item_code, document_date, document_number, quantity
                    FROM purchase_orders
                    WHERE UPPER(TRIM(branch)) = UPPER(TRIM(%s)) 
                    AND UPPER(TRIM(company)) = UPPER(TRIM(%s))
                    
                    UNION ALL
                    
                    SELECT item_code, document_date, document_number, quantity
                    FROM branch_orders
                    WHERE UPPER(TRIM(destination_branch)) = UPPER(TRIM(%s)) 
                    AND UPPER(TRIM(company)) = UPPER(TRIM(%s))
                    
                    UNION ALL
                    
                    SELECT item_code, date as document_date, invoice_number as document_number, quantity
                    FROM hq_invoices
                    WHERE UPPER(TRIM(branch)) = UPPER(TRIM(%s))
                ) all_orders
                GROUP BY item_code
            ),
            last_order_details AS (
                SELECT 
                    ao.item_code,
                    MAX(ao.document_number) as last_order_doc,
                    SUM(ao.quantity) as last_order_quantity
                FROM (
                    SELECT item_code, document_date, document_number, quantity
                    FROM purchase_orders
                    WHERE UPPER(TRIM(branch)) = UPPER(TRIM(%s)) 
                    AND UPPER(TRIM(company)) = UPPER(TRIM(%s))
                    
                    UNION ALL
                    
                    SELECT item_code, document_date, document_number, quantity
                    FROM branch_orders
                    WHERE UPPER(TRIM(destination_branch)) = UPPER(TRIM(%s)) 
                    AND UPPER(TRIM(company)) = UPPER(TRIM(%s))
                    
                    UNION ALL
                    
                    SELECT item_code, date as document_date, invoice_number as document_number, quantity
                    FROM hq_invoices
                    WHERE UPPER(TRIM(branch)) = UPPER(TRIM(%s))
                ) ao
                INNER JOIN last_order_info loi ON ao.item_code = loi.item_code AND ao.document_date = loi.last_order_date
                GROUP BY ao.item_code
            ),
            last_supply_info AS (
                SELECT 
                    item_code,
                    MAX(document_date) as last_supply_date
                FROM supplier_invoices
                WHERE UPPER(TRIM(branch)) = UPPER(TRIM(%s)) 
                AND UPPER(TRIM(company)) = UPPER(TRIM(%s))
                GROUP BY item_code
            ),
            last_supply_details AS (
                SELECT 
                    si.item_code,
                    MAX(si.document_number) as last_supply_doc,
                    SUM(si.units) as last_supply_quantity
                FROM supplier_invoices si
                INNER JOIN last_supply_info lsi ON si.item_code = lsi.item_code AND si.document_date = lsi.last_supply_date
                WHERE UPPER(TRIM(si.branch)) = UPPER(TRIM(%s)) 
                AND UPPER(TRIM(si.company)) = UPPER(TRIM(%s))
                GROUP BY si.item_code
            ),
            last_invoice_info AS (
                SELECT 
                    item_code,
                    MAX(date) as last_invoice_date
                FROM hq_invoices
                WHERE UPPER(TRIM(branch)) = UPPER(TRIM(%s))
                GROUP BY item_code
            ),
            last_invoice_details AS (
                SELECT 
                    hi.item_code,
                    MAX(hi.invoice_number) as last_invoice_doc,
                    SUM(hi.quantity) as last_invoice_quantity
                FROM hq_invoices hi
                INNER JOIN last_invoice_info lii ON hi.item_code = lii.item_code AND hi.date = lii.last_invoice_date
                WHERE UPPER(TRIM(hi.branch)) = UPPER(TRIM(%s))
                GROUP BY hi.item_code
            )
            SELECT 
                ui.item_code,
                COALESCE(tbs.item_name, ui.item_name) as item_name,
                COALESCE(sbs.supplier_stock, 0) as supplier_stock,
                COALESCE(tbs.branch_stock, 0) as branch_stock,
                COALESCE(tbs.pack_size, 1) as pack_size,
                COALESCE(tbs.unit_price, 0) as unit_price,
                COALESCE(tbs.stock_value, 0) as stock_value,
                loi.last_order_date,
                lod.last_order_doc,
                lod.last_order_quantity,
                lii.last_invoice_date,
                lid.last_invoice_doc,
                lid.last_invoice_quantity,
                lsi.last_supply_date,
                lsd.last_supply_doc,
                lsd.last_supply_quantity
            FROM unique_items ui
            LEFT JOIN target_branch_stock tbs ON ui.item_code = tbs.item_code
            LEFT JOIN source_branch_stock sbs ON ui.item_code = sbs.item_code
            LEFT JOIN last_order_info loi ON ui.item_code = loi.item_code
            LEFT JOIN last_order_details lod ON ui.item_code = lod.item_code
            LEFT JOIN last_supply_info lsi ON ui.item_code = lsi.item_code
            LEFT JOIN last_supply_details lsd ON ui.item_code = lsd.item_code
            LEFT JOIN last_invoice_info lii ON ui.item_code = lii.item_code
            LEFT JOIN last_invoice_details lid ON ui.item_code = lid.item_code
            ORDER BY ui.item_code
            """
            
            params = (
                branch_company,  # unique_items
                branch_name, branch_company,  # target_branch_stock
                source_branch_name, source_branch_company,  # source_branch_stock
                branch_name, branch_company,  # purchase_orders (in last_order_info)
                branch_name, branch_company,  # branch_orders (in last_order_info)
                branch_name,  # hq_invoices (in last_order_info)
                branch_name, branch_company,  # purchase_orders (in last_order_details)
                branch_name, branch_company,  # branch_orders (in last_order_details)
                branch_name,  # hq_invoices (in last_order_details)
                branch_name, branch_company,  # last_supply_info
                branch_name, branch_company,  # last_supply_details
                branch_name,  # last_invoice_info
                branch_name  # last_invoice_details
            )
            
            logger.info(f"Executing stock view query with params: branch={branch_name}, company={branch_company}, source={source_branch_name}, source_company={source_branch_company}")
            logger.info(f"Query params: {params[:4]}... (showing first 4)")
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            logger.info(f"Query executed successfully, fetched {len(results)} rows")
            
            if results:
                df = pd.DataFrame(results)
                logger.info(f"Main query returned {len(df)} rows")
                logger.info(f"Sample columns: {list(df.columns)[:5]}")
                if len(df) > 0:
                    logger.info(f"Sample row: {df.iloc[0].to_dict()}")
            else:
                logger.warning("Main query returned no results - trying simplified query")
                # Try a simpler query - just get items from branch_stock directly (fallback)
                simple_query = """
                    SELECT 
                        item_code,
                        item_name,
                        stock_pieces as branch_stock,
                        pack_size,
                        unit_price,
                        stock_value,
                        0 as supplier_stock,
                        NULL::date as last_order_date,
                        NULL::text as last_order_doc,
                        NULL::numeric as last_order_quantity,
                        NULL::date as last_invoice_date,
                        NULL::text as last_invoice_doc,
                        NULL::numeric as last_invoice_quantity,
                        NULL::date as last_supply_date,
                        NULL::text as last_supply_doc,
                        NULL::numeric as last_supply_quantity,
                        NULL::date as last_grn_date,
                        NULL::text as last_grn_doc,
                        NULL::numeric as last_grn_quantity,
                        0 as hq_stock
                    FROM current_stock
                    WHERE UPPER(TRIM(branch)) = UPPER(TRIM(%s)) 
                    AND UPPER(TRIM(company)) = UPPER(TRIM(%s))
                    ORDER BY item_code
                    LIMIT 1000
                """
                cursor.execute(simple_query, (branch_name, branch_company))
                simple_results = cursor.fetchall()
                if simple_results:
                    df = pd.DataFrame(simple_results)
                    logger.info(f"✅ Simplified query returned {len(df)} rows")
                else:
                    logger.warning(f"Even simplified query returned no results for '{branch_name}' ({branch_company})")
                    df = pd.DataFrame()
            
            cursor.close()
            self.db_manager.put_connection(conn)
            
            # Add ABC class and AMC from inventory_analysis_new (with error protection)
            inventory_df = pd.DataFrame()
            try:
                logger.info("Loading inventory analysis data...")
                inventory_df = self.load_inventory_analysis()
                logger.info(f"Inventory analysis loaded: {len(inventory_df)} rows")
            except Exception as inv_error:
                logger.warning(f"Could not load inventory analysis (non-critical, continuing without it): {inv_error}")
                import traceback
                logger.debug(traceback.format_exc())
                inventory_df = pd.DataFrame()  # Continue without inventory analysis
            
            if not inventory_df.empty and not df.empty:
                # Filter inventory by branch if columns exist
                branch_inventory = inventory_df.copy()
                if 'branch_name' in branch_inventory.columns and 'company_name' in branch_inventory.columns:
                    branch_inventory = branch_inventory[
                        (branch_inventory['branch_name'] == branch_name) & 
                        (branch_inventory['company_name'] == branch_company)
                    ]
                    if branch_inventory.empty:
                        branch_inventory = inventory_df[
                            inventory_df['company_name'] == branch_company
                        ]
                
                # Merge available columns
                merge_cols = ['item_code']
                for col in ['abc_class', 'ideal_stock_pieces', 'adjusted_amc', 'base_amc', 
                           'customer_appeal', 'stock_recommendation']:
                    if col in branch_inventory.columns:
                        merge_cols.append(col)
                
                if len(merge_cols) > 1:
                    df = df.merge(
                        branch_inventory[merge_cols].drop_duplicates('item_code'),
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
            
            # Initialize missing columns
            for col in ['abc_class', 'ideal_stock_pieces', 'amc', 'customer_appeal', 'stock_comment',
                       'last_order_date', 'last_supply_date', 'last_invoice_date',
                       'last_order_quantity', 'last_supply_quantity', 'last_invoice_quantity',
                       'last_order_doc', 'last_supply_doc', 'last_invoice_doc']:
                if col not in df.columns:
                    df[col] = None if 'date' in col or 'quantity' in col or 'doc' in col else ('' if 'class' in col or 'comment' in col else 0)
            
            # Fill NaN values
            df['branch_stock'] = df['branch_stock'].fillna(0)
            df['supplier_stock'] = df['supplier_stock'].fillna(0)
            df['pack_size'] = df['pack_size'].fillna(1)
            df['unit_price'] = df['unit_price'].fillna(0)
            df['stock_value'] = df['stock_value'].fillna(0)
            df['amc'] = df['amc'].fillna(0)
            df['ideal_stock_pieces'] = df['ideal_stock_pieces'].fillna(0)
            df['customer_appeal'] = df['customer_appeal'].fillna(1.0)
            df['abc_class'] = df['abc_class'].fillna('')
            df['stock_comment'] = df['stock_comment'].fillna('')
            
            # Calculate AMC in packs: adjusted_amc / pack_size (as user requested)
            df['amc_packs'] = df.apply(
                lambda row: row['amc'] / row['pack_size'] if row['pack_size'] > 0 and row['amc'] > 0 else 0,
                axis=1
            )
            df['ideal_stock_packs'] = df.apply(
                lambda row: row['ideal_stock_pieces'] / row['pack_size'] if row['pack_size'] > 0 else 0,
                axis=1
            )
            df['branch_stock_packs'] = df.apply(
                lambda row: row['branch_stock'] / row['pack_size'] if row['pack_size'] > 0 else 0,
                axis=1
            )
            df['stock_level'] = df.apply(
                lambda row: (
                    0.0 if row['branch_stock_packs'] == 0
                    else 0.0 if row['ideal_stock_packs'] < 0.1
                    else min((row['branch_stock_packs'] / row['ideal_stock_packs']), 5.0)
                ),
                axis=1
            )
            df['stock_level_pct'] = df['stock_level']
            
            # Format dates for display
            date_columns = ['last_order_date', 'last_supply_date', 'last_invoice_date']
            for col in date_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                    df[col] = df[col].dt.strftime('%Y-%m-%d').replace('NaT', '').replace('nan', '')
            
            logger.info(f"✅ Successfully retrieved {len(df)} items for stock view")
            if len(df) > 0:
                logger.info(f"Sample item codes: {df['item_code'].head(5).tolist()}")
            return df
            
        except Exception as e:
            logger.error(f"❌ Error getting stock view data: {e}")
            import traceback
            logger.error(traceback.format_exc())
            if cursor:
                try:
                    cursor.close()
                except:
                    pass
            if conn:
                try:
                    self.db_manager.put_connection(conn)
                except:
                    pass
            # Return empty DataFrame - let API handle the error message
            return pd.DataFrame()

