# Data Retention Policy for Supabase Free Tier

## Overview

To stay within Supabase free tier limits, we've implemented a **30-day data retention policy** for time-based data. This ensures the database stays manageable and within free tier constraints.

## Retention Rules

### 1. **Time-Based Data (30 Days Retention)**
The following tables only keep data from the **last 30 days**:
- `supplier_invoices` - Supplier invoice records
- `grn` - Goods Received Notes
- `purchase_orders` - Purchase order records
- `branch_orders` - Branch order records
- `hq_invoices` - HQ invoice and transfer records

**How it works:**
- Fetchers automatically fetch only the last 30 days from the API
- Old data (older than 30 days) is automatically cleaned up after each fetch
- No duplicates or gaps - fetchers ensure complete coverage of the 30-day window

### 2. **Current Stock (Most Recent Only)**
- `current_stock` - Only the **most recent version** is kept
- On each refresh, old stock data is **automatically deleted** before inserting new data
- This ensures we always have the latest stock position without accumulating historical snapshots

### 3. **Inventory Analysis (Constant)**
- `inventory_analysis` - **No cleanup** - this data remains constant
- Contains branch analysis, ABC classes, AMC calculations, etc.
- Loaded once and maintained as reference data

## Implementation Details

### Updated Fetchers

All fetchers now use a **30-day window** instead of fetching from year start:

1. **GRN Fetcher** (`database_grn_fetcher.py`)
   - Fetches GRNs from last 30 days
   - Previously: Year start to today
   - Now: `(today - 30 days) to today`

2. **Orders Fetcher** (`database_orders_fetcher.py`)
   - Fetches purchase orders and branch orders from last 30 days
   - Previously: Year start to today
   - Now: `(today - 30 days) to today`

3. **Supplier Invoices Fetcher** (`database_supplier_invoices_fetcher.py`)
   - Fetches supplier invoices from last 30 days
   - Previously: Year start to today
   - Now: `(today - 30 days) to today`

4. **HQ Invoices Fetcher** (`database_hq_invoices_fetcher.py`)
   - Fetches HQ invoices and transfers from last 30 days
   - Previously: Last 90 days
   - Now: `(today - 30 days) to today`

5. **Stock Fetcher** (`database_stock_fetcher.py`)
   - Already clears old data before inserting new
   - No changes needed - already optimized

### Cleanup Script

**File:** `scripts/cleanup_old_data.py`

**Purpose:** Removes data older than 30 days from time-based tables

**Usage:**
```bash
# Run manually
python scripts/cleanup_old_data.py [connection_string] [retention_days]

# Or it runs automatically after fetchers complete
```

**What it does:**
- Deletes records older than 30 days from:
  - `supplier_invoices` (where `document_date < 30 days ago`)
  - `grn` (where `grn_date < 30 days ago`)
  - `purchase_orders` (where `order_date < 30 days ago`)
  - `branch_orders` (where `order_date < 30 days ago`)
  - `hq_invoices` (where `document_date < 30 days ago`)

### Orchestrator Integration

The `database_fetcher_orchestrator.py` automatically runs cleanup after all fetchers complete:

1. Fetches new data (last 30 days)
2. Inserts/updates database
3. Cleans up old data (older than 30 days)
4. Reports summary

## Benefits

1. **Stays within Supabase free tier** - Database size remains manageable
2. **No data loss** - Always maintains complete 30-day window
3. **No duplicates** - Fetchers track processed documents
4. **No gaps** - Ensures continuous coverage of the retention period
5. **Automatic** - Cleanup runs automatically after each fetch

## Monitoring

The cleanup script reports:
- Number of records deleted per table
- Current record counts (last 30 days)
- Success/failure status

Check orchestrator logs or run cleanup manually to see statistics.

## Manual Cleanup

To run cleanup manually:

```bash
cd c:\PharmaStockApp\web_app\scripts
python cleanup_old_data.py "postgresql://user:pass@host:port/db" 30
```

Or if DATABASE_URL is set in config:
```bash
python cleanup_old_data.py
```

## Configuration

To change retention period (default: 30 days):

1. Update fetchers to use different days:
   ```python
   start_date, end_date = self.get_retention_date_range(30)  # Change 30 to desired days
   ```

2. Update cleanup script:
   ```bash
   python cleanup_old_data.py [connection_string] [retention_days]
   ```

## Notes

- **Inventory analysis** is not cleaned - it's reference data that stays constant
- **Current stock** is always replaced (not cleaned by date) - only most recent version kept
- **Document tracking** ensures no duplicates are fetched
- **Date ranges** are calculated dynamically to ensure no gaps

## Troubleshooting

If you see data older than 30 days:
1. Check if cleanup ran successfully (check orchestrator logs)
2. Run cleanup manually to remove old data
3. Verify fetchers are using 30-day window (check logs)

If cleanup fails:
- Check database connection
- Verify table names match (case-sensitive)
- Check date column names are correct

