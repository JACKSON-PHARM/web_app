# Materialized Views Setup and Refresh

## Overview

Materialized views pre-compute complex joins and aggregations for instant access to stock view and priority items data.

## Setup

1. **Run Migration Script**:
   ```powershell
   cd C:\PharmaStockApp\web_app
   python scripts/create_supabase_tables.py
   ```

   This creates:
   - `stock_view_materialized` - Pre-computed stock view with all columns
   - `priority_items_materialized` - Pre-computed priority items with ABC class and AMC
   - `refresh_materialized_views()` PostgreSQL function

## Automatic Refresh

Materialized views refresh automatically after each data sync:

1. **Scheduler triggers data refresh** (every hour, 8 AM - 6 PM)
2. **Fetchers update tables** in Supabase (current_stock, purchase_orders, etc.)
3. **Refresh service calls** `_refresh_materialized_views()`
4. **Views refresh** with new data
5. **Frontend queries** use materialized views for instant results

## Manual Refresh

### Via API Endpoint

```bash
POST /api/materialized-views/refresh
Authorization: Bearer <token>
```

### Via PostgreSQL Function

```sql
SELECT refresh_materialized_views();
```

### Via Supabase Dashboard

1. Go to Supabase Dashboard → SQL Editor
2. Run: `SELECT refresh_materialized_views();`

## Performance

- **Before**: 5+ minutes to compile stock view/priority table
- **After**: Seconds to load (materialized views are pre-computed)
- **Refresh Time**: ~10-30 seconds (depends on data size)

## Troubleshooting

### Views not refreshing?

Check if views exist:
```sql
SELECT * FROM pg_matviews WHERE schemaname = 'public';
```

Check if unique indexes exist (required for CONCURRENT refresh):
```sql
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename IN ('stock_view_materialized', 'priority_items_materialized');
```

### Views out of date?

Manually refresh:
```sql
REFRESH MATERIALIZED VIEW stock_view_materialized;
REFRESH MATERIALIZED VIEW priority_items_materialized;
```

Or use the API endpoint or PostgreSQL function.

## Architecture

```
Data Flow:
1. APIs (NILA/DAIMA) 
   ↓
2. Fetchers (using saved credentials)
   ↓
3. Supabase Tables (current_stock, purchase_orders, etc.)
   ↓
4. Materialized Views (auto-refresh after data sync)
   ↓
5. Frontend (instant queries)
```

## Benefits

1. **Fast Queries**: Pre-computed joins - queries in seconds
2. **Auto-Refresh**: Views refresh after each data sync
3. **Free Tier Compatible**: Efficient refresh within Supabase limits
4. **User Experience**: Instant access to correct information

