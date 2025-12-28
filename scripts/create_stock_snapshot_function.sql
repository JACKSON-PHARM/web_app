-- ============================================================================
-- Stock Snapshot Function - Canonical PostgreSQL Function
-- ============================================================================
-- This function replaces materialized views and pandas merges
-- Single source of truth for all stock view and dashboard queries
-- ============================================================================

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
    branch_stock_pieces NUMERIC,           -- Target branch stock (converted from packs)
    source_branch_stock_pieces NUMERIC,    -- Source branch stock (converted from packs)
    pack_size NUMERIC,                     -- Pack size for conversions
    
    -- Inventory analysis (from inventory_analysis_new - authoritative)
    adjusted_amc_pieces NUMERIC,           -- Adjusted AMC in pieces
    ideal_stock_pieces NUMERIC,            -- Ideal stock in pieces
    abc_class TEXT,                        -- ABC classification
    
    -- Last order information
    last_order_date DATE,
    last_order_quantity NUMERIC,           -- In pieces
    last_order_document TEXT,
    last_order_type TEXT,                  -- 'PURCHASE', 'BRANCH', or 'HQ_INVOICE'
    
    -- Last invoice information (HQ invoices)
    last_invoice_date DATE,
    last_invoice_quantity NUMERIC,         -- In pieces
    last_invoice_document TEXT,
    
    -- Last supplier invoice information
    last_supplier_invoice_date DATE,
    last_supplier_invoice_quantity NUMERIC, -- In pieces
    last_supplier_invoice_document TEXT,
    
    -- Computed metrics
    stock_level_vs_amc NUMERIC,            -- branch_stock_pieces / adjusted_amc_pieces (percentage)
    priority_flag TEXT                     -- 'LOW', 'RECENT_ORDER', 'RECENT_INVOICE', 'NORMAL'
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
    
    -- Target branch stock
    -- IMPORTANT: Based on your requirement, stock_pieces are FULL PACKS
    -- So we convert to pieces: stock_pieces * pack_size
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
    
    -- Source branch stock
    -- IMPORTANT: Based on your requirement, stock_pieces are FULL PACKS
    -- So we convert to pieces: stock_pieces * pack_size
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
            THEN (COALESCE(ts.stock_pieces, 0) / ia.adjusted_amc) * 100
            ELSE 0
        END as stock_level_vs_amc,
        
        -- Computed: priority flag
        CASE
            -- LOW: Stock is below ideal or very low vs AMC
            WHEN COALESCE(ts.stock_pieces, 0) < COALESCE(ia.ideal_stock_pieces * 0.5, 0)
                OR (COALESCE(ia.adjusted_amc, 0) > 0 AND COALESCE(ts.stock_pieces, 0) < ia.adjusted_amc * 0.3)
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

-- Add comment
COMMENT ON FUNCTION stock_snapshot IS 
'Canonical function for stock view and dashboard. Returns complete stock snapshot including inventory analysis, orders, and invoices. All stock values returned in PIECES.';

