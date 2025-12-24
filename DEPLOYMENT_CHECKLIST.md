# Deployment Checklist - Supabase Ready

## Pre-Deployment Checklist

### ✅ Data Migration Complete
- [x] Inventory analysis loaded to Supabase
- [ ] HQ invoices migrated (last 30 days)
- [ ] Verify all tables exist in Supabase

### ✅ Code Updates Complete
- [x] Fetchers updated for 30-day window
- [x] Cleanup script created
- [x] Base fetcher detects Supabase
- [x] Orchestrator passes database manager to fetchers
- [x] Refresh service uses orchestrator correctly

## Deployment Steps

### 1. Set Environment Variables in Render

**Go to Render Dashboard → Your Service → Environment**

Add these environment variables:

```
DATABASE_URL=postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres
PYTHON_VERSION=3.11.0
PORT=8000
```

**Important:** 
- `DATABASE_URL` is REQUIRED for Supabase connection
- Do NOT commit `DATABASE_URL` to Git (security)
- Set it in Render dashboard only

### 2. Push Code to GitHub

```bash
cd c:\PharmaStockApp\web_app
git add .
git commit -m "Configured for Supabase - 30-day retention policy"
git push origin main
```

### 3. Deploy on Render

- **Auto-deploy:** Render will automatically deploy if enabled
- **Manual deploy:** Go to Render dashboard → Deploy → Deploy latest commit

### 4. Verify Deployment

After deployment, check:

1. **App loads** - Visit your Render URL
2. **Database connection** - Check logs for "✅ Using Supabase PostgreSQL database"
3. **Health endpoint** - Visit `/api/health` to verify database connection
4. **Data appears** - Dashboard should show data from Supabase

## Post-Deployment Testing

### Test Dashboard
- [ ] Dashboard loads without errors
- [ ] Data appears (stock, orders, invoices)
- [ ] Filters work correctly
- [ ] Charts display properly

### Test Stock View
- [ ] Stock view loads
- [ ] Inventory analysis data appears
- [ ] Filters and search work
- [ ] Branch switching works

### Test Data Refresh
- [ ] Configure credentials in Settings
- [ ] Run data refresh
- [ ] Verify data updates in Supabase
- [ ] Check cleanup runs automatically

### Test Procurement Bot
- [ ] Procurement bot loads
- [ ] Can select items
- [ ] Can generate orders
- [ ] Orders save correctly

## Troubleshooting

### Issue: "Using SQLite database" in logs
**Solution:** `DATABASE_URL` environment variable not set in Render

### Issue: Data not appearing
**Solution:** 
1. Check if migrations completed
2. Verify `DATABASE_URL` is correct
3. Check Supabase dashboard for data

### Issue: Refresh fails
**Solution:**
1. Check credentials are saved
2. Verify API endpoints are accessible
3. Check Render logs for errors

### Issue: Timeout errors
**Solution:**
- Normal for Supabase free tier
- Scripts handle timeouts gracefully
- Data will still load (may take longer)

## Environment Variables Reference

### Required
```bash
DATABASE_URL=postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres
```

### Optional
```bash
PYTHON_VERSION=3.11.0
PORT=8000
DEBUG=False  # Set to False in production
```

## Rollback Plan

If deployment fails:

1. **Remove DATABASE_URL** from Render environment variables
2. App will fall back to SQLite
3. Fix issues locally
4. Redeploy with fixes

## Success Indicators

✅ App loads successfully
✅ Logs show "Using Supabase PostgreSQL database"
✅ Dashboard shows data
✅ Data refresh works
✅ No timeout errors in logs
✅ Cleanup runs after refresh

## Next Steps After Successful Deployment

1. ✅ Monitor app performance
2. ✅ Set up auto-refresh schedule
3. ✅ Configure user access
4. ✅ Test all features
5. ✅ Document any issues

