CREATE OR REPLACE FUNCTION stock_snapshot(
    p_target_branch TEXT,
    p_source_branch TEXT,
    p_company TEXT
)
RETURNS TABLE (
    item_code TEXT,
    item_name TEXT,
    pack_size NUMERIC,
    adjusted_amc_packs NUMERIC,
    ideal_stock_pieces NUMERIC,
    abc_class TEXT,
    target_stock_display TEXT,
    source_stock_display TEXT,
    last_order_date DATE,
    last_order_qty_packs NUMERIC,
    last_order_document TEXT,
    last_order_type TEXT,
    last_invoice_date DATE,
    last_invoice_qty_packs NUMERIC,
    last_invoice_document TEXT,
    last_supplier_invoice_date DATE,
    last_supplier_invoice_qty_packs NUMERIC,
    last_supplier_invoice_document TEXT
) 
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN QUERY
    WITH 
    inventory_analysis AS (
        SELECT DISTINCT ON (ia.item_code)
            ia.item_code,
            ia.item_name,
            ia.adjusted_amc,
            ia.ideal_stock_pieces,
            ia.abc_class
        FROM inventory_analysis_new ia
        WHERE ia.branch_name = p_target_branch 
            AND ia.company_name = p_company
        ORDER BY ia.item_code, ia.adjusted_amc DESC NULLS LAST
        -- If multiple records exist for same item_code, prefer the one with highest adjusted_amc
    ),
    target_stock AS (
        SELECT DISTINCT ON (tgt.item_code)
            tgt.item_code,
            tgt.item_name,
            tgt.stock_string,
            tgt.pack_size
        FROM current_stock tgt
        WHERE tgt.branch = p_target_branch 
            AND tgt.company = p_company
        ORDER BY tgt.item_code, tgt.stock_pieces DESC NULLS LAST
        -- If multiple records exist for same item_code, prefer the one with highest stock
    ),
    source_stock AS (
        SELECT DISTINCT ON (src.item_code)
            src.item_code,
            src.stock_string,
            src.pack_size
        FROM current_stock src
        WHERE src.branch = p_source_branch 
            AND src.company = p_company
        ORDER BY src.item_code, src.stock_pieces DESC NULLS LAST
        -- If multiple records exist for same item_code, prefer the one with highest stock
    ),
    all_orders AS (
        SELECT 
            po.item_code,
            po.document_date,
            po.document_number,
            po.quantity,
            'PURCHASE' as order_type
        FROM purchase_orders po
        WHERE po.branch = p_target_branch 
            AND po.company = p_company
        
        UNION ALL
        
        SELECT 
            bo.item_code,
            bo.document_date,
            bo.document_number,
            bo.quantity,
            'BRANCH' as order_type
        FROM branch_orders bo
        WHERE bo.destination_branch = p_target_branch 
            AND bo.company = p_company
        
        UNION ALL
        
        SELECT 
            hi.item_code,
            hi.date as document_date,
            hi.invoice_number as document_number,
            hi.quantity,
            'HQ_INVOICE' as order_type
        FROM hq_invoices hi
        WHERE hi.branch = p_target_branch
            AND p_company = 'NILA'
    ),
    last_order_info AS (
        SELECT DISTINCT ON (ao.item_code)
            ao.item_code,
            ao.document_date as last_order_date,
            ao.document_number as last_order_document,
            ao.quantity as last_order_qty_packs,
            ao.order_type as last_order_type
        FROM all_orders ao
        ORDER BY ao.item_code, ao.document_date DESC, ao.document_number DESC
    ),
    last_invoice_info AS (
        SELECT DISTINCT ON (hi2.item_code)
            hi2.item_code,
            hi2.date as last_invoice_date,
            hi2.invoice_number as last_invoice_document,
            hi2.quantity as last_invoice_qty_packs
        FROM hq_invoices hi2
        WHERE hi2.branch = p_target_branch
            AND p_company = 'NILA'
        ORDER BY hi2.item_code, hi2.date DESC, hi2.invoice_number DESC
    ),
    last_supplier_invoice_info AS (
        SELECT DISTINCT ON (si.item_code)
            si.item_code,
            si.document_date as last_supplier_invoice_date,
            si.document_number as last_supplier_invoice_document,
            si.units as last_supplier_invoice_qty_packs
        FROM supplier_invoices si
        WHERE si.branch = p_target_branch 
            AND si.company = p_company
        ORDER BY si.item_code, si.document_date DESC, si.document_number DESC
    )
    SELECT 
        ia.item_code,
        -- Prioritize stock table item_name over inventory_analysis if inventory_analysis has "NO SALES"
        CASE 
            WHEN ia.item_name IS NULL OR UPPER(TRIM(ia.item_name)) = 'NO SALES' THEN 
                COALESCE(tgt.item_name, src.item_name, '')
            ELSE 
                COALESCE(ia.item_name, tgt.item_name, src.item_name, '')
        END as item_name,
        COALESCE(tgt.pack_size, src.pack_size, 1)::NUMERIC as pack_size,
        COALESCE(ia.adjusted_amc, 0)::NUMERIC as adjusted_amc_packs,
        COALESCE(ia.ideal_stock_pieces, 0)::NUMERIC as ideal_stock_pieces,
        COALESCE(ia.abc_class, '') as abc_class,
        COALESCE(tgt.stock_string, '0W0P') as target_stock_display,
        COALESCE(src.stock_string, '0W0P') as source_stock_display,
        loi.last_order_date::DATE,
        COALESCE(loi.last_order_qty_packs, 0)::NUMERIC as last_order_qty_packs,
        loi.last_order_document,
        loi.last_order_type,
        lii.last_invoice_date::DATE,
        COALESCE(lii.last_invoice_qty_packs, 0)::NUMERIC as last_invoice_qty_packs,
        lii.last_invoice_document,
        lsii.last_supplier_invoice_date::DATE,
        COALESCE(lsii.last_supplier_invoice_qty_packs, 0)::NUMERIC as last_supplier_invoice_qty_packs,
        lsii.last_supplier_invoice_document
    FROM inventory_analysis ia
    LEFT JOIN target_stock tgt ON ia.item_code = tgt.item_code
    LEFT JOIN source_stock src ON ia.item_code = src.item_code
    LEFT JOIN last_order_info loi ON ia.item_code = loi.item_code
    LEFT JOIN last_invoice_info lii ON ia.item_code = lii.item_code
    LEFT JOIN last_supplier_invoice_info lsii ON ia.item_code = lsii.item_code
    ORDER BY ia.item_code;
END;
$$;
