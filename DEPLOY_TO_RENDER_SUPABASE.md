# Deploy to Render with Supabase

## Quick Deployment Guide

### Prerequisites
- ✅ All data migrated to Supabase (inventory_analysis, hq_invoices, etc.)
- ✅ GitHub repository with your code
- ✅ Render.com account

### Step 1: Set Environment Variables in Render

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Select your service (`pharmastock-web`)
3. Go to **Environment** tab
4. Add these environment variables:

```
DATABASE_URL=postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres
PYTHON_VERSION=3.11.0
PORT=8000
```

**Important:** The `DATABASE_URL` must be set for the app to use Supabase!

### Step 2: Deploy

1. **Push to GitHub** (if not already done):
   ```bash
   git add .
   git commit -m "Configured for Supabase deployment"
   git push origin main
   ```

2. **Render will auto-deploy** if auto-deploy is enabled
   - Or manually trigger deployment from Render dashboard

3. **Check deployment logs** to verify:
   - ✅ `Using Supabase PostgreSQL database` message appears
   - ✅ No database connection errors

### Step 3: Verify Deployment

After deployment, check:

1. **App loads** - Visit your Render URL
2. **Database connection** - Check `/api/health` endpoint
3. **Data appears** - Dashboard should show data from Supabase
4. **Refresh works** - Test data refresh functionality

## What Changed

### Database Configuration
- App automatically uses Supabase when `DATABASE_URL` is set
- Falls back to SQLite if `DATABASE_URL` is not set (for local dev)

### Data Fetchers
- All fetchers now use 30-day window (for free tier)
- Automatically clean up old data after fetching
- Use Supabase database manager when available

### Features Available
- ✅ Dashboard with real-time data
- ✅ Stock view with inventory analysis
- ✅ Procurement bot
- ✅ Data refresh from APIs
- ✅ Automatic cleanup (30-day retention)

## Troubleshooting

### App shows "Using SQLite database"
- **Fix:** Set `DATABASE_URL` environment variable in Render

### Data not appearing
- Check if migrations completed successfully
- Verify `DATABASE_URL` is correct
- Check Render logs for database errors

### Refresh fails
- Verify credentials are saved in Settings
- Check Render logs for API errors
- Ensure Supabase connection is working

## Environment Variables Reference

```bash
# Required for Supabase
DATABASE_URL=postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres

# Optional
PYTHON_VERSION=3.11.0
PORT=8000
DEBUG=False  # Set to False in production
```

## Next Steps After Deployment

1. ✅ Test all features (dashboard, stock view, procurement)
2. ✅ Configure credentials in Settings
3. ✅ Run initial data refresh
4. ✅ Verify data appears correctly
5. ✅ Test procurement bot functionality

## Rollback Plan

If something goes wrong:
1. Remove `DATABASE_URL` environment variable
2. App will fall back to SQLite
3. Fix issues and redeploy

