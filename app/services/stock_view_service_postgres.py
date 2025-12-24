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
            return self._inventory_analysis_cache
        
        try:
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
                
                # Build SELECT query with all available columns
                select_cols = ', '.join(columns)
                query = f"SELECT {select_cols} FROM {table_name} LIMIT 1000000"
                
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
        try:
            branch_name = branch_name.strip() if branch_name else ""
            branch_company = branch_company.strip() if branch_company else ""
            source_branch_name = source_branch_name.strip() if source_branch_name else ""
            source_branch_company = source_branch_company.strip() if source_branch_company else ""
            
            logger.info(f"Querying stock view - Branch: '{branch_name}' ({branch_company}), Source: '{source_branch_name}' ({source_branch_company})")
            
            conn = self.db_manager.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Main query with CTEs for PostgreSQL
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
                WHERE UPPER(TRIM(branch)) = UPPER(TRIM(%s)) AND UPPER(TRIM(company)) = UPPER(TRIM(%s))
            ),
            all_items AS (
                SELECT DISTINCT 
                    item_code,
                    MAX(item_name) as item_name
                FROM (
                    SELECT item_code, item_name FROM branch_stock
                    UNION
                    SELECT DISTINCT item_code, MAX(item_name) as item_name 
                    FROM current_stock 
                    WHERE UPPER(TRIM(company)) = UPPER(TRIM(%s))
                    GROUP BY item_code
                ) combined
                GROUP BY item_code
            ),
            source_stock AS (
                SELECT 
                    item_code,
                    stock_pieces as supplier_stock
                FROM current_stock
                WHERE UPPER(TRIM(branch)) = UPPER(TRIM(%s)) AND UPPER(TRIM(company)) = UPPER(TRIM(%s))
            ),
            combined_orders AS (
                SELECT 
                    item_code,
                    document_date,
                    document_number,
                    quantity,
                    company,
                    'PURCHASE' as order_type
                FROM purchase_orders
                WHERE UPPER(TRIM(branch)) = UPPER(TRIM(%s)) AND UPPER(TRIM(company)) = UPPER(TRIM(%s))
                
                UNION ALL
                
                SELECT 
                    item_code,
                    document_date,
                    document_number,
                    quantity,
                    company,
                    'BRANCH' as order_type
                FROM branch_orders
                WHERE UPPER(TRIM(source_branch)) = UPPER(TRIM(%s)) AND UPPER(TRIM(company)) = UPPER(TRIM(%s))
                
                UNION ALL
                
                SELECT 
                    item_code,
                    date as document_date,
                    invoice_number as document_number,
                    quantity,
                    'NILA' as company,
                    'HQ_INVOICE' as order_type
                FROM hq_invoices
                WHERE UPPER(TRIM(branch)) = UPPER(TRIM(%s))
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
                    SUM(CASE WHEN document_date = (
                        SELECT MAX(document_date) 
                        FROM supplier_invoices si2 
                        WHERE si2.item_code = supplier_invoices.item_code 
                        AND UPPER(TRIM(si2.branch)) = UPPER(TRIM(supplier_invoices.branch))
                        AND UPPER(TRIM(si2.company)) = UPPER(TRIM(supplier_invoices.company))
                    ) THEN units ELSE 0 END) as last_supply_quantity
                FROM supplier_invoices
                WHERE UPPER(TRIM(branch)) = UPPER(TRIM(%s)) AND UPPER(TRIM(company)) = UPPER(TRIM(%s))
                GROUP BY item_code
            ),
            last_hq_invoice AS (
                SELECT 
                    item_code,
                    MAX(date) as last_invoice_date,
                    MAX(invoice_number) as last_invoice_doc,
                    SUM(CASE WHEN date = (
                        SELECT MAX(date) 
                        FROM hq_invoices hi2 
                        WHERE hi2.item_code = hq_invoices.item_code 
                        AND UPPER(TRIM(hi2.branch)) = UPPER(TRIM(hq_invoices.branch))
                    ) THEN quantity ELSE 0 END) as last_invoice_quantity
                FROM hq_invoices
                WHERE UPPER(TRIM(branch)) = UPPER(TRIM(%s))
                GROUP BY item_code
            ),
            last_grn AS (
                SELECT 
                    item_code,
                    MAX(document_date) as last_grn_date,
                    MAX(document_number) as last_grn_doc,
                    SUM(CASE WHEN document_date = (
                        SELECT MAX(document_date) 
                        FROM goods_received_notes grn2 
                        WHERE grn2.item_code = goods_received_notes.item_code 
                        AND UPPER(TRIM(grn2.branch)) = UPPER(TRIM(goods_received_notes.branch))
                        AND UPPER(TRIM(grn2.company)) = UPPER(TRIM(goods_received_notes.company))
                    ) THEN quantity ELSE 0 END) as last_grn_quantity
                FROM goods_received_notes
                WHERE UPPER(TRIM(branch)) = UPPER(TRIM(%s)) AND UPPER(TRIM(company)) = UPPER(TRIM(%s))
                GROUP BY item_code
            ),
            hq_stock_data AS (
                SELECT 
                    item_code,
                    stock_pieces as hq_stock
                FROM current_stock
                WHERE UPPER(TRIM(branch)) = UPPER(TRIM(%s)) AND UPPER(TRIM(company)) = UPPER(TRIM(%s))
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
            
            params = (
                branch_name, branch_company,  # branch_stock
                branch_company,  # all_items
                source_branch_name, source_branch_company,  # source_stock
                branch_name, branch_company,  # purchase_orders
                branch_name, branch_company,  # branch_orders
                branch_name,  # hq_invoices
                branch_name, branch_company,  # last_supply
                branch_name,  # last_hq_invoice
                branch_name, branch_company,  # last_grn
                'BABA DOGO HQ', branch_company  # hq_stock_data
            )
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            if results:
                df = pd.DataFrame(results)
                logger.info(f"Main query returned {len(df)} rows")
            else:
                logger.warning("Main query returned no results")
                df = pd.DataFrame()
            
            cursor.close()
            self.db_manager.put_connection(conn)
            
            # Add ABC class and AMC from inventory_analysis_new
            inventory_df = self.load_inventory_analysis()
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
                       'last_order_date', 'last_supply_date', 'last_invoice_date', 'last_grn_date',
                       'last_order_quantity', 'last_supply_quantity', 'last_invoice_quantity', 'last_grn_quantity']:
                if col not in df.columns:
                    df[col] = None if 'date' in col or 'quantity' in col else ('' if 'class' in col or 'comment' in col else 0)
            
            # Fill NaN values
            df['branch_stock'] = df['branch_stock'].fillna(0)
            df['supplier_stock'] = df['supplier_stock'].fillna(0)
            df['pack_size'] = df['pack_size'].fillna(1)
            df['unit_price'] = df['unit_price'].fillna(0)
            df['stock_value'] = df['stock_value'].fillna(0)
            df['hq_stock'] = df['hq_stock'].fillna(0)
            df['amc'] = df['amc'].fillna(0)
            df['ideal_stock_pieces'] = df['ideal_stock_pieces'].fillna(0)
            df['customer_appeal'] = df['customer_appeal'].fillna(1.0)
            df['abc_class'] = df['abc_class'].fillna('')
            df['stock_comment'] = df['stock_comment'].fillna('')
            
            # Calculate derived columns
            df['amc_packs'] = df.apply(
                lambda row: row['amc'] / row['pack_size'] if row['pack_size'] > 0 else 0,
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
            date_columns = ['last_order_date', 'last_supply_date', 'last_invoice_date', 'last_grn_date']
            for col in date_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                    df[col] = df[col].dt.strftime('%Y-%m-%d').replace('NaT', '').replace('nan', '')
            
            logger.info(f"Retrieved {len(df)} items for stock view")
            return df
            
        except Exception as e:
            logger.error(f"Error getting stock view data: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return pd.DataFrame()

