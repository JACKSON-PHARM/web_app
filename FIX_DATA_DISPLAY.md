# 🔧 Fix Data Display Issues

## Problems

1. **Refresh taking too long** (6+ minutes)
2. **No data showing** after refresh
3. **Localhost and Render out of sync**

## Solutions

### 1. Check if Data Exists

**In Supabase Dashboard:**
```sql
-- Check if tables have data
SELECT COUNT(*) FROM current_stock;
SELECT COUNT(*) FROM supplier_invoices;
SELECT COUNT(*) FROM grn;
SELECT COUNT(*) FROM purchase_orders;
SELECT COUNT(*) FROM branch_orders;
SELECT COUNT(*) FROM hq_invoices;
SELECT COUNT(*) FROM inventory_analysis;
```

**If all return 0**: Data hasn't been loaded yet - need to run refresh

### 2. Verify Credentials Are Saved

**On Render:**
1. Go to your app: `https://your-app.onrender.com/settings`
2. Check if credentials are configured
3. If not, add NILA and/or DAIMA credentials

**On Localhost:**
1. Go to: `http://localhost:8000/settings`
2. Configure credentials

### 3. Check Render Logs

Look for:
- ✅ `✅ Using Supabase PostgreSQL database`
- ✅ `✅ Database manager initialized`
- ❌ Any errors about credentials
- ❌ Any timeout errors
- ❌ Any "No data found" messages

### 4. Test Refresh Process

The refresh should:
1. Connect to Supabase (0-10%)
2. Fetch stock data (10-30%)
3. Fetch GRN data (30-50%)
4. Fetch orders (50-70%)
5. Fetch supplier invoices (70-85%)
6. Fetch HQ invoices (85-95%)
7. Cleanup old data (95-100%)

**If it hangs at any step:**
- Check Render logs for that step
- Might be API timeout
- Might be database connection issue

### 5. Push Latest Code

Make sure you've pushed:
1. ✅ Template changes (removed Google Drive messages)
2. ✅ Refresh service updates (better progress tracking)
3. ✅ All Supabase changes

**Commit and push:**
```bash
git add .
git commit -m "Fix refresh progress tracking and remove Google Drive UI"
git push origin main
```

### 6. Clear Browser Cache

After deploying:
- Hard refresh: `Ctrl+Shift+R` (Windows) or `Cmd+Shift+R` (Mac)
- Or clear browser cache

---

## Quick Diagnostic Steps

### Step 1: Check Database Connection

Visit: `https://your-app.onrender.com/api/health`

Should show:
```json
{
  "status": "ok",
  "database": {
    "type": "PostgreSQL",
    ...
  }
}
```

### Step 2: Check Branches Endpoint

Visit: `https://your-app.onrender.com/api/dashboard/branches`

Should return list of branches. If empty, database has no data.

### Step 3: Check Refresh Status

Visit: `https://your-app.onrender.com/api/refresh/status`

Shows:
- Is refresh running?
- Last refresh time
- Progress percentage

### Step 4: Run Refresh

1. Go to dashboard
2. Click "Refresh All Data"
3. Watch progress
4. Check if it completes

---

## Common Issues & Fixes

### Issue: Refresh Hangs at 20%

**Cause**: API timeout or slow API response  
**Fix**: 
- Check credentials are valid
- Check API is accessible
- Increase timeout in fetchers

### Issue: No Data After Refresh

**Cause**: Refresh failed silently  
**Fix**:
- Check Render logs for errors
- Verify credentials are saved
- Check Supabase connection

### Issue: "No data available yet"

**Cause**: Database queries returning empty  
**Fix**:
- Run refresh to populate data
- Check if refresh completed successfully
- Verify data exists in Supabase

---

## Next Steps

1. ✅ Check Supabase for data
2. ✅ Verify DATABASE_URL is set on Render
3. ✅ Check Render logs for errors
4. ✅ Push latest code changes
5. ✅ Test refresh again
6. ✅ Check if data appears

---

**After fixing, the dashboard should show data!** 🎉

