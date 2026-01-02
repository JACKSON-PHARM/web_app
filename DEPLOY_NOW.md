# 🚀 Deploy Latest Changes to Render NOW

## Current Status

- ✅ Local code is committed: `7179ac5 new changes`
- ⚠️ Render needs to be synced
- ⚠️ Database connection needs fixing

## Quick Deploy Steps

### 1. Push Latest Code (if not already done)

```powershell
git push origin main
```

### 2. Update DATABASE_URL in Render

**CRITICAL**: The database connection is failing. You MUST update the connection string.

1. **Go to**: https://dashboard.render.com
2. **Click** your service
3. **Go to**: Environment tab
4. **Find**: `DATABASE_URL`
5. **Update** with pooler connection string from Supabase:
   - ⚠️ **CRITICAL**: Free tier REQUIRES pooler connection - direct connections won't work!
   - Get it from: Supabase Dashboard → Settings → Database → Connection pooling → Session mode
   - **Copy the EXACT connection string** (don't modify it)
   - Must use username format: `postgres.[PROJECT_REF]` (NOT just `postgres`)
   - Must use port **6543** (not 5432)
   - Must use **pooler.supabase.com** hostname (NOT `db.xxx.supabase.co`)
   - URL-encode password special characters if needed
   - Password must be URL-encoded

### 3. Trigger Deployment

**Option A: Manual Deploy**
1. Go to Render Dashboard → Your Service
2. Click **"Manual Deploy"** tab
3. Select branch: `main`
4. Click **"Deploy latest commit"**

**Option B: Auto-Deploy**
- If auto-deploy is enabled, it should deploy automatically after you push
- Wait 5-10 minutes

### 4. Verify

After deployment:
- ✅ Check logs show: `✅ Using Supabase PostgreSQL database`
- ✅ Check logs show: `✅ PostgreSQL connection pool created`
- ✅ Visit app URL - should load without errors
- ✅ Test dashboard - should show data

---

## What Was Fixed in Latest Code

1. ✅ Auto-selection procurement bot now uses class-specific thresholds (A=50%, B=30%, C=25%)
2. ✅ Excludes items ordered in past 14 days
3. ✅ Checks source branch has enough stock
4. ✅ Only selects items with ABC class A, B, or C

---

## If Deployment Fails

1. Check Render logs for errors
2. Verify DATABASE_URL format is correct
3. Try clearing build cache: Settings → Clear Build Cache
4. Redeploy manually

---

**ACTION**: Update DATABASE_URL and trigger deployment NOW! 🚀

