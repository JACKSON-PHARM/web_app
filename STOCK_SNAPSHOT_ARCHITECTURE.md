# Stock Snapshot Architecture - PostgreSQL-First Design

## Overview

This document defines a **single canonical SQL function** that serves as the source of truth for all stock view and dashboard queries. No pandas, no materialized views, no CSV merges.

## Table Schema Assumptions

Based on codebase analysis:

- **current_stock**: `stock_pieces` = FULL PACKS (not pieces), `pack_size` provided separately
- **inventory_analysis_new**: `adjusted_amc` = PIECES, `ideal_stock_pieces` = PIECES
- **purchase_orders**: `quantity` = pieces (verify in your schema)
- **branch_orders**: `quantity` = pieces (verify in your schema)
- **supplier_invoices**: `units` = pieces (verify in your schema)
- **hq_invoices**: `quantity` = pieces (verify in your schema)

## Core SQL Function: `stock_snapshot()`

```sql
-- Drop existing function if exists
DROP FUNCTION IF EXISTS stock_snapshot(text, text, text);

-- Create the canonical stock snapshot function
CREATE OR REPLACE FUNCTION stock_snapshot(
    p_target_branch TEXT,
    p_source_branch TEXT,
    p_company TEXT
)
RETURNS TABLE (
    -- Item identification
    item_code TEXT,
    item_name TEXT,
    
    -- Stock levels (all in PIECES after conversion)
    branch_stock_pieces NUMERIC,      -- Target branch stock (converted from packs)
    source_branch_stock_pieces NUMERIC, -- Source branch stock (converted from packs)
    pack_size NUMERIC,                 -- Pack size for conversions
    
    -- Inventory analysis (from inventory_analysis_new - authoritative)
    adjusted_amc_pieces NUMERIC,       -- Adjusted AMC in pieces
    ideal_stock_pieces NUMERIC,        -- Ideal stock in pieces
    abc_class TEXT,                    -- ABC classification
    
    -- Last order information
    last_order_date DATE,
    last_order_quantity NUMERIC,       -- In pieces
    last_order_document TEXT,
    last_order_type TEXT,              -- 'PURCHASE', 'BRANCH', or 'HQ_INVOICE'
    
    -- Last invoice information (HQ invoices)
    last_invoice_date DATE,
    last_invoice_quantity NUMERIC,     -- In pieces
    last_invoice_document TEXT,
    
    -- Last supplier invoice information
    last_supplier_invoice_date DATE,
    last_supplier_invoice_quantity NUMERIC, -- In pieces
    last_supplier_invoice_document TEXT,
    
    -- Computed metrics
    stock_level_vs_amc NUMERIC,       -- branch_stock_pieces / adjusted_amc_pieces (percentage)
    priority_flag TEXT                 -- 'LOW', 'RECENT_ORDER', 'RECENT_INVOICE', 'NORMAL'
) 
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN QUERY
    WITH 
    -- Get all unique items (from current_stock or inventory_analysis_new)
    unique_items AS (
        SELECT DISTINCT 
            COALESCE(cs.item_code, ia.item_code) as item_code,
            MAX(COALESCE(cs.item_name, '')) as item_name
        FROM current_stock cs
        FULL OUTER JOIN inventory_analysis_new ia 
            ON cs.item_code = ia.item_code
        WHERE (cs.company = p_company OR ia.company_name = p_company)
        GROUP BY COALESCE(cs.item_code, ia.item_code)
    ),
    
    -- Target branch stock (convert packs to pieces)
    target_stock AS (
        SELECT 
            item_code,
            item_name,
            stock_pieces * COALESCE(pack_size, 1) as stock_pieces,  -- Convert packs to pieces
            COALESCE(pack_size, 1) as pack_size
        FROM current_stock
        WHERE branch = p_target_branch 
            AND company = p_company
    ),
    
    -- Source branch stock (convert packs to pieces)
    source_stock AS (
        SELECT 
            item_code,
            stock_pieces * COALESCE(pack_size, 1) as stock_pieces,  -- Convert packs to pieces
            COALESCE(pack_size, 1) as pack_size
        FROM current_stock
        WHERE branch = p_source_branch 
            AND company = p_company
    ),
    
    -- Inventory analysis (authoritative source for AMC and ABC)
    inventory_analysis AS (
        SELECT 
            item_code,
            adjusted_amc,
            ideal_stock_pieces,
            abc_class
        FROM inventory_analysis_new
        WHERE branch_name = p_target_branch 
            AND company_name = p_company
    ),
    
    -- Last order from any source (purchase_orders, branch_orders, hq_invoices)
    all_orders AS (
        -- Purchase orders
        SELECT 
            item_code,
            document_date,
            document_number,
            quantity,
            'PURCHASE' as order_type
        FROM purchase_orders
        WHERE branch = p_target_branch 
            AND company = p_company
        
        UNION ALL
        
        -- Branch orders (destination_branch is target)
        SELECT 
            item_code,
            document_date,
            document_number,
            quantity,
            'BRANCH' as order_type
        FROM branch_orders
        WHERE destination_branch = p_target_branch 
            AND company = p_company
        
        UNION ALL
        
        -- HQ invoices (for NILA company)
        SELECT 
            item_code,
            date as document_date,
            invoice_number as document_number,
            quantity,
            'HQ_INVOICE' as order_type
        FROM hq_invoices
        WHERE branch = p_target_branch
            AND p_company = 'NILA'  -- Only for NILA
    ),
    
    last_order_info AS (
        SELECT DISTINCT ON (item_code)
            item_code,
            document_date as last_order_date,
            document_number as last_order_document,
            quantity as last_order_quantity,
            order_type as last_order_type
        FROM all_orders
        ORDER BY item_code, document_date DESC, document_number DESC
    ),
    
    -- Last HQ invoice
    last_invoice_info AS (
        SELECT DISTINCT ON (item_code)
            item_code,
            date as last_invoice_date,
            invoice_number as last_invoice_document,
            quantity as last_invoice_quantity
        FROM hq_invoices
        WHERE branch = p_target_branch
            AND p_company = 'NILA'  -- Only for NILA
        ORDER BY item_code, date DESC, invoice_number DESC
    ),
    
    -- Last supplier invoice
    last_supplier_invoice_info AS (
        SELECT DISTINCT ON (item_code)
            item_code,
            document_date as last_supplier_invoice_date,
            document_number as last_supplier_invoice_document,
            units as last_supplier_invoice_quantity
        FROM supplier_invoices
        WHERE branch = p_target_branch 
            AND company = p_company
        ORDER BY item_code, document_date DESC, document_number DESC
    )
    
    SELECT 
        ui.item_code,
        ui.item_name,
        
        -- Stock levels (in pieces)
        COALESCE(ts.stock_pieces, 0) as branch_stock_pieces,
        COALESCE(ss.stock_pieces, 0) as source_branch_stock_pieces,
        COALESCE(ts.pack_size, ss.pack_size, 1) as pack_size,
        
        -- Inventory analysis (authoritative)
        COALESCE(ia.adjusted_amc, 0) as adjusted_amc_pieces,
        COALESCE(ia.ideal_stock_pieces, 0) as ideal_stock_pieces,
        COALESCE(ia.abc_class, '') as abc_class,
        
        -- Last order
        loi.last_order_date,
        COALESCE(loi.last_order_quantity, 0) as last_order_quantity,
        loi.last_order_document,
        loi.last_order_type,
        
        -- Last invoice
        lii.last_invoice_date,
        COALESCE(lii.last_invoice_quantity, 0) as last_invoice_quantity,
        lii.last_invoice_document,
        
        -- Last supplier invoice
        lsii.last_supplier_invoice_date,
        COALESCE(lsii.last_supplier_invoice_quantity, 0) as last_supplier_invoice_quantity,
        lsii.last_supplier_invoice_document,
        
        -- Computed: stock level vs AMC (percentage)
        CASE 
            WHEN COALESCE(ia.adjusted_amc, 0) > 0 
            THEN (COALESCE(ts.stock_pieces, 0) / ia.adjusted_amc_pieces) * 100
            ELSE 0
        END as stock_level_vs_amc,
        
        -- Computed: priority flag
        CASE
            -- LOW: Stock is below ideal or very low vs AMC
            WHEN COALESCE(ts.stock_pieces, 0) < COALESCE(ia.ideal_stock_pieces * 0.5, 0)
                OR (COALESCE(ia.adjusted_amc, 0) > 0 AND COALESCE(ts.stock_pieces, 0) < ia.adjusted_amc_pieces * 0.3)
            THEN 'LOW'
            
            -- RECENT_ORDER: Ordered in last 7 days
            WHEN loi.last_order_date >= CURRENT_DATE - INTERVAL '7 days'
            THEN 'RECENT_ORDER'
            
            -- RECENT_INVOICE: Received invoice in last 7 days
            WHEN lii.last_invoice_date >= CURRENT_DATE - INTERVAL '7 days'
                OR lsii.last_supplier_invoice_date >= CURRENT_DATE - INTERVAL '7 days'
            THEN 'RECENT_INVOICE'
            
            -- NORMAL: Everything else
            ELSE 'NORMAL'
        END as priority_flag
        
    FROM unique_items ui
    LEFT JOIN target_stock ts ON ui.item_code = ts.item_code
    LEFT JOIN source_stock ss ON ui.item_code = ss.item_code
    LEFT JOIN inventory_analysis ia ON ui.item_code = ia.item_code
    LEFT JOIN last_order_info loi ON ui.item_code = loi.item_code
    LEFT JOIN last_invoice_info lii ON ui.item_code = lii.item_code
    LEFT JOIN last_supplier_invoice_info lsii ON ui.item_code = lsii.item_code
    ORDER BY ui.item_code;
END;
$$;
```

