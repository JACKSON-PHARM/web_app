# Complete Refactor - NO Materialized Views

## Changes Made

### 1. SQL Function (`scripts/create_stock_snapshot_function.sql`)
- ✅ Uses dual aliases for `current_stock` (target and source branches)
- ✅ Returns `stock_string` for display (NO parsing in SQL)
- ✅ Returns `adjusted_amc_packs` in PACKS (display value)
- ✅ All order/invoice quantities already in PACKS
- ✅ NO computation in SQL - placeholders for Python

### 2. Stock Snapshot Service (`app/services/stock_snapshot_service.py`)
- ✅ Parses `stock_string` in Python (not SQL)
- ✅ Computes `stock_level_pct` from parsed stock
- ✅ Computes `priority_flag` based on business rules
- ✅ NO materialized views, NO pandas, NO CSV

### 3. Stock View Service (`app/services/stock_view_service_postgres.py`)
- ❌ REMOVED: All materialized view checks
- ❌ REMOVED: All fallback logic
- ✅ Uses `stock_snapshot_service` only
- ✅ Returns stock_string for display

### 4. Dashboard Service (`app/services/dashboard_service.py`)
- ❌ REMOVED: All materialized view checks
- ❌ REMOVED: All fallback logic
- ✅ Uses `stock_snapshot_service` only

## Deployment Steps

1. **Deploy SQL Function**:
   ```bash
   python scripts/deploy_stock_snapshot.py
   ```

2. **Remove Materialized Views** (after deployment):
   ```sql
   DROP MATERIALIZED VIEW IF EXISTS stock_view_materialized CASCADE;
   DROP MATERIALIZED VIEW IF EXISTS priority_items_materialized CASCADE;
   ```

3. **Restart Application**

## Key Fixes

1. **Source ≠ Target Stock**: Dual aliases ensure correct mapping
2. **AMC in PACKS**: Displayed correctly, not converted
3. **Stock Level %**: Computed from parsed stock_string
4. **Priority Flag**: Computed in Python based on dates and stock level
5. **NO Legacy Code**: All materialized view references removed

## Verification

After deployment, verify:
- Source stock ≠ Target stock (unless truly equal)
- AMC shows in packs
- Stock level % is realistic
- Branch selection drives results correctly

