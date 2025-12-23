# Supabase Migration Plan - Minimize Database for Procurement

## Goal
Reduce database from 600MB to <500MB to fit Supabase free tier, keeping only procurement-essential data.

## Data Retention Policy

### ✅ KEEP (Essential for Procurement):
1. **Current Stock** - All records (needed for stock reports)
2. **Recent Orders** - Last 3 months only
   - `purchase_orders` (last 3 months)
   - `branch_orders` (last 3 months)
3. **Recent Supplier Invoices** - Last 3 months only
   - `supplier_invoices` (last 3 months)
4. **Inventory Analysis** - All records (ABC class, AMC)
   - `inventory_analysis` or CSV data
5. **Item Master** - All records (item codes, names, pack sizes)
   - `items` or `master_inventory`

### ❌ REMOVE (Not needed for procurement):
1. **Old Orders** - Older than 3 months
2. **Old Invoices** - Older than 3 months
3. **Sales Data** - Not needed for procurement
4. **GRN Data** - Can be derived from invoices
5. **Historical Stock Snapshots** - Keep only current stock
6. **Old Stock Data** - Keep only `current_stock`, remove `stock_data` snapshots

## Database Optimization Strategy

### Step 1: Clean Existing SQLite Database
```sql
-- Delete old orders (keep only last 3 months)
DELETE FROM purchase_orders 
WHERE document_date < date('now', '-3 months');

DELETE FROM branch_orders 
WHERE document_date < date('now', '-3 months');

-- Delete old supplier invoices
DELETE FROM supplier_invoices 
WHERE invoice_date < date('now', '-3 months');

-- Delete old stock snapshots (keep only current_stock)
DELETE FROM stock_data 
WHERE snapshot_date < date('now', '-1 month');

-- Remove sales data (not needed for procurement)
DROP TABLE IF EXISTS sales;
DROP TABLE IF EXISTS sales_details;

-- Remove GRN if not needed
-- DROP TABLE IF EXISTS grn;
```

### Step 2: Optimize Tables
```sql
-- Add indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_purchase_orders_date 
ON purchase_orders(document_date DESC);

CREATE INDEX IF NOT EXISTS idx_branch_orders_date 
ON branch_orders(document_date DESC);

CREATE INDEX IF NOT EXISTS idx_supplier_invoices_date 
ON supplier_invoices(invoice_date DESC);

CREATE INDEX IF NOT EXISTS idx_current_stock_branch 
ON current_stock(branch, company, item_code);

-- Vacuum database to reclaim space
VACUUM;
```

### Step 3: Estimate Size After Cleanup
- Current Stock: ~50MB (all branches, all items)
- Orders (3 months): ~100MB (instead of 2+ years)
- Invoices (3 months): ~50MB (instead of 2+ years)
- Inventory Analysis: ~10MB
- Item Master: ~5MB
- **Total: ~215MB** ✅ Fits in Supabase free tier (500MB)

## Migration Steps

### Phase 1: Clean SQLite Database
1. Create cleanup script
2. Run cleanup (remove old data)
3. Verify size < 500MB
4. Test app functionality

### Phase 2: Setup Supabase
1. Create Supabase project
2. Get connection string
3. Create tables in PostgreSQL

### Phase 3: Migrate Data
1. Export cleaned SQLite data
2. Convert to PostgreSQL format
3. Import to Supabase
4. Verify data integrity

### Phase 4: Update App
1. Install PostgreSQL driver (`psycopg2`)
2. Update database connection
3. Update queries (SQLite → PostgreSQL)
4. Test all features

## Implementation

Let me create the cleanup script and migration tools.

