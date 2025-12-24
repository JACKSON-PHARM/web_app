"""
Dashboard Service
Provides data for dashboard views: new arrivals, priority items, etc.
"""
import logging
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import os
import glob

logger = logging.getLogger(__name__)

class DashboardService:
    """Service for dashboard data queries"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        # ALL data is in Supabase PostgreSQL - no SQLite support
        # Verify we're using PostgreSQL
        if not (hasattr(db_manager, 'connection_string') or hasattr(db_manager, 'pool') or 'PostgresDatabaseManager' in str(type(db_manager))):
            raise ValueError("DashboardService requires PostgresDatabaseManager. All data is stored in Supabase PostgreSQL.")
        self.is_postgres = True  # Always PostgreSQL now
        # Inventory analysis CSV for ABC mapping (same as stock view)
        self.inventory_analysis_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "resources", "templates", "Inventory_Analysis.csv"
        )
        self._abc_cache = None
        self._inventory_analysis_cache = None
        # Removed _cached_db_path - not needed for PostgreSQL
    
    def _normalize_query(self, query: str) -> str:
        """Convert SQLite-style ? placeholders to PostgreSQL-style %s"""
        # Always PostgreSQL - replace ? with %s
        return query.replace('?', '%s')
    
    def _execute_query(self, query: str, params: tuple = None) -> list:
        """Execute query using PostgreSQL database manager"""
        normalized_query = self._normalize_query(query)
        return self.db_manager.execute_query(normalized_query, params)

    # Removed _get_database_path - not needed for PostgreSQL

    def _load_inventory_analysis(self) -> pd.DataFrame:
        """Load Inventory_Analysis from Supabase (or CSV fallback)"""
        if self._inventory_analysis_cache is not None:
            return self._inventory_analysis_cache
        
        try:
            # For PostgreSQL, load from database table
            if self.is_postgres:
                # Try inventory_analysis_new first (then inventory_analysis as fallback)
                table_name = None
                try:
                    # Check which table exists
                    check_result = self._execute_query("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name IN ('inventory_analysis_new', 'inventory_analysis')
                        ORDER BY CASE WHEN table_name = 'inventory_analysis_new' THEN 1 ELSE 2 END
                        LIMIT 1
                    """)
                    if check_result:
                        table_name = check_result[0]['table_name']
                        logger.info(f"Using table: {table_name}")
                except Exception as e:
                    logger.warning(f"Could not check for inventory_analysis tables: {e}")
                
                if table_name:
                    try:
                        # Get column names to build appropriate query
                        # Use parameterized query for table name check
                        columns_result = self._execute_query("""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_schema = 'public' 
                            AND table_name = %s
                        """, (table_name,))
                        available_columns = [row['column_name'] for row in columns_result] if columns_result else []
                        
                        # Build SELECT list based on available columns
                        select_cols = []
                        if 'company_name' in available_columns:
                            select_cols.append('company_name')
                        elif 'company' in available_columns:
                            select_cols.append('company as company_name')
                        
                        if 'branch_name' in available_columns:
                            select_cols.append('branch_name')
                        elif 'branch' in available_columns:
                            select_cols.append('branch as branch_name')
                        
                        # Add other columns that might exist
                        for col in ['item_code', 'item_name', 'total_pieces_sold', 'total_sales_value', 
                                   'sale_days_nosun', 'base_amc', 'adjusted_amc', 'days_since_first_sale',
                                   'days_since_last_sale', 'stock_days_nosun', 'snapshot_days_nosun',
                                   'stock_availability_pct', 'abc_class', 'abc_priority',
                                   'customer_appeal', 'modal_units_sold', 'last_stock_level',
                                   'ideal_stock_pieces', 'stock_recommendation']:
                            if col in available_columns:
                                select_cols.append(col)
                        
                        if select_cols:
                            # Table name is validated, safe to use in f-string
                            # Escape table name to prevent SQL injection (though we've validated it)
                            safe_table_name = table_name.replace('"', '""')  # Escape quotes
                            query = f"""
                                SELECT {', '.join(select_cols)}
                                FROM "{safe_table_name}"
                                LIMIT 1000000
                            """
                            results = self._execute_query(query)
                            
                            if results:
                                df = pd.DataFrame(results)
                                self._inventory_analysis_cache = df
                                logger.info(f"✅ Loaded {len(df)} items from Supabase {table_name} table")
                                return df
                            else:
                                logger.warning(f"⚠️ {table_name} table is empty in Supabase. Run load_inventory_analysis_to_supabase.py to load data.")
                        else:
                            logger.warning(f"⚠️ {table_name} table exists but has no recognized columns")
                    except Exception as e:
                        logger.warning(f"Could not load from Supabase {table_name} table: {e}")
                        logger.info("Falling back to CSV file...")
                else:
                    logger.warning("⚠️ Neither inventory_analysis_new nor inventory_analysis table found in Supabase")
                    logger.info("Falling back to CSV file...")
            
            # Fallback to CSV file (for SQLite or if Supabase table doesn't exist)
            if os.path.exists(self.inventory_analysis_path):
                df = pd.read_csv(self.inventory_analysis_path)
                # Cache it
                self._inventory_analysis_cache = df
                logger.info(f"✅ Loaded {len(df)} items from Inventory_Analysis.csv")
                return df
            else:
                logger.warning(f"⚠️ Inventory_Analysis.csv not found at {self.inventory_analysis_path}")
                return pd.DataFrame()
        except Exception as e:
            logger.error(f"❌ Error loading Inventory_Analysis: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return pd.DataFrame()

    def _load_abc_map(self) -> pd.DataFrame:
        """Load ABC classification map from Inventory_Analysis.csv or latest stock_view_*.xlsx"""
        if self._abc_cache is not None:
            return self._abc_cache
        try:
            # 1) Try CSV first (Inventory_Analysis.csv)
            if os.path.exists(self.inventory_analysis_path):
                try:
                    df = pd.read_csv(self.inventory_analysis_path)
                    # Normalize column names we need: ItemCode, ABC
                    cols = {c.lower(): c for c in df.columns}
                    code_col = cols.get('item_code') or cols.get('itemcode') or cols.get('item')
                    abc_col = cols.get('abc_class') or cols.get('abc') or cols.get('class')
                    if code_col and abc_col:
                        df = df[[code_col, abc_col]].rename(
                            columns={code_col: 'item_code', abc_col: 'abc_class'}
                        )
                        # Clean up: remove rows with missing values
                        df = df.dropna(subset=['item_code', 'abc_class'])
                        df['item_code'] = df['item_code'].astype(str).str.strip()
                        df['abc_class'] = df['abc_class'].astype(str).str.strip().str.upper()
                        # Remove duplicates by item_code, keeping first occurrence
                        df = df.drop_duplicates(subset=['item_code'], keep='first')
                        self._abc_cache = df
                        logger.info(f"Loaded {len(df)} ABC mappings from CSV (deduplicated)")
                        return df
                except Exception as ex:
                    logger.warning(f"Failed to load ABC from CSV: {ex}")
            
            # 2) Fallback: latest stock_view_*.xlsx export (column T holds ABC class)
            app_root = os.path.dirname(os.path.dirname(__file__))
            # Check both app root and resources/templates folder
            xlsx_candidates = []
            # First check resources/templates folder (preferred location)
            resources_xlsx = glob.glob(os.path.join(app_root, "resources", "templates", "stock_view_*.xlsx"))
            xlsx_candidates.extend(resources_xlsx)
            # Then check app root
            root_xlsx = glob.glob(os.path.join(app_root, "stock_view_*.xlsx"))
            xlsx_candidates.extend(root_xlsx)
            # Sort by modification time (most recent first)
            xlsx_candidates = sorted(
                xlsx_candidates,
                key=os.path.getmtime,
                reverse=True
            )
            for path in xlsx_candidates:
                try:
                    logger.info(f"Trying to load ABC from Excel: {path}")
                    df_x = pd.read_excel(path)
                    logger.info(f"Excel file has {len(df_x.columns)} columns: {list(df_x.columns[:25])}")
                    
                    # Normalize column names
                    cols = {c.lower(): c for c in df_x.columns}
                    code_col = cols.get('item_code') or cols.get('itemcode') or cols.get('item')
                    
                    # Try to find ABC column by name first
                    abc_col = cols.get('abc_class') or cols.get('abc') or cols.get('class')
                    
                    # If not found by name, try column T (index 19, zero-based)
                    if not abc_col and len(df_x.columns) > 19:
                        abc_col = df_x.columns[19]
                        logger.info(f"Using column index 19 (T) as ABC: {abc_col}")
                    
                    if code_col and abc_col:
                        # Extract only needed columns
                        df_x = df_x[[code_col, abc_col]].copy()
                        df_x = df_x.rename(columns={code_col: 'item_code', abc_col: 'abc_class'})
                        
                        # Clean up: remove rows with missing values
                        df_x = df_x.dropna(subset=['item_code', 'abc_class'])
                        df_x['item_code'] = df_x['item_code'].astype(str).str.strip()
                        df_x['abc_class'] = df_x['abc_class'].astype(str).str.strip().str.upper()
                        
                        # Remove duplicates, keeping first
                        df_x = df_x.drop_duplicates(subset=['item_code'], keep='first')
                        
                        self._abc_cache = df_x
                        logger.info(f"Loaded {len(df_x)} ABC mappings from Excel file {os.path.basename(path)}")
                        return df_x
                    else:
                        logger.warning(f"Could not find item_code or ABC column in {path}. Code: {code_col}, ABC: {abc_col}")
                except Exception as ex:
                    logger.warning(f"Failed to load ABC from {path}: {ex}", exc_info=True)
            
            # Fallback: empty DataFrame
            logger.warning("No ABC mapping found in CSV or Excel files")
            self._abc_cache = pd.DataFrame(columns=['item_code', 'abc_class'])
            return self._abc_cache
        except Exception as e:
            logger.error(f"Error loading ABC map: {e}", exc_info=True)
            self._abc_cache = pd.DataFrame(columns=['item_code', 'abc_class'])
            return self._abc_cache
    
    def get_new_arrivals_this_week(self, source_branch: str, source_company: str,
                                   target_branch: str, target_company: str, limit: int = 50):
        """
        Get new arrivals (supplier invoices) from BABA DOGO HQ this week (last 7 days)
        Shows items received at HQ regardless of selected branch, with branch stock info
        
        Args:
            source_branch: Always "BABA DOGO HQ" (hardcoded)
            source_company: Company name (NILA or DAIMA)
            target_branch: Selected branch name (to show stock levels)
            target_company: Target company name
            limit: Maximum number of items to return
            
        Returns:
            DataFrame with columns: item_code, item_name, quantity, document_date, document_number, 
                                   source_type, branch_stock, hq_stock, abc_class, etc.
        """
        try:
            # Always use BABA DOGO HQ as source branch
            hq_branch = "BABA DOGO HQ"
            
            # Use database manager instead of direct SQLite connection
            # First, find what companies actually have invoices for BABA DOGO HQ
            # (invoices might be for a different company than the selected one)
            available_companies_result = self._execute_query("""
                SELECT DISTINCT company 
                FROM supplier_invoices 
                WHERE branch = ?
            """, (hq_branch,))
            available_companies = [row['company'] for row in available_companies_result] if available_companies_result else []
            
            if not available_companies:
                # Check if table exists and has any data
                total_invoices_result = self._execute_query("SELECT COUNT(*) as count FROM supplier_invoices")
                total_invoices = total_invoices_result[0]['count'] if total_invoices_result else 0
                logger.warning(f"No supplier invoices found for {hq_branch} (total invoices in table: {total_invoices})")
                logger.warning(f"Database: Supabase PostgreSQL")
                return pd.DataFrame(columns=['item_code', 'item_name', 'quantity', 'document_date', 
                                            'document_number', 'source_type', 'branch_stock_pieces', 
                                            'branch_stock_packs', 'hq_stock_pieces', 'hq_stock_packs'])
            
            logger.info(f"Found supplier invoices for companies: {available_companies} at {hq_branch}")
            
            # Calculate date range: last 7 days from TODAY
            # This shows actual "this week" arrivals relative to current date
            today = datetime.now().date()
            end_date = today
            start_date = end_date - timedelta(days=7)
            
            # Check if there are any invoices in the last 7 days
            recent_count_result = self._execute_query("""
                SELECT COUNT(*) as count
                FROM supplier_invoices 
                WHERE branch = %s AND document_date >= %s AND document_date <= %s
            """, (hq_branch, start_date, end_date))
            recent_count = recent_count_result[0]['count'] if recent_count_result else 0
            
            # Always use today's date range - don't fall back to old dates
            # This ensures we show current data when available, and empty when it's not
            # Check what the most recent invoice date actually is (for logging/debugging)
            max_date_result = self._execute_query("""
                SELECT MAX(document_date) as max_date
                FROM supplier_invoices 
                WHERE branch = %s
            """, (hq_branch,))
            max_date = max_date_result[0]['max_date'] if max_date_result and max_date_result[0].get('max_date') else None
            
            if max_date:
                if isinstance(max_date, str):
                    max_date_obj = datetime.strptime(max_date, '%Y-%m-%d').date()
                elif isinstance(max_date, datetime):
                    max_date_obj = max_date.date()
                else:
                    max_date_obj = max_date
                
                days_old = (today - max_date_obj).days
                if days_old > 7:
                    logger.warning(f"⚠️ Most recent invoice date ({max_date_obj}) is {days_old} days old. No invoices in last 7 days. Refresh data to see new arrivals.")
                else:
                    logger.info(f"✅ Found {recent_count} invoices in last 7 days (most recent: {max_date_obj})")
            else:
                logger.warning(f"⚠️ No invoices found in database for {hq_branch}. Refresh data to see new arrivals.")
            
            # If no invoices in last 7 days, return empty DataFrame (don't show old data)
            if recent_count == 0:
                logger.info(f"No invoices in last 7 days from today ({start_date} to {end_date}). Returning empty results. Refresh data to see new arrivals.")
                return pd.DataFrame(columns=['item_code', 'item_name', 'quantity', 'document_date', 
                                            'document_number', 'source_type', 'branch_stock_pieces', 
                                            'branch_stock_packs', 'hq_stock_pieces', 'hq_stock_packs'])
            else:
                logger.info(f"Found {recent_count} invoices in last 7 days. Querying new arrivals from {hq_branch} for this week: {start_date} to {end_date}")
            
            # Query supplier invoices from BABA DOGO HQ (last 7 days from most recent date)
            # Show all items received at HQ, regardless of target branch stock
            # Include branch stock from selected branch for reference
            # Check if current_stock has data, if not try stock_data as fallback
            hq_stock_result = self._execute_query("SELECT COUNT(*) as count FROM current_stock WHERE branch = %s", (hq_branch,))
            hq_stock_count = hq_stock_result[0]['count'] if hq_stock_result else 0
            use_stock_data_fallback = False
            hq_latest_date = None
            branch_latest_date = None
            
            # Default query using current_stock (will show zeros if table is empty)
            invoice_query = """
                SELECT 
                    si.item_code,
                    MAX(si.item_name) AS item_name,
                    MAX(si.units) as quantity,
                    MAX(COALESCE(cs_hq.pack_size, 1)) AS pack_size,
                    MAX(ROUND(si.units / NULLIF(COALESCE(cs_hq.pack_size, 1), 0))) AS quantity_packs,
                    MAX(si.document_date) AS document_date,
                    MAX(si.document_number) AS document_number,
                    'Supplier Invoice' as source_type,
                    COALESCE(MAX(cs_branch.stock_pieces), 0) AS branch_stock_pieces,
                    COALESCE(MAX(cs_branch.stock_pieces / NULLIF(COALESCE(cs_branch.pack_size, 1), 0)), 0) AS branch_stock_packs,
                    MAX(COALESCE(cs_hq.stock_pieces, 0)) AS hq_stock_pieces,
                    COALESCE(MAX(cs_hq.stock_pieces / NULLIF(COALESCE(cs_hq.pack_size, 1), 0)), 0) AS hq_stock_packs,
                    MAX(cs_hq.pack_size) AS pack_size_hq,
                    MAX(cs_branch.pack_size) AS pack_size_branch
                FROM supplier_invoices si
                LEFT JOIN current_stock cs_hq
                    ON cs_hq.item_code = si.item_code 
                   AND cs_hq.company = si.company 
                   AND cs_hq.branch = ?
                LEFT JOIN current_stock cs_branch
                    ON cs_branch.item_code = si.item_code
                   AND cs_branch.company = ?
                   AND cs_branch.branch = ?
                WHERE si.branch = ?
                    AND si.document_date >= ? AND si.document_date <= ?
                GROUP BY si.item_code
                ORDER BY MAX(si.document_date) DESC, MAX(si.document_number) DESC
                LIMIT ?
            """
            
            if hq_stock_count == 0:
                # Try to use stock_data as fallback
                try:
                    hq_date_result = self._execute_query("SELECT MAX(snapshot_date) as max_date FROM stock_data WHERE branch_name = %s", (hq_branch,))
                    hq_latest_date = hq_date_result[0]['max_date'] if hq_date_result and hq_date_result[0].get('max_date') else None
                    
                    branch_date_result = self._execute_query("SELECT MAX(snapshot_date) as max_date FROM stock_data WHERE company_name = %s AND branch_name = %s", 
                                 (target_company, target_branch))
                    branch_latest_date = branch_date_result[0]['max_date'] if branch_date_result and branch_date_result[0].get('max_date') else None
                    
                    if hq_latest_date or branch_latest_date:
                        use_stock_data_fallback = True
                        logger.info(f"current_stock table is empty for {hq_branch}, using stock_data table as fallback (HQ date: {hq_latest_date}, Branch date: {branch_latest_date})")
                        
                        # Override query to use stock_data
                        invoice_query = """
                            SELECT 
                                si.item_code,
                                MAX(si.item_name) AS item_name,
                                MAX(si.units) as quantity,
                                MAX(COALESCE(sd_hq.pack_size, 1)) AS pack_size,
                                MAX(ROUND(si.units / NULLIF(COALESCE(sd_hq.pack_size, 1), 0))) AS quantity_packs,
                                MAX(si.document_date) AS document_date,
                                MAX(si.document_number) AS document_number,
                                'Supplier Invoice' as source_type,
                                COALESCE(MAX(sd_branch.total_pieces_in_stock), 0) AS branch_stock_pieces,
                                COALESCE(MAX(sd_branch.total_pieces_in_stock / NULLIF(COALESCE(sd_branch.pack_size, 1), 0)), 0) AS branch_stock_packs,
                                MAX(COALESCE(sd_hq.total_pieces_in_stock, 0)) AS hq_stock_pieces,
                                COALESCE(MAX(sd_hq.total_pieces_in_stock / NULLIF(COALESCE(sd_hq.pack_size, 1), 0)), 0) AS hq_stock_packs,
                                MAX(sd_hq.pack_size) AS pack_size_hq,
                                MAX(sd_branch.pack_size) AS pack_size_branch
                            FROM supplier_invoices si
                            LEFT JOIN stock_data sd_hq
                                ON sd_hq.item_code = si.item_code 
                               AND sd_hq.company_name = si.company 
                               AND sd_hq.branch_name = %s
                               AND (%s IS NULL OR sd_hq.snapshot_date = %s)
                            LEFT JOIN stock_data sd_branch
                                ON sd_branch.item_code = si.item_code
                               AND sd_branch.company_name = %s
                               AND sd_branch.branch_name = %s
                               AND (%s IS NULL OR sd_branch.snapshot_date = %s)
                            WHERE si.branch = %s
                                AND si.document_date >= %s AND si.document_date <= %s
                            GROUP BY si.item_code
                            ORDER BY MAX(si.document_date) DESC, MAX(si.document_number) DESC
                            LIMIT %s
                        """
                    else:
                        logger.warning(f"Both current_stock and stock_data tables are empty. Stock values will show as 0.")
                except Exception as e:
                    logger.warning(f"Error checking stock_data table: {e}. Stock values will show as 0.")
            
            # Execute query with appropriate parameters based on whether we're using stock_data fallback
            if use_stock_data_fallback:
                # Use latest snapshot dates (or None if no data)
                hq_snapshot_date = hq_latest_date if hq_latest_date else None
                branch_snapshot_date = branch_latest_date if branch_latest_date else None
                
                results = self._execute_query(
                    invoice_query,
                    (hq_branch, hq_snapshot_date, hq_snapshot_date, target_company, target_branch, branch_snapshot_date, branch_snapshot_date, hq_branch, start_date, end_date, limit * 2)
                )
            else:
                results = self._execute_query(
                    invoice_query,
                    (hq_branch, target_company, target_branch, hq_branch, start_date, end_date, limit * 2)
                )
            
            combined = pd.DataFrame(results) if results else pd.DataFrame()
            logger.info(f"New arrivals query returned {len(combined)} items from {hq_branch} (this week: {start_date} to {end_date})")
            
            # If no results in last 7 days, try last 30 days as fallback
            if combined.empty:
                logger.info(f"No invoices in last 7 days, trying last 30 days from today")
                start_date_fallback = today - timedelta(days=30)
                if use_stock_data_fallback:
                    hq_snapshot_date = hq_latest_date if hq_latest_date else None
                    branch_snapshot_date = branch_latest_date if branch_latest_date else None
                    results = self._execute_query(
                        invoice_query,
                        (hq_branch, hq_snapshot_date, hq_snapshot_date, target_company, target_branch, branch_snapshot_date, branch_snapshot_date, hq_branch, start_date_fallback, end_date, limit * 2)
                    )
                else:
                    results = self._execute_query(
                        invoice_query,
                        (hq_branch, target_company, target_branch, hq_branch, start_date_fallback, end_date, limit * 2)
                    )
                combined = pd.DataFrame(results) if results else pd.DataFrame()
                logger.info(f"Fallback query returned {len(combined)} items from {hq_branch} (last 30 days)")
            
            if combined.empty:
                logger.warning(f"No new arrivals found at {hq_branch} (checked last 30 days from today: {start_date} to {end_date})")
                return pd.DataFrame(columns=['item_code', 'item_name', 'quantity', 'document_date', 
                                            'document_number', 'source_type', 'branch_stock_pieces', 
                                            'branch_stock_packs', 'hq_stock_pieces', 'hq_stock_packs'])
            
            # Attach ABC class, AMC, and other data from Inventory_Analysis.csv
            inventory_df = self._load_inventory_analysis()
            if not inventory_df.empty:
                # Filter inventory data for the target branch/company if available
                branch_inventory = inventory_df[
                    (inventory_df.get('branch_name', '') == target_branch) & 
                    (inventory_df.get('company_name', '') == target_company)
                ].copy()
                
                if branch_inventory.empty:
                    # Try without branch filter
                    branch_inventory = inventory_df[
                        inventory_df.get('company_name', '') == target_company
                    ].copy()
                
                if not branch_inventory.empty:
                    # Merge available columns
                    merge_cols = ['item_code']
                    if 'abc_class' in branch_inventory.columns:
                        merge_cols.append('abc_class')
                    if 'adjusted_amc' in branch_inventory.columns:
                        merge_cols.append('adjusted_amc')
                    elif 'base_amc' in branch_inventory.columns:
                        merge_cols.append('base_amc')
                    if 'customer_appeal' in branch_inventory.columns:
                        merge_cols.append('customer_appeal')
                    if 'stock_recommendation' in branch_inventory.columns:
                        merge_cols.append('stock_recommendation')
                    
                    available_cols = [col for col in merge_cols if col in branch_inventory.columns]
                    if available_cols:
                        combined = combined.merge(
                            branch_inventory[available_cols].drop_duplicates('item_code'),
                            on='item_code',
                            how='left'
                        )
                        
                        # Rename columns for consistency
                        if 'adjusted_amc' in combined.columns:
                            combined['amc'] = combined['adjusted_amc']
                        elif 'base_amc' in combined.columns:
                            combined['amc'] = combined['base_amc']
                        
                        if 'stock_recommendation' in combined.columns:
                            combined['stock_comment'] = combined['stock_recommendation']
            
            # Ensure required columns exist
            if 'abc_class' not in combined.columns:
                combined['abc_class'] = ''
            if 'amc' not in combined.columns:
                combined['amc'] = 0
            if 'customer_appeal' not in combined.columns:
                combined['customer_appeal'] = 1.0
            if 'stock_comment' not in combined.columns:
                combined['stock_comment'] = ''
            
            # Fill NaN values
            combined['abc_class'] = combined['abc_class'].fillna('')
            combined['amc'] = pd.to_numeric(combined['amc'], errors='coerce').fillna(0)
            combined['customer_appeal'] = pd.to_numeric(combined['customer_appeal'], errors='coerce').fillna(1.0)
            combined['stock_comment'] = combined['stock_comment'].fillna('')
            combined['branch_stock_pieces'] = pd.to_numeric(combined['branch_stock_pieces'], errors='coerce').fillna(0)
            combined['branch_stock_packs'] = pd.to_numeric(combined['branch_stock_packs'], errors='coerce').fillna(0)
            combined['hq_stock_pieces'] = pd.to_numeric(combined['hq_stock_pieces'], errors='coerce').fillna(0)
            combined['hq_stock_packs'] = pd.to_numeric(combined['hq_stock_packs'], errors='coerce').fillna(0)
            
            # Sort by date descending and limit
            combined = combined.sort_values('document_date', ascending=False).head(limit)
            
            logger.info(f"Found {len(combined)} new arrivals from {hq_branch} (last 7 days from most recent date: {max_date})")
            return combined
            
        except Exception as e:
            logger.error(f"Error getting new arrivals: {e}", exc_info=True)
            return pd.DataFrame(columns=['item_code', 'item_name', 'quantity', 'document_date', 
                                        'document_number', 'source_type'])
    
    def get_priority_items_between_branches(self, target_branch: str, target_company: str,
                                            source_branch: str, source_company: str,
                                            limit: int = 50):
        """
        Get priority items: Items that are IN STOCK at source branch (HQ) but NOT in selected branch
        and are fast moving (Class A, B, or C)
        
        Priority items are those where:
        - Item is available (stock_pieces > 0) in source branch (HQ)
        - Item is NOT available (stock_pieces <= 0) in target branch (selected branch)
        - Item is fast moving (ABC Class A, B, or C)
        
        Args:
            target_branch: Target branch name (selected branch - where we DON'T have stock)
            target_company: Target company name
            source_branch: Source branch name (e.g., "BABA DOGO HQ" - where we HAVE stock)
            source_company: Source company name
            limit: Maximum number of items to return
            
        Returns:
            DataFrame with columns: item_code, item_name, source_stock_packs, branch_name,
                                  target_stock_packs, abc_class, stock_level_pct, amc_pieces, pack_size
        """
        try:
            # Use database manager instead of direct SQLite connection
            # Check if current_stock has data, if not use stock_data as fallback
            # Check both current_stock and stock_data for source branch
            source_stock_result = self._execute_query(
                "SELECT COUNT(*) as count FROM current_stock WHERE branch = ? AND company = ?",
                (source_branch, source_company)
            )
            source_stock_count = source_stock_result[0]['count'] if source_stock_result else 0
            
            # Also check stock_data for source branch (if table exists - PostgreSQL might not have this)
            try:
                stock_data_result = self._execute_query(
                    "SELECT COUNT(*) as count, MAX(snapshot_date) as max_date FROM stock_data WHERE branch_name = %s AND company_name = %s",
                    (source_branch, source_company)
                )
                stock_data_count = stock_data_result[0]['count'] if stock_data_result else 0
                source_latest_date = stock_data_result[0]['max_date'] if stock_data_result and stock_data_result[0].get('max_date') else None
            except Exception:
                # stock_data table might not exist in PostgreSQL (we removed it)
                stock_data_count = 0
                source_latest_date = None
            
            # Check target branch stock_data
            try:
                target_latest_date_result = self._execute_query(
                    "SELECT MAX(snapshot_date) as max_date FROM stock_data WHERE branch_name = %s AND company_name = %s",
                    (target_branch, target_company)
                )
                target_latest_date = target_latest_date_result[0]['max_date'] if target_latest_date_result and target_latest_date_result[0].get('max_date') else None
            except Exception:
                target_latest_date = None
            
            use_stock_data_fallback = False
            
            # Prefer current_stock if available, otherwise use stock_data with latest snapshot
            if source_stock_count > 0:
                # Use current_stock (most recent data) - Simplified query to avoid timeouts
                logger.info(f"Using current_stock table for priority items (found {source_stock_count} records for {source_branch})")
                # Simplified query - remove complex subquery for last_order_date to avoid timeouts
                query = """
                    SELECT 
                        cs_source.item_code,
                        MAX(cs_source.item_name) AS item_name,
                        MAX(cs_source.stock_pieces) AS source_stock_pieces,
                        MAX(cs_source.pack_size) AS source_pack_size,
                        COALESCE(MAX(cs_target.stock_pieces), 0) AS target_stock_pieces,
                        COALESCE(MAX(cs_target.pack_size), MAX(cs_source.pack_size)) AS pack_size,
                        0 AS stock_level_pct,
                        NULL::date AS last_order_date
                    FROM current_stock cs_source
                    LEFT JOIN current_stock cs_target
                        ON cs_target.item_code = cs_source.item_code
                        AND UPPER(TRIM(cs_target.company)) = UPPER(TRIM(%s))
                        AND UPPER(TRIM(cs_target.branch)) = UPPER(TRIM(%s))
                    WHERE UPPER(TRIM(cs_source.branch)) = UPPER(TRIM(%s))
                        AND UPPER(TRIM(cs_source.company)) = UPPER(TRIM(%s))
                        AND cs_source.stock_pieces > 0
                        AND (
                            cs_target.stock_pieces IS NULL 
                            OR cs_target.stock_pieces <= 0
                            OR cs_target.stock_pieces < 1000
                        )
                    GROUP BY cs_source.item_code
                    ORDER BY MAX(cs_source.stock_pieces) DESC
                    LIMIT %s
                """
                # Normalize query for database type
                query = self._normalize_query(query)
                params = (
                    target_company, target_branch,  # For cs_target join
                    source_branch, source_company,  # For cs_source WHERE
                    limit  # For LIMIT
                )
            elif stock_data_count > 0 and source_latest_date:
                # Use stock_data with latest snapshot (fallback to most recent available data)
                use_stock_data_fallback = True
                logger.info(f"current_stock table has no data for {source_branch}, using stock_data table with latest snapshot (Source date: {source_latest_date}, Target date: {target_latest_date})")
                
                # Override query to use stock_data
                query = """
                    SELECT 
                        sd_source.item_code,
                        MAX(sd_source.item_name) AS item_name,
                        MAX(sd_source.total_pieces_in_stock) AS source_stock_pieces,
                        MAX(sd_source.pack_size) AS source_pack_size,
                        COALESCE(MAX(sd_target.total_pieces_in_stock), 0) AS target_stock_pieces,
                        COALESCE(MAX(sd_target.pack_size), MAX(sd_source.pack_size)) AS pack_size,
                        0 AS stock_level_pct,
                        MAX(po.last_order_date) AS last_order_date
                    FROM stock_data sd_source
                    LEFT JOIN stock_data sd_target
                        ON sd_target.item_code = sd_source.item_code
                        AND sd_target.company_name = ?
                        AND sd_target.branch_name = ?
                        AND (? IS NULL OR sd_target.snapshot_date = ?)
                    LEFT JOIN (
                        SELECT 
                            item_code,
                            MAX(date) AS last_order_date
                        FROM (
                            SELECT item_code, document_date as date
                            FROM purchase_orders
                            WHERE company = ? AND branch = ?
                            UNION ALL
                            SELECT item_code, document_date as date
                            FROM branch_orders
                            WHERE company = ? AND source_branch = ?
                            UNION ALL
                            SELECT item_code, date
                            FROM hq_invoices
                            WHERE branch = ?
                        ) combined_orders
                        GROUP BY item_code
                    ) po ON po.item_code = sd_source.item_code
                    WHERE sd_source.branch_name = ? 
                        AND sd_source.company_name = ?
                        AND (? IS NULL OR sd_source.snapshot_date = ?)
                        AND sd_source.total_pieces_in_stock > 0
                        AND (
                            sd_target.total_pieces_in_stock IS NULL 
                            OR sd_target.total_pieces_in_stock <= 0
                            OR sd_target.total_pieces_in_stock < 1000
                        )
                    GROUP BY sd_source.item_code
                    ORDER BY MAX(sd_source.total_pieces_in_stock) DESC
                    LIMIT ?
                """
            else:
                logger.warning(f"No stock data found for {source_branch} ({source_company}) in either current_stock or stock_data tables.")
                logger.info(f"Please sync stock data using 'Refresh All Data' -> 'Stock' to populate priority items.")
                return pd.DataFrame(columns=['item_code', 'item_name', 'source_stock_packs', 'branch_name',
                                            'target_stock_packs', 'abc_class', 'stock_level_pct', 'amc_packs', 
                                            'pack_size', 'last_order_date'])
            # Check if source and target are the same branch (would return no results)
            if source_branch == target_branch and source_company == target_company:
                logger.warning(f"⚠️ Source and target branches are the same ({source_branch}), cannot find priority items. Priority items require different branches.")
                logger.info(f"💡 Tip: Select a different target branch (e.g., a retail branch) to see items that need to be transferred from {source_branch}.")
                return pd.DataFrame(columns=['item_code', 'item_name', 'source_stock_packs', 'branch_name',
                                            'target_stock_packs', 'abc_class', 'stock_level_pct', 'amc_packs', 
                                            'pack_size', 'last_order_date'])
            
            # Execute query with appropriate parameters using database manager
            logger.info(f"🔍 Executing priority items query: source={source_branch} ({source_company}), target={target_branch} ({target_company})")
            logger.info(f"📊 Query will be normalized for {'PostgreSQL' if self.is_postgres else 'SQLite'}")
            
            if use_stock_data_fallback:
                source_snapshot_date = source_latest_date if source_latest_date else None
                target_snapshot_date = target_latest_date if target_latest_date else None
                # Normalize query before executing
                normalized_query = self._normalize_query(query)
                logger.debug(f"Normalized query (first 200 chars): {normalized_query[:200]}")
                results = self._execute_query(
                    normalized_query,
                    (target_company, target_branch, target_snapshot_date, target_snapshot_date, 
                     target_company, target_branch, target_company, target_branch, 
                     source_branch, source_company, 
                     source_snapshot_date, source_snapshot_date, limit * 20)
                )
            else:
                # Query was already normalized above when params were set
                # But ensure it's normalized here too
                normalized_query = self._normalize_query(query) if 'params' not in locals() else query
                logger.debug(f"Normalized query (first 200 chars): {normalized_query[:200]}")
                try:
                    results = self._execute_query(
                        normalized_query,
                        params if 'params' in locals() else (target_company, target_branch, target_company, target_branch, target_company, target_branch,
                         target_branch, source_branch, source_company, limit * 20)  # Get more to filter by ABC later
                    )
                except Exception as query_error:
                    logger.error(f"Priority items query failed: {query_error}")
                    import traceback
                    logger.error(traceback.format_exc())
                    # Return empty DataFrame on error to avoid breaking the UI
                    return pd.DataFrame(columns=['item_code', 'item_name', 'source_stock_packs', 'branch_name',
                                                'target_stock_packs', 'abc_class', 'stock_level_pct', 'amc_packs', 
                                                'pack_size', 'last_order_date'])
            
            # Convert results to DataFrame
            df = pd.DataFrame(results) if results else pd.DataFrame()
            
            logger.info(f"📊 Query returned {len(df)} rows before filtering")
            
            if df.empty:
                logger.info(f"No priority items found: source={source_branch} has stock, target={target_branch} doesn't")
                logger.info(f"💡 This could mean:")
                logger.info(f"   1. Target branch ({target_branch}) already has all items in stock")
                logger.info(f"   2. Source branch ({source_branch}) doesn't have stock for items that target needs")
                logger.info(f"   3. Try selecting different branches")
                return pd.DataFrame(columns=['item_code', 'item_name', 'source_stock_packs', 'branch_name',
                                            'target_stock_packs', 'abc_class', 'stock_level_pct', 'amc_packs', 
                                            'pack_size', 'last_order_date'])
            
            # Aggressive duplicate removal by item_code (should not happen with GROUP BY, but safety check)
            initial_count = len(df)
            # Check for duplicates before removal
            duplicates = df[df.duplicated(subset=['item_code'], keep=False)]
            if not duplicates.empty:
                logger.warning(f"Found {len(duplicates)} duplicate item_codes in priority query before removal")
            
            df = df.drop_duplicates(subset=['item_code'], keep='first')
            if len(df) < initial_count:
                logger.warning(f"Removed {initial_count - len(df)} duplicate items from priority query (after GROUP BY)")
            
            # Verify we have unique item_codes
            if len(df) != len(df['item_code'].unique()):
                logger.error(f"Still have duplicates after drop_duplicates! {len(df)} rows vs {len(df['item_code'].unique())} unique item_codes")
                # Force unique by taking first occurrence
                df = df.groupby('item_code').first().reset_index()
            
            # Verify source stock > 0 (should already be filtered in SQL, but double-check)
            df = df[df['source_stock_pieces'] > 0]
            
            # Load ABC class and AMC from Inventory_Analysis (same as desktop version)
            inventory_df = self._load_inventory_analysis()
            if not inventory_df.empty:
                # Filter by target branch and company (same as desktop)
                branch_inventory = inventory_df[
                    (inventory_df['branch_name'] == target_branch) & 
                    (inventory_df['company_name'] == target_company)
                ].copy()
                
                if branch_inventory.empty:
                    # Try without branch filter (use company only)
                    branch_inventory = inventory_df[
                        inventory_df['company_name'] == target_company
                    ].copy()
                
                if not branch_inventory.empty:
                    # Prepare columns to merge (same as desktop)
                    merge_cols = ['item_code']
                    
                    # Add ABC class
                    if 'abc_class' in branch_inventory.columns:
                        merge_cols.append('abc_class')
                    
                    # Add AMC (use adjusted_amc if available, else base_amc)
                    if 'adjusted_amc' in branch_inventory.columns:
                        merge_cols.append('adjusted_amc')
                    elif 'base_amc' in branch_inventory.columns:
                        merge_cols.append('base_amc')
                    
                    # Merge available columns
                    available_cols = [col for col in merge_cols if col in branch_inventory.columns]
                    if available_cols:
                        branch_inventory_dedup = branch_inventory[available_cols].drop_duplicates('item_code')
                        df = df.merge(branch_inventory_dedup, on='item_code', how='left')
                        
                        # Set ABC class (same as desktop)
                        if 'abc_class' in df.columns:
                            df['abc_class'] = df['abc_class'].fillna('')
                        else:
                            df['abc_class'] = ''
                        
                        # Set AMC (use adjusted_amc if available, else base_amc) - same as desktop
                        if 'adjusted_amc' in df.columns:
                            df['amc_pieces'] = df['adjusted_amc'].fillna(0)
                        elif 'base_amc' in df.columns:
                            df['amc_pieces'] = df['base_amc'].fillna(0)
                        else:
                            df['amc_pieces'] = 0
                    else:
                        df['abc_class'] = ''
                        df['amc_pieces'] = 0
                else:
                    df['abc_class'] = ''
                    df['amc_pieces'] = 0
            else:
                # Fallback: Load ABC class from ABC map (same as desktop)
                abc_map = self._load_abc_map()
                if not abc_map.empty:
                    # Ensure ABC map is deduplicated by item_code before merging
                    abc_map = abc_map.drop_duplicates(subset=['item_code'], keep='first')
                    # Merge ABC class by item_code
                    df = df.merge(abc_map, on='item_code', how='left')
                    # Fill missing ABC class with empty string
                    df['abc_class'] = df['abc_class'].fillna('')
                else:
                    df['abc_class'] = ''
                df['amc_pieces'] = 0
            
            # Filter to A/B/C only (fast moving items) - same as desktop version (no conditional check)
            before_abc = len(df)
            df = df[df['abc_class'].isin(['A', 'B', 'C'])]
            logger.info(f"After ABC filter (A/B/C): {len(df)} items (was {before_abc})")
            
            # Log detailed diagnostics before reorder filter
            logger.info(f"📊 Before reorder level filter: {len(df)} items")
            if len(df) > 0:
                logger.info(f"   Sample items: {df[['item_code', 'item_name', 'target_stock_pieces', 'source_stock_pieces']].head(3).to_dict('records')}")
            
            if df.empty:
                logger.info(f"No priority items found (no A/B/C items in {source_branch} but not in {target_branch})")
                return pd.DataFrame(columns=['item_code', 'item_name', 'source_stock_packs', 'branch_name',
                                            'target_stock_packs', 'abc_class', 'stock_level_pct', 'amc_packs', 
                                            'pack_size', 'last_order_date'])
            
            # Calculate reorder level based on ABC class and filter items below reorder level
            # Reorder thresholds: A=50%, B=30%, C=25% of AMC
            df['reorder_threshold'] = df.apply(
                lambda row: row['amc_pieces'] * {'A': 0.5, 'B': 0.3, 'C': 0.25}.get(row.get('abc_class', 'C'), 0.25),
                axis=1
            )
            
            # Filter to items that are out of stock OR below reorder level
            before_reorder_filter = len(df)
            df = df[
                (df['target_stock_pieces'] <= 0) | 
                (df['target_stock_pieces'] < df['reorder_threshold'])
            ]
            logger.info(f"After reorder level filter: {len(df)} items (was {before_reorder_filter})")

            # Ensure pack_size is available - get from source or target stock, or use default 1
            if 'pack_size' not in df.columns or df['pack_size'].isna().all():
                # Try to get pack_size from source_pack_size
                if 'source_pack_size' in df.columns:
                    df['pack_size'] = df['source_pack_size'].fillna(1)
                else:
                    df['pack_size'] = 1
            
            # Replace 0 or NaN pack_size with 1 to avoid division by zero
            df['pack_size'] = df['pack_size'].replace(0, 1).fillna(1)
            source_pack_size = df['source_pack_size'].replace(0, 1).fillna(1) if 'source_pack_size' in df.columns else df['pack_size']
            
            # Calculate packs from pieces using pack_size (round to whole packs)
            df['source_stock_packs'] = (df['source_stock_pieces'] / source_pack_size).round(0).astype(int)
            df['target_stock_packs'] = (df['target_stock_pieces'] / df['pack_size']).round(0).astype(int)
            
            # Convert AMC from pieces to packs (using target branch pack_size) - round to 2 decimals for display
            df['amc_packs'] = (df['amc_pieces'] / df['pack_size']).round(2)
            
            # Recalculate stock_level_pct using AMC from Inventory_Analysis
            df['stock_level_pct'] = df.apply(
                lambda row: (row['target_stock_pieces'] / row['amc_pieces'] * 100) if row['amc_pieces'] > 0 else 0,
                axis=1
            )
            
            # Add branch_name column (target branch)
            df['branch_name'] = target_branch
            
            # Format dates - convert to datetime and format as string for display
            if 'last_order_date' in df.columns:
                df['last_order_date'] = pd.to_datetime(df['last_order_date'], errors='coerce')
                # Format as YYYY-MM-DD or empty string if NaT
                df['last_order_date'] = df['last_order_date'].dt.strftime('%Y-%m-%d').replace('NaT', '').replace('nan', '')
            
            # Drop temporary columns
            df = df.drop(columns=['source_pack_size', 'reorder_threshold'], errors='ignore')
            
            # Sort by ABC class (A first, then B, then C), then by target stock ascending (lowest first)
            df['abc_sort'] = df['abc_class'].map({'A': 1, 'B': 2, 'C': 3}).fillna(99)
            df = df.sort_values(['abc_sort', 'target_stock_packs', 'source_stock_packs'], ascending=[True, True, False])
            df = df.drop(columns=['abc_sort'])
            
            logger.info(f"Found {len(df)} priority items: {source_branch} has stock, {target_branch} needs restocking")
            return df[['item_code', 'item_name', 'source_stock_packs', 'branch_name',
                      'target_stock_packs', 'abc_class', 'stock_level_pct', 'amc_packs', 
                      'pack_size', 'last_order_date']].head(limit)
                
        except Exception as e:
            logger.error(f"Error getting priority items: {e}", exc_info=True)
            return pd.DataFrame(columns=['item_code', 'item_name', 'source_stock_packs', 'branch_name',
                                        'target_stock_packs', 'abc_class', 'stock_level_pct', 'amc_packs', 
                                        'pack_size', 'last_order_date'])

