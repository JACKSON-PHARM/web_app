# Render + Supabase Free Tier Deployment Fixes

## Summary
Applied minimal fixes to align the app with Render free tier deployment requirements while maintaining existing architecture.

## Fixes Applied

### ✅ A. Database Connection Pooling
**Status**: Already implemented correctly
- `PostgresDatabaseManager` validates connection string contains `pooler.supabase.com`
- Provides clear error messages if direct connection detected
- Uses connection pooling (2-20 connections)
- **Action Required**: Update `DATABASE_URL` in Render environment variables to use pooler connection string

### ✅ B. Frontend JS Reliability
**Files Modified**: `templates/stock_view.html`

**Changes**:
1. Added global error handlers:
   - `window.addEventListener('error')` - catches uncaught JS errors
   - `window.addEventListener('unhandledrejection')` - catches promise rejections
   - Prevents JS errors from breaking execution chain

2. Fixed button event listeners:
   - "Load Stock View" button: Removed inline `onclick`, added proper event listener in `DOMContentLoaded`
   - "Run Procurement Bot" button: Removed inline `onclick`, added proper event listener in `DOMContentLoaded`
   - Both wrapped in try-catch for error handling

3. Ensured all JS wrapped in `DOMContentLoaded`:
   - `loadBranches()` called on page load
   - All event listeners attached after DOM ready
   - Null checks added for DOM elements

### ✅ C. Materialized View Fallback
**Files Modified**: `app/services/stock_view_service_postgres.py`

**Changes**:
1. Enhanced fallback logic:
   - Explicitly sets `has_materialized_view = False` on exception
   - Ensures fallback CTE query ALWAYS executes when:
     - Materialized view doesn't exist
     - Materialized view returns 0 rows
     - Materialized view query fails
   - Added comment clarifying fallback conditions

**Current Logic Flow**:
```
1. Check if materialized view exists
2. If exists, query with 2 params (branch_name, branch_company)
3. If returns rows → return data immediately
4. If no rows OR doesn't exist OR query fails → fallback to CTE query (20+ params)
5. CTE query always executes as backup
```

### ✅ D. Render Deployment
**Files Created/Modified**:
- `Procfile` - Created for Render web service
- `app/main.py` - Enhanced `/health` endpoint
- `run.py` - Updated to use Render's PORT environment variable

**Health Endpoint** (`/health`):
- Returns database connection status
- Checks materialized view existence
- Reports scheduler status
- Returns appropriate HTTP status codes (200 for OK, 503 for degraded)

**Procfile**:
```
web: python run.py
```

**run.py Updates**:
- Uses `PORT` environment variable (provided by Render)
- Uses `HOST` environment variable (defaults to 0.0.0.0)
- Disables reload in production

## Deployment Checklist

### Before Deploying to Render:

1. **Update DATABASE_URL**:
   - Go to Supabase Dashboard → Settings → Database → Connection pooling
   - Copy pooler connection string (starts with `pooler.supabase.com`)
   - In Render Dashboard → Environment Variables → Set `DATABASE_URL`

2. **Verify Environment Variables**:
   - `DATABASE_URL` - Pooler connection string (REQUIRED)
   - `SECRET_KEY` - Random secret for JWT tokens
   - `PORT` - Automatically set by Render (don't override)
   - `HOST` - Automatically set by Render (don't override)

3. **Test Health Endpoint**:
   ```bash
   curl https://your-app.onrender.com/health
   ```
   Should return:
   ```json
   {
     "status": "ok",
     "database": { "connected": true },
     "materialized_views": { "stock_view_materialized": true }
   }
   ```

## Architecture Preserved

✅ **No architectural changes made**:
- External APIs → Supabase PostgreSQL → Materialized Views → Frontend
- Scheduler fetches data using credentials from database
- Materialized views refreshed post-fetch
- Frontend queries materialized views with safe fallbacks
- Procurement bot consumes already-loaded stock data

## Testing

### Local Testing:
```bash
cd web_app
python run.py
# Visit http://localhost:8000/health
```

### Verify Fixes:
1. ✅ Database connection uses pooler string
2. ✅ Frontend JS errors don't break execution
3. ✅ Buttons respond to clicks
4. ✅ Branches load in dropdowns
5. ✅ Stock view loads (materialized view or fallback)
6. ✅ Health endpoint returns proper status

## Next Steps

1. **Update DATABASE_URL in Render** (CRITICAL)
2. Deploy to Render
3. Test `/health` endpoint
4. Test frontend functionality
5. Monitor logs for any connection issues

## Notes

- All changes are **minimal** and **non-breaking**
- Architecture remains unchanged
- Backward compatible with existing code
- Ready for Render free tier deployment

