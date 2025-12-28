# Deployment Instructions - stock_snapshot() Function

## Quick Fix Summary

The app is currently using materialized views that don't properly handle `source_branch` parameter. The new `stock_snapshot()` function fixes this.

## Step 1: Deploy stock_snapshot Function

Run the deployment script:

```bash
cd C:\PharmaStockApp\web_app
python scripts/deploy_stock_snapshot.py
```

This will:
1. Create the `stock_snapshot()` PostgreSQL function
2. Create performance indexes
3. Test the function

## Step 2: Verify Deployment

Check if function exists:

```sql
-- In Supabase SQL Editor
SELECT routine_name 
FROM information_schema.routines 
WHERE routine_name = 'stock_snapshot';
```

Test the function:

```sql
SELECT * FROM stock_snapshot('DAIMA MERU WHOLESALE', 'DAIMA WHOLESALE THIKA', 'DAIMA') LIMIT 5;
```

## Step 3: Restart Application

Restart your FastAPI application so it picks up the new function.

## What Changed

### Fixed Issues:

1. **SQL Parameter Error**: Fixed `not all arguments converted during string formatting` in dashboard_service.py
2. **Source Branch Handling**: Updated services to use `stock_snapshot()` which properly handles `source_branch` parameter
3. **Stock Level Calculation**: `stock_snapshot()` computes `stock_level_vs_amc` correctly

### Updated Files:

- `app/services/dashboard_service.py` - Now checks for `stock_snapshot()` first
- `app/services/stock_view_service_postgres.py` - Now uses `stock_snapshot()` with source_branch support
- `scripts/deploy_stock_snapshot.py` - Deployment script

## How It Works Now

1. **Stock View**: Uses `stock_snapshot(target_branch, source_branch, company)` - properly shows different stock levels
2. **Priority Items**: Uses `stock_snapshot()` with priority filtering
3. **Fallback**: If `stock_snapshot()` doesn't exist, falls back to materialized view (for backward compatibility)

## Verification

After deployment, check logs for:
- `✅ Using stock_snapshot() function (PostgreSQL-first, handles source_branch)`
- Stock view should show different values for target vs source branches
- Stock Level % should be calculated correctly (not 0.0%)

## Troubleshooting

### Function doesn't exist
- Run `scripts/deploy_stock_snapshot.py` again
- Check Supabase SQL Editor for errors

### Still using materialized view
- Check logs for `stock_snapshot function exists: True`
- Restart the application

### Stock levels still 0.0%
- Verify `inventory_analysis_new` has `adjusted_amc` values
- Check that `current_stock.stock_pieces` is in PACKS (not pieces)

