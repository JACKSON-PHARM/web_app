# 🔍 Check Database Connection - Diagnostic Guide

## Problem
Dashboard shows "Database synced" but "No Data Available" - need to verify if we're actually connected to Supabase and if data exists.

## Quick Diagnostic

### Step 1: Check Database Connection

Visit this URL on your Render app:
```
https://your-app.onrender.com/api/diagnostics/database-check
```

This will show:
- ✅ Database type (Supabase PostgreSQL or SQLite)
- ✅ Connection status
- ✅ Connection string (masked)
- ✅ Record counts for each table
- ✅ Any errors

### Step 2: Check Health Endpoint

Visit:
```
https://your-app.onrender.com/api/health
```

Should show:
```json
{
  "status": "ok",
  "database": {
    "type": "PostgreSQL",
    "exists": true
  }
}
```

### Step 3: Check Sync Status

Visit:
```
https://your-app.onrender.com/api/dashboard/sync-status
```

Should show:
```json
{
  "database_type": "Supabase PostgreSQL",
  "connected": true,
  "stock_records": <number>
}
```

## What to Look For

### ✅ Good Signs:
- `"database_type": "Supabase PostgreSQL"`
- `"connected": true`
- `"connection_string_set": true`
- Tables show record counts > 0

### ❌ Bad Signs:
- `"database_type": "SQLite"` → DATABASE_URL not set!
- `"connected": false` → Connection failed
- `"connection_string_set": false` → DATABASE_URL not configured
- All tables show `"record_count": 0` → No data in database

## If Database is Empty

If connection is good but no data:

1. **Check Supabase Dashboard**:
   - Go to: https://supabase.com/dashboard
   - Check tables manually
   - Run: `SELECT COUNT(*) FROM current_stock;`

2. **Run Data Refresh**:
   - Go to dashboard
   - Click "Refresh All Data"
   - Wait for completion
   - Check diagnostic endpoint again

3. **Verify Credentials**:
   - Make sure API credentials are saved
   - Check Settings page

## If Not Connected to Supabase

If diagnostic shows SQLite:

1. **Check Render Environment Variables**:
   - Go to Render Dashboard
   - Your Service → Environment
   - Verify `DATABASE_URL` is set

2. **Check Connection String Format**:
   ```
   DATABASE_URL=postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres
   ```

3. **Redeploy**:
   - After setting DATABASE_URL
   - Manual Deploy → Deploy latest commit

---

## Next Steps

1. ✅ Run diagnostic endpoint
2. ✅ Check results
3. ✅ Fix issues found
4. ✅ Run refresh if database is empty
5. ✅ Verify data appears

---

**Use the diagnostic endpoint to see exactly what's happening!** 🔍

