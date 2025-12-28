# Migration Plan: Remove Materialized Views, Use stock_snapshot()

## Overview

This guide helps you safely migrate from materialized views and pandas merges to the canonical `stock_snapshot()` PostgreSQL function.

## Prerequisites

1. **Verify Table Schemas**: Confirm that `current_stock.stock_pieces` is in PACKS (not pieces)
2. **Backup Database**: Always backup before major changes
3. **Test Environment**: Test in development first

## Step 1: Deploy SQL Function and Indexes

### Option A: Via Supabase Dashboard

1. Go to Supabase Dashboard → SQL Editor
2. Copy and paste `scripts/create_stock_snapshot_function.sql`
3. Execute
4. Copy and paste `scripts/create_stock_snapshot_indexes.sql`
5. Execute

### Option B: Via Python Script

```python
# scripts/deploy_stock_snapshot.py
from app.services.postgres_database_manager import PostgresDatabaseManager
from app.dependencies import get_db_manager

db_manager = get_db_manager()

# Read and execute SQL files
with open('scripts/create_stock_snapshot_function.sql', 'r') as f:
    db_manager.execute_query(f.read())

with open('scripts/create_stock_snapshot_indexes.sql', 'r') as f:
    db_manager.execute_query(f.read())

print("✅ Stock snapshot function and indexes deployed")
```

## Step 2: Verify Function Works

```sql
-- Test the function
SELECT * FROM stock_snapshot('BABA DOGO HQ', 'BABA DOGO HQ', 'NILA') LIMIT 10;

-- Check execution plan (should use indexes)
EXPLAIN ANALYZE 
SELECT * FROM stock_snapshot('BABA DOGO HQ', 'BABA DOGO HQ', 'NILA');

-- Verify all columns are returned
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'stock_snapshot';
```

## Step 3: Update Python Services (Gradual Migration)

### 3.1 Add Feature Flag

In `app/config.py`:

```python
# Feature flags
USE_STOCK_SNAPSHOT: bool = os.getenv('USE_STOCK_SNAPSHOT', 'false').lower() == 'true'
```

### 3.2 Update StockViewServicePostgres

```python
# In app/services/stock_view_service_postgres.py

from app.services.stock_snapshot_service import StockSnapshotService
from app.config import settings

class StockViewServicePostgres:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.snapshot_service = StockSnapshotService(db_manager)  # New service
        # ... existing code ...
    
    def get_stock_view_data(self, branch_name: str, branch_company: str, 
                           source_branch: str = None):
        """Get stock view data - uses stock_snapshot if enabled"""
        
        if settings.USE_STOCK_SNAPSHOT:
            # NEW: Use stock_snapshot function
            source = source_branch or branch_name
            snapshot = self.snapshot_service.get_snapshot(
                branch_name, source, branch_company
            )
            
            # Convert to expected format (add pack calculations if needed)
            return self._format_snapshot_for_view(snapshot)
        else:
            # OLD: Use existing logic (materialized view or pandas)
            return self._get_stock_view_data_legacy(branch_name, branch_company, source_branch)
    
    def _format_snapshot_for_view(self, snapshot: List[Dict]) -> pd.DataFrame:
        """Format snapshot data for stock view display"""
        import pandas as pd
        
        df = pd.DataFrame(snapshot)
        
        # Add pack calculations for display
        df['branch_stock_packs'] = (df['branch_stock_pieces'] / df['pack_size']).round(0)
        df['source_stock_packs'] = (df['source_branch_stock_pieces'] / df['pack_size']).round(0)
        df['amc_packs'] = (df['adjusted_amc_pieces'] / df['pack_size']).round(2)
        
        # Rename columns to match expected format
        df = df.rename(columns={
            'branch_stock_pieces': 'branch_stock',
            'source_branch_stock_pieces': 'supplier_stock',
            'adjusted_amc_pieces': 'amc',
            'stock_level_vs_amc': 'stock_level_pct'
        })
        
        return df
```

### 3.3 Update DashboardService

