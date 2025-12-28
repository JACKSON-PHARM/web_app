-- ============================================================================
-- Verify Stock Schema - Check if stock_pieces is in PACKS or PIECES
-- ============================================================================
-- Run this BEFORE deploying stock_snapshot() to verify your schema
-- ============================================================================

-- Check current_stock table structure
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'current_stock'
    AND table_schema = 'public'
ORDER BY ordinal_position;

-- Sample data to verify pack/piece relationship
-- If stock_pieces is in PACKS, then stock_pieces * pack_size should give total pieces
-- If stock_pieces is in PIECES, then stock_pieces / pack_size should give packs
SELECT 
    item_code,
    item_name,
    stock_pieces,
    pack_size,
    stock_pieces * COALESCE(pack_size, 1) as calculated_total_pieces,
    CASE 
        WHEN pack_size > 0 THEN stock_pieces / pack_size 
        ELSE stock_pieces 
    END as calculated_packs
FROM current_stock
WHERE pack_size > 0
LIMIT 10;

-- Check inventory_analysis_new structure
SELECT 
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name = 'inventory_analysis_new'
    AND table_schema = 'public'
    AND column_name IN ('adjusted_amc', 'ideal_stock_pieces', 'abc_class', 'branch_name', 'company_name')
ORDER BY ordinal_position;

-- Verify order/invoice quantity units
SELECT 
    'purchase_orders' as table_name,
    item_code,
    quantity,
    document_date
FROM purchase_orders
LIMIT 5

UNION ALL

SELECT 
    'branch_orders' as table_name,
    item_code,
    quantity,
    document_date
FROM branch_orders
LIMIT 5

UNION ALL

SELECT 
    'supplier_invoices' as table_name,
    item_code,
    units as quantity,
    document_date
FROM supplier_invoices
LIMIT 5;

