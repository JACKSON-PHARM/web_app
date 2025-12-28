# Stock Snapshot Quick Start Guide

## What This Does

Replaces slow pandas merges and materialized views with a **single PostgreSQL function** that:
- ✅ Returns all stock data in one query
- ✅ Handles pack/piece conversions in SQL
- ✅ Uses `inventory_analysis_new` as authoritative source
- ✅ Computes priority flags and stock levels
- ✅ No pandas, no CSV, no materialized views

## Quick Deploy (3 Steps)

### Step 1: Verify Schema

```sql
-- Run this first to verify your data structure
\i scripts/verify_stock_schema.sql
```

**Check**: Does `stock_pieces * pack_size` make sense? If yes, `stock_pieces` is in PACKS (correct). If no, adjust the SQL.

### Step 2: Deploy Function and Indexes

```sql
-- Deploy the function
\i scripts/create_stock_snapshot_function.sql

-- Deploy indexes
\i scripts/create_stock_snapshot_indexes.sql
```

### Step 3: Test

```sql
-- Test the function
SELECT * FROM stock_snapshot('BABA DOGO HQ', 'BABA DOGO HQ', 'NILA') LIMIT 5;

-- Should return columns:
-- item_code, item_name, branch_stock_pieces, source_branch_stock_pieces, 
-- pack_size, adjusted_amc_pieces, ideal_stock_pieces, abc_class,
-- last_order_date, last_order_quantity, last_order_document, last_order_type,
-- last_invoice_date, last_invoice_quantity, last_invoice_document,
-- last_supplier_invoice_date, last_supplier_invoice_quantity, last_supplier_invoice_document,
-- stock_level_vs_amc, priority_flag
```

## Python Usage

```python
from app.services.stock_snapshot_service import StockSnapshotService
from app.dependencies import get_db_manager

# Initialize
db_manager = get_db_manager()
snapshot_service = StockSnapshotService(db_manager)

# Get full snapshot
snapshot = snapshot_service.get_snapshot(
    target_branch='BABA DOGO HQ',
    source_branch='BABA DOGO HQ', 
    company='NILA'
)

# Get priority items only
priority = snapshot_service.get_priority_items(
    target_branch='BABA DOGO HQ',
    source_branch='BABA DOGO HQ',
    company='NILA',
    priority_only=True,
    days=7
)

# Get new arrivals
new_arrivals = snapshot_service.get_new_arrivals(
    branch='BABA DOGO HQ',
    company='NILA',
    days=7
)
```

## Integration Points

### Stock View
Replace `StockViewServicePostgres.get_stock_view_data()` to use `stock_snapshot()`.

### Dashboard
Replace:
- `DashboardService.get_priority_items_between_branches()` 
- `DashboardService.get_new_arrivals_this_week()`

Both should call `StockSnapshotService` methods.

## Key Benefits

1. **Single Source of Truth**: One function, one query, consistent results
2. **Fast**: Indexed queries, no pandas overhead
3. **Always Fresh**: No materialized view refresh needed
4. **Centralized Logic**: Priority flags, stock levels computed in SQL
5. **Type Safe**: All conversions (packs→pieces) in SQL

## Files Created

- `STOCK_SNAPSHOT_ARCHITECTURE.md` - Full design documentation
- `scripts/create_stock_snapshot_function.sql` - SQL function
- `scripts/create_stock_snapshot_indexes.sql` - Performance indexes
- `scripts/verify_stock_schema.sql` - Schema verification
- `app/services/stock_snapshot_service.py` - Python service
- `MIGRATION_TO_STOCK_SNAPSHOT.md` - Step-by-step migration guide

## Next Steps

1. **Verify schema** with `verify_stock_schema.sql`
2. **Deploy function** and indexes
3. **Test** with sample queries
4. **Integrate** into services (see MIGRATION_TO_STOCK_SNAPSHOT.md)
5. **Remove** materialized views (after validation)