## Required Indexes

```sql
-- Current stock indexes (for fast branch/company lookups)
CREATE INDEX IF NOT EXISTS idx_current_stock_branch_company 
    ON current_stock(branch, company, item_code);
CREATE INDEX IF NOT EXISTS idx_current_stock_item_code 
    ON current_stock(item_code);

-- Inventory analysis indexes (authoritative source)
CREATE INDEX IF NOT EXISTS idx_inventory_analysis_branch_company 
    ON inventory_analysis_new(branch_name, company_name, item_code);
CREATE INDEX IF NOT EXISTS idx_inventory_analysis_item_code 
    ON inventory_analysis_new(item_code);

-- Order indexes (for last order lookups)
CREATE INDEX IF NOT EXISTS idx_purchase_orders_branch_company_date 
    ON purchase_orders(branch, company, document_date DESC, item_code);
CREATE INDEX IF NOT EXISTS idx_branch_orders_dest_company_date 
    ON branch_orders(destination_branch, company, document_date DESC, item_code);
CREATE INDEX IF NOT EXISTS idx_hq_invoices_branch_date 
    ON hq_invoices(branch, date DESC, item_code);

-- Supplier invoice indexes
CREATE INDEX IF NOT EXISTS idx_supplier_invoices_branch_company_date 
    ON supplier_invoices(branch, company, document_date DESC, item_code);

-- Composite indexes for DISTINCT ON queries
CREATE INDEX IF NOT EXISTS idx_purchase_orders_item_branch_date_doc 
    ON purchase_orders(item_code, branch, company, document_date DESC, document_number DESC);
CREATE INDEX IF NOT EXISTS idx_branch_orders_item_dest_date_doc 
    ON branch_orders(item_code, destination_branch, company, document_date DESC, document_number DESC);
CREATE INDEX IF NOT EXISTS idx_hq_invoices_item_branch_date_doc 
    ON hq_invoices(item_code, branch, date DESC, invoice_number DESC);
CREATE INDEX IF NOT EXISTS idx_supplier_invoices_item_branch_date_doc 
    ON supplier_invoices(item_code, branch, company, document_date DESC, document_number DESC);
```