```python
# In app/services/dashboard_service.py

from app.services.stock_snapshot_service import StockSnapshotService
from app.config import settings

class DashboardService:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.snapshot_service = StockSnapshotService(db_manager)  # New service
        # ... existing code ...
    
    def get_priority_items_between_branches(self, source_branch: str, 
                                           target_branch: str, company: str,
                                           limit: int = 100):
        """Get priority items - uses stock_snapshot if enabled"""
        
        if settings.USE_STOCK_SNAPSHOT:
            # NEW: Use stock_snapshot function
            items = self.snapshot_service.get_priority_items(
                target_branch, source_branch, company,
                priority_only=True, days=7
            )
            
            # Format for frontend
            return self._format_priority_items(items, limit)
        else:
            # OLD: Use existing logic
            return self._get_priority_items_legacy(source_branch, target_branch, company, limit)
    
    def get_new_arrivals_this_week(self, branch: str, company: str):
        """Get new arrivals - uses stock_snapshot if enabled"""
        
        if settings.USE_STOCK_SNAPSHOT:
            # NEW: Use stock_snapshot function
            return self.snapshot_service.get_new_arrivals(branch, company, days=7)
        else:
            # OLD: Use existing logic
            return self._get_new_arrivals_legacy(branch, company)
```

## Step 4: Test New Implementation

1. **Set environment variable**:
   ```bash
   # Windows PowerShell
   $env:USE_STOCK_SNAPSHOT="true"
   
   # Or in .env file
   USE_STOCK_SNAPSHOT=true
   ```

2. **Test stock view**: Navigate to stock view page, verify data matches
3. **Test dashboard**: Check priority items and new arrivals
4. **Compare results**: Run both old and new in parallel, compare outputs

## Step 5: Remove Old Code (After Validation)

### 5.1 Remove Materialized View Refresh

In `app/services/refresh_service.py`:

```python
# Remove or comment out:
# self._refresh_materialized_views()
```

### 5.2 Remove Pandas Merges

In `app/services/dashboard_service.py` and `app/services/stock_view_service_postgres.py`:

- Remove `_load_inventory_analysis()` CSV loading
- Remove pandas merge operations
- Remove materialized view fallback logic

### 5.3 Remove Materialized View Dependencies

```python
# Remove from refresh_service.py
def _refresh_materialized_views(self):
    # DELETE THIS ENTIRE METHOD
    pass
```

## Step 6: Drop Materialized Views (Final Step)

**Only after confirming everything works!**

```sql
-- Drop materialized views
DROP MATERIALIZED VIEW IF EXISTS stock_view_materialized CASCADE;
DROP MATERIALIZED VIEW IF EXISTS priority_items_materialized CASCADE;

-- Drop refresh function if exists
DROP FUNCTION IF EXISTS refresh_materialized_views() CASCADE;
```

## Step 7: Clean Up

1. Remove `MATERIALIZED_VIEWS_SETUP.md` (or archive it)
2. Remove materialized view creation from `scripts/create_supabase_tables.py`
3. Remove pandas imports where no longer needed
4. Update documentation

## Rollback Plan

If issues occur:

1. **Set environment variable**: `USE_STOCK_SNAPSHOT=false`
2. **Restore materialized views** (if dropped):
   ```sql
   -- Re-run scripts/create_supabase_tables.py
   -- Or restore from backup
   ```
3. **Revert code changes** via git

## Verification Checklist

- [ ] Function deployed and testable
- [ ] Indexes created and analyzed
- [ ] Stock view works with new function
- [ ] Dashboard priority items work
- [ ] Dashboard new arrivals work
- [ ] Performance is acceptable (< 5 seconds for full snapshot)
- [ ] Data matches old implementation
- [ ] No pandas in request path
- [ ] No materialized view dependencies
- [ ] Materialized views dropped (final step)

## Performance Expectations

- **First query**: 2-5 seconds (cold cache)
- **Subsequent queries**: < 1 second (warm cache)
- **With proper indexes**: Should be fast even for large datasets

## Troubleshooting

### Function doesn't exist
```sql
-- Check if function exists
SELECT routine_name 
FROM information_schema.routines 
WHERE routine_name = 'stock_snapshot';
```

### Slow queries
```sql
-- Check if indexes are being used
EXPLAIN ANALYZE SELECT * FROM stock_snapshot('BRANCH', 'BRANCH', 'COMPANY');

-- Verify indexes exist
SELECT indexname FROM pg_indexes 
WHERE tablename IN ('current_stock', 'inventory_analysis_new', ...);
```

### Wrong data
- Verify `current_stock.stock_pieces` is in PACKS (not pieces)
- Check `inventory_analysis_new` has correct branch_name/company_name format
- Verify order/invoice tables have correct date columns

