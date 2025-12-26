# Dashboard Branch Loading & Priority Items Fixes

## Summary
Fixed dashboard branch loading and priority items filtering to match requirements.

## Fixes Applied

### ✅ A. Dashboard Branch Loading
**File**: `web_app/templates/dashboard.html`

**Changes**:
1. Added global error handlers to prevent JS errors from breaking execution:
   - `window.addEventListener('error')` - catches uncaught JS errors
   - `window.addEventListener('unhandledrejection')` - catches promise rejections
2. Enhanced `loadBranches()` error handling:
   - Added try-catch wrapper in DOMContentLoaded
   - Better error messages in dropdowns
   - Matches working stock_view.html implementation
3. Added error handling for `loadPriorityItems()` call:
   - Wrapped in try-catch when triggered from branch loading
   - Added console logging for debugging

**Result**: Branches should now load correctly, matching stock_view behavior.

---

### ✅ B. Priority Items Filtering
**Files**: 
- `web_app/app/services/dashboard_service.py`
- `web_app/templates/dashboard.html`

**Changes**:

1. **ABC Class Filter** (A or B only):
   - Changed from `['A', 'B', 'C']` to `['A', 'B']` in Python filtering
   - Added SQL filter: `AND (abc_class = 'A' OR abc_class = 'B')` in materialized view query

2. **Last Order Date Filter** (> 10 days old OR NULL):
   - Added SQL filter: `AND (last_order_date IS NULL OR last_order_date < CURRENT_DATE - INTERVAL '10 days')`
   - Added Python filter for materialized view results (when using materialized view)

3. **Stock Level Filter** (< 50%):
   - Already filtered in SQL: `AND (stock_level_pct IS NULL OR stock_level_pct < 0.5)`
   - Ensured in Python filtering as well

4. **Materialized View Filtering**:
   - Previously skipped filtering when using materialized view
   - Now applies all filters even when using materialized view
   - Ensures consistent results regardless of query method

**Priority Items Criteria** (now enforced):
```sql
WHERE target_branch = %s
  AND target_company = %s
  AND supplier_stock > 0                    -- Source has stock
  AND (branch_stock IS NULL OR branch_stock <= 0 OR branch_stock < 1000)  -- Target needs stock
  AND (stock_level_pct IS NULL OR stock_level_pct < 0.5)  -- Below 50% stock level
  AND (abc_class = 'A' OR abc_class = 'B')  -- ABC class A or B only
  AND (last_order_date IS NULL OR last_order_date < CURRENT_DATE - INTERVAL '10 days')  -- > 10 days old or NULL
```

---

### ✅ C. Frontend Logging & Debugging
**File**: `web_app/templates/dashboard.html`

**Changes**:
1. Added detailed console logging for:
   - Branch loading process
   - Priority items API calls
   - API URLs being called
   - API responses

**Result**: Easier debugging when issues occur.

---

## Testing Checklist

1. **Branch Loading**:
   - [ ] Open dashboard page
   - [ ] Check browser console for "📋 Calling loadBranches()..."
   - [ ] Verify "✅ Found X branches" message
   - [ ] Verify dropdowns populate with branches
   - [ ] Verify default branch is selected

2. **Priority Items**:
   - [ ] Select target branch (e.g., "DAIMA MERU WHOLESALE")
   - [ ] Select source branch (e.g., "BABA DOGO HQ")
   - [ ] Check browser console for priority items API call
   - [ ] Verify priority items table displays
   - [ ] Verify only ABC class A or B items shown
   - [ ] Verify items have last_order_date > 10 days old OR NULL
   - [ ] Verify stock_level_pct < 0.5

3. **Error Handling**:
   - [ ] Check browser console for any red errors
   - [ ] Verify errors don't break page functionality
   - [ ] Verify error messages appear in dropdowns if API fails

---

## Files Modified

1. `web_app/templates/dashboard.html`
   - Added global error handlers
   - Enhanced branch loading error handling
   - Added logging for priority items API calls

2. `web_app/app/services/dashboard_service.py`
   - Changed ABC filter from A/B/C to A/B only
   - Added last_order_date filter to SQL query
   - Added filters for materialized view results
   - Fixed return statement to include proper columns

---

## Next Steps

1. Test branch loading on dashboard page
2. Test priority items display with different branch combinations
3. Verify filters are working correctly (ABC class, last_order_date, stock_level_pct)
4. Check browser console for any remaining errors