## Python Query Examples

### Stock View Service

```python
def get_stock_snapshot(self, target_branch: str, source_branch: str, company: str) -> List[Dict]:
    """Get complete stock snapshot using canonical function"""
    conn = self.db_manager.get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cursor.execute("""
            SELECT * FROM stock_snapshot(%s, %s, %s)
        """, (target_branch, source_branch, company))
        
        results = cursor.fetchall()
        return [dict(row) for row in results]
    finally:
        cursor.close()
        self.db_manager.put_connection(conn)
```

### Dashboard Service - Priority Items

```python
def get_priority_items(self, source_branch: str, target_branch: str, company: str, 
                      priority_only: bool = True, days: int = 7) -> List[Dict]:
    """Get priority items using stock_snapshot function"""
    conn = self.db_manager.get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        query = """
            SELECT * FROM stock_snapshot(%s, %s, %s)
            WHERE 1=1
        """
        params = [target_branch, source_branch, company]
        
        if priority_only:
            query += " AND priority_flag IN ('LOW', 'RECENT_ORDER', 'RECENT_INVOICE')"
        
        # Filter by recent activity if needed
        if days:
            query += """
                AND (
                    last_order_date >= CURRENT_DATE - INTERVAL '%s days'
                    OR last_invoice_date >= CURRENT_DATE - INTERVAL '%s days'
                    OR last_supplier_invoice_date >= CURRENT_DATE - INTERVAL '%s days'
                )
            """
            params.extend([days, days, days])
        
        query += " ORDER BY priority_flag, item_code"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        return [dict(row) for row in results]
    finally:
        cursor.close()
        self.db_manager.put_connection(conn)
```

