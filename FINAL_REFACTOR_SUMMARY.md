# Final Refactor Summary - NO Materialized Views

## ✅ Completed

### 1. SQL Function (`scripts/create_stock_snapshot_function.sql`)
- ✅ Uses **dual aliases** for `current_stock` (target and source branches)
- ✅ Returns `stock_string` for display (NO parsing in SQL)
- ✅ Returns `adjusted_amc_packs` in **PACKS** (display value)
- ✅ All order/invoice quantities already in PACKS
- ✅ NO computation in SQL - placeholders for Python

### 2. Stock Snapshot Service (`app/services/stock_snapshot_service.py`)
- ✅ Parses `stock_string` in Python (not SQL)
- ✅ Computes `stock_level_pct` from parsed stock
- ✅ Computes `priority_flag` based on business rules
- ✅ NO materialized views, NO pandas, NO CSV

### 3. Stock View Service (`app/services/stock_view_service_postgres.py`)
- ✅ **REPLACED** with clean version - NO materialized views
- ✅ Uses `stock_snapshot_service` only
- ✅ Returns stock_string for display

## ⚠️ Remaining Work

### Dashboard Service (`app/services/dashboard_service.py`)
**Still has materialized view references** that need to be removed:

1. **Lines 513-541**: Remove materialized view check, keep only stock_snapshot check
2. **Lines 603-647**: Remove entire materialized view query block (already disabled with `if False`)
3. **Lines 704-735**: Remove materialized view processing logic
4. **Lines 656-684**: Remove fallback query (should use stock_snapshot_service only)

## 🔧 Quick Fix for Dashboard Service

Replace the entire `get_priority_items_between_branches` method with:

```python
def get_priority_items_between_branches(self, target_branch: str, target_company: str,
                                        source_branch: str, source_company: str,
                                        limit: int = 50):
    """Get priority items - NO materialized views"""
    try:
        from app.services.stock_snapshot_service import StockSnapshotService
        
        snapshot_service = StockSnapshotService(self.db_manager)
        priority_items = snapshot_service.get_priority_items(
            target_branch, source_branch, target_company,
            priority_only=True, days=7
        )
        
        if not priority_items:
            return pd.DataFrame(columns=['item_code', 'item_name', 'source_stock_packs', 'branch_name',
                                        'target_stock_packs', 'abc_class', 'stock_level_pct', 'amc_packs', 
                                        'pack_size', 'last_order_date'])
        
        # Convert to DataFrame
        df = pd.DataFrame(priority_items)
        
        # Map columns for frontend compatibility
        df = df.rename(columns={
            'source_branch_stock_pieces': 'source_stock_pieces',
            'branch_stock_pieces': 'target_stock_pieces',
            'adjusted_amc_packs': 'amc_pieces',
            'last_order_qty_packs': 'last_order_quantity',
        })
        
        # Parse stock_string for display
        def parse_to_packs(stock_string: str, pack_size: float) -> float:
            import re
            if not stock_string: return 0.0
            whole = int(re.search(r'(\d+)W', stock_string).group(1)) if re.search(r'(\d+)W', stock_string) else 0
            pieces = int(re.search(r'(\d+)P', stock_string).group(1)) if re.search(r'(\d+)P', stock_string) else 0
            return float(whole) + (float(pieces) / pack_size if pack_size > 0 else 0)
        
        df['source_stock_packs'] = df.apply(
            lambda r: parse_to_packs(r.get('source_stock_display', '0W0P'), r.get('pack_size', 1)),
            axis=1
        )
        df['target_stock_packs'] = df.apply(
            lambda r: parse_to_packs(r.get('target_stock_display', '0W0P'), r.get('pack_size', 1)),
            axis=1
        )
        df['amc_packs'] = df['amc_pieces']  # Already in packs
        df['branch_name'] = target_branch
        
        return df.head(limit)
        
    except Exception as e:
        logger.error(f"❌ Error getting priority items: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return pd.DataFrame(columns=['item_code', 'item_name', 'source_stock_packs', 'branch_name',
                                    'target_stock_packs', 'abc_class', 'stock_level_pct', 'amc_packs', 
                                    'pack_size', 'last_order_date'])
```

## 📋 Deployment Checklist

1. ✅ Deploy SQL function: `python scripts/deploy_stock_snapshot.py`
2. ⚠️ Update dashboard_service.py (remove materialized view code)
3. ✅ Restart application
4. ✅ Drop materialized views:
   ```sql
   DROP MATERIALIZED VIEW IF EXISTS stock_view_materialized CASCADE;
   DROP MATERIALIZED VIEW IF EXISTS priority_items_materialized CASCADE;
   ```

## 🎯 Success Criteria

- ✅ Source stock ≠ Target stock (unless truly equal)
- ✅ AMC shows in packs
- ✅ Stock level % is realistic
- ✅ Branch selection drives results
- ✅ NO materialized view references in code

