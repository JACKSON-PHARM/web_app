# 🔄 Sync Render Deployment & Fix Database Issues

## Issues Identified

1. **Database Connection Failed**: `could not translate host name "aws-1-eu-west-1.pooler.supabase.com" to address`
2. **Version Not Synced**: Render version doesn't match local version

---

## Part 1: Sync Version to Render

### Step 1: Verify Local Code is Committed

```powershell
# Check git status
git status

# If there are uncommitted changes, commit them:
git add .
git commit -m "Fix auto-selection procurement bot criteria"
git push origin main
```

### Step 2: Force Render to Deploy Latest

**Option A: Manual Deploy (Recommended)**

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click on your service (`pharmastock-web` or `web_app`)
3. Go to **"Manual Deploy"** tab
4. Select branch: `main`
5. Click **"Deploy latest commit"**
6. Wait 5-10 minutes for deployment

**Option B: Trigger via Git**

```powershell
# Create an empty commit to trigger deployment
git commit --allow-empty -m "Trigger Render deployment"
git push origin main
```

### Step 3: Verify Deployment

After deployment completes, check Render logs for:
- ✅ `✅ Using Supabase PostgreSQL database`
- ✅ `✅ PostgreSQL connection pool created`
- ✅ No database connection errors

---

## Part 2: Fix Database Connection

### Problem

The error `could not translate host name "aws-1-eu-west-1.pooler.supabase.com"` suggests:
- Wrong connection string format
- DNS resolution failure
- Need to use correct pooler connection string

### Solution: Update DATABASE_URL in Render

#### Step 1: Get Correct Pooler Connection String from Supabase

**⚠️ CRITICAL: Free tier REQUIRES pooler connection - direct connections won't work!**

1. Go to [Supabase Dashboard](https://supabase.com/dashboard)
2. Select your project
3. Go to **Settings** → **Database**
4. Scroll to **"Connection pooling"** section
5. Click **"Session mode"** (recommended) or **"Transaction mode"**
6. **Copy the EXACT connection string** shown (don't modify it)

It should look like:
```
postgresql://postgres.oagcmmkmypmwmeuodkym:[PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

**Critical Requirements:**
- ✅ Username format: `postgres.[PROJECT_REF]` (NOT just `postgres`)
- ✅ Use **port 6543** (connection pooling) NOT 5432
- ✅ Use **pooler.supabase.com** hostname, NOT `db.xxx.supabase.co`
- ✅ The hostname should contain `pooler` in it
- ✅ Get the EXACT string from Supabase - don't guess the region

#### Step 2: URL-Encode Password

If your password has special characters, encode them:
- `?` → `%3F`
- `!` → `%21`
- `$` → `%24`

Example: `b?!HABE69$TwwSV` → `b%3F%21HABE69%24TwwSV`

#### Step 3: Update in Render

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click on your service
3. Go to **"Environment"** tab
4. Find `DATABASE_URL` variable
5. Click to edit
6. **Replace** with the pooler connection string from Supabase
7. Make sure it uses:
   - Port **6543** (not 5432)
   - Hostname with **pooler.supabase.com** (not `db.xxx.supabase.co`)
8. Click **"Save Changes"**
9. Render will automatically restart

#### Step 4: Verify Connection

After restart, check Render logs for:
- ✅ `✅ PostgreSQL connection pool created`
- ✅ `✅ Using Supabase PostgreSQL database`
- ✅ No DNS resolution errors
- ✅ No connection errors

---

## Part 3: Verify Everything Works

### Check App Health

1. Visit your Render URL: `https://your-app.onrender.com`
2. Check `/api/health` endpoint
3. Try logging in
4. Check dashboard loads data

### Check Database Connection

Visit: `https://your-app.onrender.com/api/diagnostics/database-check`

Should show:
- ✅ `"database_type": "PostgreSQL"`
- ✅ `"connection_string_set": true`
- ✅ Record counts for tables
- ✅ No errors

### Check Version Sync

1. Check Render logs for latest commit hash
2. Compare with local: `git log --oneline -1`
3. Should match!

---

## Troubleshooting

### Issue: "Still showing old version"

**Solution:**
1. Clear Render cache: Settings → Clear Build Cache
2. Manual deploy again
3. Wait for full deployment (5-10 minutes)

### Issue: "Still can't connect to database"

**Solution:**
1. Verify connection string format:
   - ✅ Uses `pooler.supabase.com`
   - ✅ Uses port `6543`
   - ✅ Password is URL-encoded
2. Test connection string locally first
3. Check Supabase project is active (not paused)

### Issue: "DNS resolution still failing"

**Solution:**
1. Try using direct connection (port 5432) temporarily to test
2. Verify Supabase project region matches connection string
3. Check if Supabase project is paused or deleted

---

## Quick Checklist

- [ ] Local code committed and pushed to GitHub
- [ ] Render manually deployed latest commit
- [ ] DATABASE_URL updated with pooler connection string (port 6543)
- [ ] Render service restarted
- [ ] Logs show successful database connection
- [ ] App loads and shows data
- [ ] Version matches between local and Render

---

## Next Steps After Fix

1. **Test the app** - Make sure all features work
2. **Monitor logs** - Watch for any errors
3. **Verify data** - Check that reports load correctly
4. **Test procurement bot** - Verify auto-selection fixes work

---

**Status**: ⚠️ Action Required - Update DATABASE_URL and trigger deployment