### Dashboard Service - New Arrivals

```python
def get_new_arrivals(self, branch: str, company: str, days: int = 7) -> List[Dict]:
    """Get new arrivals using stock_snapshot function"""
    conn = self.db_manager.get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cursor.execute("""
            SELECT * FROM stock_snapshot(%s, %s, %s)
            WHERE (
                last_order_date >= CURRENT_DATE - INTERVAL '%s days'
                OR last_invoice_date >= CURRENT_DATE - INTERVAL '%s days'
                OR last_supplier_invoice_date >= CURRENT_DATE - INTERVAL '%s days'
            )
            ORDER BY 
                COALESCE(last_order_date, last_invoice_date, last_supplier_invoice_date) DESC,
                item_code
        """, (branch, branch, company, days, days, days))
        
        results = cursor.fetchall()
        return [dict(row) for row in results]
    finally:
        cursor.close()
        self.db_manager.put_connection(conn)
```

## Migration Plan

### Step 1: Deploy SQL Function and Indexes

```sql
-- Run the stock_snapshot() function creation script
-- Run the index creation script
```

### Step 2: Update Python Services (Gradual Migration)

1. **Create new service methods** that use `stock_snapshot()`:
   - `StockViewServicePostgres.get_stock_snapshot()`
   - `DashboardService.get_priority_items_v2()`
   - `DashboardService.get_new_arrivals_v2()`

2. **Add feature flag** to switch between old and new:
   ```python
   USE_STOCK_SNAPSHOT = os.getenv('USE_STOCK_SNAPSHOT', 'false').lower() == 'true'
   ```

3. **Test new methods** in parallel with old ones

4. **Switch over** when validated

### Step 3: Remove Old Code

1. Remove pandas merges from `dashboard_service.py`
2. Remove materialized view logic from `refresh_service.py`
3. Remove CSV fallbacks
4. Simplify `stock_view_service_postgres.py`

### Step 4: Drop Materialized Views

```sql
-- Only after confirming new function works
DROP MATERIALIZED VIEW IF EXISTS stock_view_materialized CASCADE;
DROP MATERIALIZED VIEW IF EXISTS priority_items_materialized CASCADE;
DROP FUNCTION IF EXISTS refresh_materialized_views() CASCADE;
```

## Performance Considerations

1. **Function is STABLE**: PostgreSQL can cache results within a transaction
2. **Indexes**: All lookups are indexed for fast joins
3. **DISTINCT ON**: Efficient for getting latest records
4. **No materialized views**: Always fresh data, no refresh overhead

## Verification Queries

```sql
-- Test the function
SELECT * FROM stock_snapshot('BABA DOGO HQ', 'BABA DOGO HQ', 'NILA') LIMIT 10;

-- Check execution plan
EXPLAIN ANALYZE 
SELECT * FROM stock_snapshot('BABA DOGO HQ', 'BABA DOGO HQ', 'NILA');

-- Verify indexes exist
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename IN ('current_stock', 'inventory_analysis_new', 'purchase_orders', 
                    'branch_orders', 'hq_invoices', 'supplier_invoices')
ORDER BY tablename, indexname;
```

## Notes

1. **Pack/Piece Conversion**: The function assumes `current_stock.stock_pieces` is in PACKS and converts to pieces. Verify this matches your actual data.

2. **HQ Invoices**: Only included for NILA company. Adjust if DAIMA also has HQ invoices.

3. **Priority Logic**: Adjust thresholds in the `CASE` statement based on business rules.

4. **Performance**: For very large datasets, consider adding `LIMIT` or pagination in the Python layer, not in SQL.

