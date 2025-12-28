-- ============================================================================
-- Indexes for Stock Snapshot Function Performance
-- ============================================================================
-- These indexes optimize the stock_snapshot() function queries
-- ============================================================================

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

-- Composite indexes for DISTINCT ON queries (optimize last order/invoice lookups)
CREATE INDEX IF NOT EXISTS idx_purchase_orders_item_branch_date_doc 
    ON purchase_orders(item_code, branch, company, document_date DESC, document_number DESC);
    
CREATE INDEX IF NOT EXISTS idx_branch_orders_item_dest_date_doc 
    ON branch_orders(item_code, destination_branch, company, document_date DESC, document_number DESC);
    
CREATE INDEX IF NOT EXISTS idx_hq_invoices_item_branch_date_doc 
    ON hq_invoices(item_code, branch, date DESC, invoice_number DESC);
    
CREATE INDEX IF NOT EXISTS idx_supplier_invoices_item_branch_date_doc 
    ON supplier_invoices(item_code, branch, company, document_date DESC, document_number DESC);

-- Analyze tables after creating indexes
ANALYZE current_stock;
ANALYZE inventory_analysis_new;
ANALYZE purchase_orders;
ANALYZE branch_orders;
ANALYZE hq_invoices;
ANALYZE supplier_invoices;

