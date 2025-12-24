# HQ Invoices Complete Setup Guide

## Overview

The HQ Invoices system tracks sales invoices and branch transfers from BABA DOGO HQ to Daima branches. This data is critical for procurement decisions as it shows:
- **Last invoice date per item per branch** - tells us when items were last ordered/transferred
- **Monthly quantities** - shows current month's order/transfer activity
- **Order fulfillment status** - whether orders have been processed

## Setup Steps (In Order)

### Step 1: Create the Table ✅

```bash
cd web_app
python scripts/create_hq_invoices_table.py
```

**Status**: ✅ Completed - Table created successfully

### Step 2: Migrate Existing CSV Data (Past 3 Months)

The standalone script has been fetching data to `D:\DATA ANALYTICS\HQ_DAIMA_INVOICES`. Now migrate it:

```bash
python scripts/migrate_hq_invoices_csv_to_supabase.py
```

Or specify custom paths:
```bash
python scripts/migrate_hq_invoices_csv_to_supabase.py "connection_string" "D:\DATA ANALYTICS\HQ_DAIMA_INVOICES"
```

**What this does**:
- Processes all CSV files from the standalone script's output folder
- Combines invoices and transfers into unified format
- Calculates monthly quantities (THIS_MONTH_QTY)
- Gets last invoice date per item per branch
- Loads into Supabase `hq_invoices` table

### Step 3: Load Inventory Analysis (If Not Done)

```bash
python scripts/load_inventory_analysis_to_supabase.py
```

This loads branches, ABC classes, AMC, etc. from `Inventory_Analysis.csv`.

### Step 4: Verify Integration

The fetcher is now integrated into the refresh orchestrator. It will:
- Run automatically during "Refresh All Data"
- Fetch new invoices/transfers from the last 90 days
- Update incrementally (only new documents)
- Update monthly quantities automatically

## How It Works

### Data Flow

1. **Standalone Script** (past 3 months) → CSV files → **Migration Script** → Supabase `hq_invoices`
2. **API Fetcher** (ongoing) → Fetches last 90 days → Supabase `hq_invoices` (incremental)
3. **Dashboard/Stock View Queries** → Read from `hq_invoices` → Display last invoice date

### Query Integration

The dashboard and stock view queries now include `hq_invoices` in their `last_order_date` calculations:

```sql
-- Combined orders: purchase_orders + branch_orders + hq_invoices
SELECT item_code, MAX(date) as last_order_date
FROM (
    SELECT item_code, document_date as date FROM purchase_orders WHERE ...
    UNION ALL
    SELECT item_code, document_date as date FROM branch_orders WHERE ...
    UNION ALL
    SELECT item_code, date FROM hq_invoices WHERE branch = ?
) combined_orders
GROUP BY item_code
```

### Procurement Bot Usage

The procurement bot can now read `last_order_date` from dashboard/stock view displays, which includes:
- Purchase orders (external suppliers)
- Branch orders (internal transfers)
- **HQ invoices** (sales invoices from BABA DOGO HQ) ← NEW!

## Table Schema

```sql
CREATE TABLE hq_invoices (
    id SERIAL PRIMARY KEY,
    branch TEXT NOT NULL,                    -- Destination branch
    invoice_number TEXT NOT NULL,            -- Invoice/transfer number
    item_code TEXT NOT NULL,
    item_name TEXT,
    quantity REAL DEFAULT 0,
    ref TEXT,                                -- Reference/comments
    date DATE NOT NULL,
    this_month_qty REAL DEFAULT 0,          -- Calculated monthly quantity
    document_type TEXT DEFAULT 'Invoice',    -- 'Invoice' or 'Branch Transfer'
    source_branch TEXT,                      -- Always 'BABA DOGO HQ'
    destination_branch TEXT,                 -- Same as branch
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(branch, invoice_number, item_code, date)
);
```

## Verification

After migration, verify data:

```sql
-- Check total records
SELECT COUNT(*) FROM hq_invoices;

-- Check branches
SELECT branch, COUNT(*) as count 
FROM hq_invoices 
GROUP BY branch 
ORDER BY count DESC;

-- Check last invoice dates
SELECT branch, item_code, MAX(date) as last_date
FROM hq_invoices
GROUP BY branch, item_code
ORDER BY last_date DESC
LIMIT 10;
```

## Next Steps

1. ✅ Table created
2. ⏳ **Run migration script** to load past 3 months of CSV data
3. ✅ Fetcher integrated (will run automatically on refresh)
4. ✅ Queries updated to use hq_invoices

After migration, the dashboard and stock view will show accurate last invoice dates including HQ invoices!

