# HQ Invoices Setup Guide

This guide explains how to set up the HQ Invoices system that tracks sales invoices and branch transfers from BABA DOGO HQ.

## Overview

The `hq_invoices` table stores:
- **Sales invoices** from BABA DOGO HQ to Daima branches
- **Branch transfers** from BABA DOGO HQ to other branches
- **Last invoice date per item per branch** (for procurement decisions)
- **Monthly quantities** (THIS_MONTH_QTY) for current month

## Setup Steps

### 1. Create the Table

```bash
cd web_app
python scripts/create_hq_invoices_table.py
```

This creates the `hq_invoices` table in Supabase with:
- Unique constraint on (branch, invoice_number, item_code, date)
- Indexes for fast queries
- Columns: branch, invoice_number, item_code, item_name, quantity, ref, date, this_month_qty, document_type, etc.

### 2. Load Inventory Analysis (if not done)

```bash
python scripts/load_inventory_analysis_to_supabase.py
```

This loads branches and other analysis data.

### 3. Fetch HQ Invoices Data

The fetcher is integrated into the refresh system. It will:
- Fetch invoices and transfers from the last 90 days (or specified range)
- Store them incrementally (only new documents)
- Update monthly quantities automatically

## Integration with Refresh System

Add to `database_fetcher_orchestrator.py`:

```python
from scripts.data_fetchers.database_hq_invoices_fetcher import DatabaseHQInvoicesFetcher

# In the refresh method:
hq_invoices_fetcher = DatabaseHQInvoicesFetcher(db_manager, cred_manager)
hq_invoices_fetcher.fetch_data()  # Fetches last 90 days by default
```

## Usage

### Query Last Invoice Date Per Item Per Branch

```sql
SELECT 
    branch,
    item_code,
    item_name,
    MAX(date) as last_invoice_date,
    SUM(this_month_qty) as this_month_total
FROM hq_invoices
GROUP BY branch, item_code, item_name
ORDER BY branch, item_code;
```

### Get Items Not Invoiced Recently

```sql
SELECT 
    branch,
    item_code,
    item_name,
    MAX(date) as last_invoice_date,
    CURRENT_DATE - MAX(date) as days_since_last_invoice
FROM hq_invoices
GROUP BY branch, item_code, item_name
HAVING MAX(date) < CURRENT_DATE - INTERVAL '30 days'
ORDER BY days_since_last_invoice DESC;
```

## Data Processing

The fetcher automatically:
1. Fetches invoices and transfers from API
2. Transforms them to unified format
3. Stores in `hq_invoices` table
4. Updates `this_month_qty` for current month records
5. Uses incremental loading (only new documents)

## Table Schema

```sql
CREATE TABLE hq_invoices (
    id SERIAL PRIMARY KEY,
    branch TEXT NOT NULL,
    invoice_number TEXT NOT NULL,
    item_code TEXT NOT NULL,
    item_name TEXT,
    quantity REAL DEFAULT 0,
    ref TEXT,
    date DATE NOT NULL,
    this_month_qty REAL DEFAULT 0,
    document_type TEXT DEFAULT 'Invoice',
    source_branch TEXT,
    destination_branch TEXT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(branch, invoice_number, item_code, date)
);
```

## Notes

- The fetcher filters for Daima branches only
- Uses incremental loading (checks for existing documents)
- Updates monthly quantities automatically
- Works with both PostgreSQL (Supabase) and SQLite

