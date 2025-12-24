# 🔄 Update GitHub & Redeploy on Render

## Current Situation
- ✅ You have `JACKSON-PHARM/web_app` repository on GitHub
- ✅ Last commit was 3 days ago
- ✅ You have Render services already set up
- ⚠️ New Supabase changes need to be pushed

## Step 1: Push New Changes to GitHub

### Using GitHub Desktop (Easiest)

1. **Open GitHub Desktop**
2. **Add Repository** (if not already added):
   - File → Add Local Repository
   - Browse to: `C:\PharmaStockApp\web_app`
   - Click "Add Repository"

3. **Check Changes**:
   - You should see all the new files/changes listed
   - Make sure these are NOT included (they're in `.gitignore`):
     - ❌ `*.db` files
     - ❌ `cache/` folder  
     - ❌ `.env` file
     - ❌ `google_credentials.json`

4. **Commit Changes**:
   - Enter commit message:
     ```
     Supabase migration complete - database manager, fetchers, and cleanup updated
     ```
   - Click "Commit to main"

5. **Push to GitHub**:
   - Click "Push origin" button (top right)
   - Wait for push to complete

### Using VS Code

1. **Open VS Code** in `C:\PharmaStockApp\web_app`
2. **Open Source Control** (`Ctrl+Shift+G`)
3. **Stage Changes**: Click "+" next to "Changes"
4. **Commit**: Enter message and press `Ctrl+Enter`
5. **Push**: Click "..." → "Push"

---

## Step 2: Update/Redeploy on Render

You have two options:

### Option A: Update Existing Service (Recommended)

1. **Go to Render Dashboard**
   - Visit: https://dashboard.render.com
   - Find your existing service: `web_app` or `pharma-stock-app`

2. **Set Environment Variable** (CRITICAL - if not already set):
   - Go to your service → "Environment" tab
   - Add/Update: `DATABASE_URL`
   - Value: `postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres`
   - Click "Save Changes"

3. **Manual Deploy** (if auto-deploy is off):
   - Go to "Manual Deploy" tab
   - Select branch: `main`
   - Click "Deploy latest commit"
   - Wait for deployment (5-10 minutes)

4. **Or Auto-Deploy** (if enabled):
   - Render will automatically deploy when you push to GitHub
   - Just wait for deployment to complete!

### Option B: Create New Service

If you want a fresh deployment:

1. **Go to Render Dashboard** → "New +" → "Web Service"
2. **Select Repository**: `JACKSON-PHARM/web_app`
3. **Configure**:
   - Name: `pharmastock-web` (or your preferred name)
   - Root Directory: `web_app` (if your code is in a subfolder)
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --timeout-keep-alive 300`
4. **Set Environment Variables**:
   - `DATABASE_URL=postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres`
   - `PYTHON_VERSION=3.11.0`
   - `PORT=8000`
5. **Deploy**: Click "Create Web Service"

---

## Step 3: Verify Deployment

### Check Logs
1. Go to Render Dashboard → Your Service → Logs
2. Look for:
   - ✅ `✅ Using Supabase PostgreSQL database`
   - ✅ `✅ Database manager initialized`
   - ✅ `🚀 Starting PharmaStock Web Application`
   - ❌ No database connection errors

### Test Your App
1. Visit your Render URL
2. Check health: `https://your-app.onrender.com/api/health`
3. Should show PostgreSQL database info

---

## Quick Checklist

- [ ] Push new Supabase changes to GitHub
- [ ] Verify code appears on GitHub (check repository)
- [ ] Go to Render Dashboard
- [ ] Set `DATABASE_URL` environment variable (if not set)
- [ ] Deploy (manual or auto)
- [ ] Check logs for Supabase connection
- [ ] Test app functionality

---

## What Changed Since Last Push?

These are the new changes that need to be pushed:

1. ✅ **Supabase Database Manager** - Auto-detects Supabase
2. ✅ **Updated Fetchers** - Use 30-day window
3. ✅ **Cleanup Script** - Automatic data retention
4. ✅ **Orchestrator Updates** - Passes database manager correctly
5. ✅ **Refresh Service** - Uses Supabase properly
6. ✅ **Migration Scripts** - For loading data to Supabase
7. ✅ **Deployment Docs** - Updated guides

---

## Need Help?

If you encounter issues:
1. Check GitHub Desktop/VS Code for error messages
2. Verify sensitive files are NOT being committed
3. Check Render logs for deployment errors
4. Ensure `DATABASE_URL` is set correctly

**Ready to push?** Let me know if you need help with any step! 🚀

