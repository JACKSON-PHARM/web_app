"""
Stock View Service for PostgreSQL/Supabase
NO MATERIALIZED VIEWS - Uses stock_snapshot() function only
"""
import pandas as pd
import logging
from typing import Optional
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

class StockViewServicePostgres:
    """Service for querying stock view data - NO materialized views"""
    
    def __init__(self, db_manager):
        """Initialize with PostgreSQL database manager"""
        self.db_manager = db_manager
        self._inventory_analysis_cache = None
        
        logger.info("StockViewServicePostgres initialized - NO materialized views")
    
    def get_stock_view_data(self, branch_name: str, branch_company: str, 
                           source_branch_name: str, source_branch_company: str) -> pd.DataFrame:
        """
        Get stock view data using stock_snapshot() function
        
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
            
            # Use stock_snapshot_service (NO materialized views)
            from app.services.stock_snapshot_service import StockSnapshotService
            
            snapshot_service = StockSnapshotService(self.db_manager)
            actual_source_branch = source_branch_name if source_branch_name else branch_name
            actual_source_company = source_branch_company if source_branch_company else branch_company
            
            logger.info(f"Using stock_snapshot: target={branch_name}, source={actual_source_branch}, company={branch_company}")
            
            # Get snapshot with computed fields
            snapshot_results = snapshot_service.get_snapshot(branch_name, actual_source_branch, branch_company)
            
            if not snapshot_results:
                logger.warning(f"No stock data found for branch '{branch_name}' ({branch_company})")
                return pd.DataFrame()
            
            # Convert to DataFrame with proper column mapping
            df = pd.DataFrame(snapshot_results)
            logger.info(f"Retrieved {len(df)} items from stock_snapshot()")
            
            # CRITICAL: Deduplicate by item_code - only one record per item_code should exist
            # If duplicates exist, keep the first one (or the one with most complete data)
            if 'item_code' in df.columns:
                before_dedup = len(df)
                # Check for duplicates
                duplicates = df[df.duplicated(subset=['item_code'], keep=False)]
                if len(duplicates) > 0:
                    logger.warning(f"⚠️ Found {len(duplicates)} duplicate item_code records - deduplicating")
                    logger.warning(f"   Duplicate item_codes: {duplicates['item_code'].unique().tolist()[:10]}")
                    # Keep first occurrence of each item_code
                    df = df.drop_duplicates(subset=['item_code'], keep='first')
                    after_dedup = len(df)
                    logger.info(f"✅ Deduplicated: {before_dedup} → {after_dedup} records (removed {before_dedup - after_dedup} duplicates)")
                else:
                    logger.info(f"✅ No duplicates found - {len(df)} unique item_codes")
            
            # Map columns for compatibility with existing frontend
            column_mapping = {
                'target_stock_display': 'branch_stock_string',
                'source_stock_display': 'supplier_stock_string',
                'last_order_qty_packs': 'last_order_quantity',
                'last_invoice_qty_packs': 'last_invoice_quantity',
                'last_supplier_invoice_qty_packs': 'last_supply_quantity',
                'last_order_document': 'last_order_doc',
                'last_invoice_document': 'last_invoice_doc',
                'last_supplier_invoice_document': 'last_supply_doc',
                'last_supplier_invoice_date': 'last_supply_date',
            }
            
            # Rename columns (but keep adjusted_amc_packs for later conversion)
            # CRITICAL: stock_level_pct is already calculated in StockSnapshotService - DO NOT modify it
            for old_col, new_col in column_mapping.items():
                if old_col in df.columns:
                    df[new_col] = df[old_col]
            
            # Ensure stock_level_pct exists and is preserved (calculated in StockSnapshotService)
            # DO NOT recompute - it's already correct: (branch_stock_pieces / amc_pieces) * 100
            if 'stock_level_pct' not in df.columns:
                logger.warning("⚠️ stock_level_pct not found - should be calculated in StockSnapshotService")
                df['stock_level_pct'] = 0.0
            
            # Add GRN columns (same as supplier invoice)
            if 'last_supplier_invoice_date' in df.columns:
                df['last_grn_date'] = df['last_supplier_invoice_date']
                df['last_grn_quantity'] = df['last_supplier_invoice_qty_packs']
                df['last_grn_doc'] = df['last_supplier_invoice_document']
            
            # Convert pack_size to float first (PostgreSQL returns NUMERIC as decimal.Decimal)
            # This must be done BEFORE parsing stock_string
            if 'pack_size' in df.columns:
                df['pack_size'] = pd.to_numeric(df['pack_size'], errors='coerce').fillna(1.0).astype(float)
            
            # CRITICAL: Preserve stock_string columns EXACTLY as stored in current_stock table
            # These are DISPLAY ONLY and must NEVER be regenerated from numeric values
            if 'branch_stock_string' in df.columns:
                df['branch_stock_string'] = df['branch_stock_string'].astype(str)
                df['branch_stock_string'] = df['branch_stock_string'].replace('nan', '0W0P').replace('None', '0W0P').replace('', '0W0P')
            else:
                df['branch_stock_string'] = '0W0P'
                
            if 'supplier_stock_string' in df.columns:
                df['supplier_stock_string'] = df['supplier_stock_string'].astype(str)
                df['supplier_stock_string'] = df['supplier_stock_string'].replace('nan', '0W0P').replace('None', '0W0P').replace('', '0W0P')
            else:
                df['supplier_stock_string'] = '0W0P'
            
            # Parse stock_string to pieces (INTERNAL ONLY - for calculations, NOT for display)
            def parse_stock_string_to_pieces(stock_string: str, pack_size: float) -> float:
                """
                Parse stock_string to total pieces (INTERNAL USE ONLY)
                
                Format: "XWYP" where:
                - X = whole packs (before 'W')
                - Y = loose pieces (before 'P')
                
                Returns: total_pieces = (whole_packs × pack_size) + loose_pieces
                """
                if not stock_string or not isinstance(stock_string, str) or stock_string in ['nan', 'None', '']:
                    return 0.0
                import re
                whole_match = re.search(r'(\d+)W', stock_string)
                whole_packs = int(whole_match.group(1)) if whole_match else 0
                pieces_match = re.search(r'(\d+)P', stock_string)
                loose_pieces = int(pieces_match.group(1)) if pieces_match else 0
                
                # Calculate total pieces: (whole_packs × pack_size) + loose_pieces
                if pack_size <= 0:
                    pack_size = 1.0
                total_pieces = (float(whole_packs) * float(pack_size)) + float(loose_pieces)
                return float(total_pieces)
            
            # Calculate numeric values (INTERNAL ONLY - for sorting and calculations)
            # These are NOT used for display - stock_string is displayed as-is
            df['branch_stock'] = df.apply(
                lambda row: parse_stock_string_to_pieces(
                    str(row.get('branch_stock_string', '0W0P')),
                    float(row.get('pack_size', 1))
                ),
                axis=1
            )
            df['supplier_stock'] = df.apply(
                lambda row: parse_stock_string_to_pieces(
                    str(row.get('supplier_stock_string', '0W0P')),
                    float(row.get('pack_size', 1))
                ),
                axis=1
            )
            
            # Calculate pack values (INTERNAL ONLY - for sorting)
            df['branch_stock_packs'] = df.apply(
                lambda row: row['branch_stock'] / row['pack_size'] if row['pack_size'] > 0 else 0,
                axis=1
            ).round(2)
            df['supplier_stock_packs'] = df.apply(
                lambda row: row['supplier_stock'] / row['pack_size'] if row['pack_size'] > 0 else 0,
                axis=1
            ).round(2)
            
            # Add sort aliases (numeric values for sorting, but display uses stock_string)
            df['branch_stock_sort'] = df['branch_stock_packs']  # Alias for numeric sorting
            df['supplier_stock_sort'] = df['supplier_stock_packs']  # Alias for numeric sorting
            
            # GROUND TRUTH: inventory_analysis_new.adjusted_amc is stored in PACKS
            # Display AMC in packs directly - do NOT divide by pack_size
            if 'adjusted_amc_packs' in df.columns:
                # adjusted_amc_packs is already in packs - display directly
                df['amc_packs'] = pd.to_numeric(df['adjusted_amc_packs'], errors='coerce').fillna(0.0).astype(float)
                df['amc'] = df['amc_packs']  # Alias for compatibility
                # amc_pieces is calculated in StockSnapshotService for stock_level_pct calculation
                # If not already present, calculate it here for compatibility
                if 'amc_pieces' not in df.columns:
                    df['amc_pieces'] = df.apply(
                        lambda row: row['amc_packs'] * row['pack_size'] if row['pack_size'] > 0 else 0.0,
                        axis=1
                    ).astype(float)
            elif 'amc_pieces' in df.columns:
                # If amc_pieces exists from StockSnapshotService, convert back to packs for display
                df['amc_pieces'] = pd.to_numeric(df['amc_pieces'], errors='coerce').fillna(0.0).astype(float)
                # Convert pieces to packs for display: amc_packs = amc_pieces / pack_size
                df['amc_packs'] = df.apply(
                    lambda row: (row['amc_pieces'] / row['pack_size']) if row['pack_size'] > 0 else 0,
                    axis=1
                ).round(2)
                df['amc'] = df['amc_packs']  # Alias for compatibility
            else:
                df['amc_packs'] = 0.0
                df['amc'] = 0.0
                df['amc_pieces'] = 0.0
            
            # Add missing columns for compatibility
            df['unit_price'] = 0.0
            df['stock_value'] = 0.0
            df['stock_comment'] = df.get('stock_recommendation', '')
            
            # Ensure numeric types (pack_size already converted above)
            # Include sort columns for numeric sorting
            # CRITICAL: stock_level_pct is READ-ONLY - already calculated in StockSnapshotService
            # DO NOT recompute or modify stock_level_pct here - it's (branch_stock_pieces / amc_pieces) * 100
            for col in ['amc', 'amc_pieces', 'last_order_quantity', 
                       'last_invoice_quantity', 'last_supply_quantity', 'ideal_stock_pieces',
                       'branch_stock', 'supplier_stock', 'branch_stock_packs', 'supplier_stock_packs',
                       'branch_stock_sort', 'supplier_stock_sort']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(float)
            
            # Ensure stock_level_pct is numeric but DO NOT recalculate
            # It's already calculated correctly in StockSnapshotService: (branch_stock_pieces / amc_pieces) * 100
            if 'stock_level_pct' in df.columns:
                df['stock_level_pct'] = pd.to_numeric(df['stock_level_pct'], errors='coerce').fillna(0.0).astype(float)
            
            # CRITICAL: Ensure stock_string columns are preserved as strings (not converted to numeric)
            # These are DISPLAY ONLY and must NEVER be regenerated
            if 'branch_stock_string' in df.columns:
                df['branch_stock_string'] = df['branch_stock_string'].astype(str).replace('nan', '0W0P').replace('None', '0W0P').replace('', '0W0P')
            if 'supplier_stock_string' in df.columns:
                df['supplier_stock_string'] = df['supplier_stock_string'].astype(str).replace('nan', '0W0P').replace('None', '0W0P').replace('', '0W0P')
            
            # Log sample data for debugging (verify stock_level_pct calculation)
            if len(df) > 0:
                sample = df.iloc[0]
                logger.info(f"✅ Successfully processed {len(df)} items")
                logger.info(f"   Sample: item_code={sample.get('item_code')}, "
                           f"branch_stock_string={sample.get('branch_stock_string')}, "
                           f"branch_stock={sample.get('branch_stock')} pieces, "
                           f"branch_stock_packs={sample.get('branch_stock_packs')}, "
                           f"amc_packs={sample.get('amc_packs')} packs (from DB), "
                           f"amc_pieces={sample.get('amc_pieces')} pieces (calculated), "
                           f"stock_level_pct={sample.get('stock_level_pct')}% (READ-ONLY from StockSnapshotService)")
                
                # Verify calculation for debugging
                branch_pieces = sample.get('branch_stock', 0)
                amc_pieces = sample.get('amc_pieces', 0)
                if amc_pieces > 0:
                    expected_pct = (branch_pieces / amc_pieces) * 100
                    actual_pct = sample.get('stock_level_pct', 0)
                    if abs(expected_pct - actual_pct) > 0.01:
                        logger.warning(f"   ⚠️ Stock level mismatch: expected={expected_pct:.2f}%, actual={actual_pct:.2f}%")
            else:
                logger.warning("⚠️ No data returned from stock_snapshot()")
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Error getting stock view data: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return pd.DataFrame()

