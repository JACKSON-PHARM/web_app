# 🚀 Step-by-Step: Push Code & Configure Render

## Part 1: Push Code to GitHub

### Option A: Using GitHub Desktop (Recommended - Easiest)

1. **Download GitHub Desktop** (if not installed):
   - Go to: https://desktop.github.com/
   - Download and install
   - Sign in with your GitHub account

2. **Add Repository**:
   - Open GitHub Desktop
   - Click "File" → "Add Local Repository"
   - Browse to: `C:\PharmaStockApp\web_app`
   - Click "Add Repository"

3. **Review Changes**:
   - You'll see all your files listed
   - Make sure these are NOT included (they should be grayed out - in `.gitignore`):
     - ❌ `*.db` files
     - ❌ `cache/` folder
     - ❌ `.env` file
     - ❌ `google_credentials.json`
     - ✅ Everything else should be included

4. **Commit**:
   - At bottom left, enter commit message:
     ```
     Supabase migration complete - database manager, fetchers, cleanup, and deployment config
     ```
   - Click "Commit to main"

5. **Push**:
   - Click "Push origin" button (top right, blue button)
   - Wait for "Pushed to origin/main" message
   - ✅ Done! Code is now on GitHub

### Option B: Using VS Code

1. **Open VS Code**:
   - Open folder: `C:\PharmaStockApp\web_app`

2. **Open Source Control**:
   - Press `Ctrl+Shift+G`
   - Or click the Source Control icon (left sidebar)

3. **Initialize Repository** (if needed):
   - If you see "Initialize Repository", click it
   - If you see files listed, skip this step

4. **Stage All Files**:
   - Click "+" next to "Changes" to stage all files
   - Or click individual files

5. **Commit**:
   - Enter commit message: `Supabase migration complete - ready for deployment`
   - Press `Ctrl+Enter` to commit

6. **Push**:
   - Click "..." menu (top right of Source Control panel)
   - Select "Push"
   - If asked for remote URL: `https://github.com/JACKSON-PHARM/web_app.git`
   - Enter GitHub credentials when prompted
   - ✅ Done!

---

## Part 2: Configure Render

### Step 1: Go to Render Dashboard

1. Visit: https://dashboard.render.com
2. Sign in with GitHub (if not already signed in)

### Step 2: Find Your Service

You have two options:

**Option A: Update Existing Service** (Recommended)
- Find your existing service: `web_app` or `pharma-stock-app`
- Click on it to open

**Option B: Create New Service**
- Click "New +" → "Web Service"
- Select repository: `JACKSON-PHARM/web_app`
- Click "Connect"

### Step 3: Configure Service Settings

If creating new service, set these:

- **Name**: `pharmastock-web` (or your preferred name)
- **Root Directory**: Leave empty (or `web_app` if your code is in a subfolder)
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --timeout-keep-alive 300`

### Step 4: Set Environment Variables (CRITICAL!)

1. **Go to "Environment" tab** (in your service settings)

2. **Add/Update these variables**:

   ```
   DATABASE_URL=postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres
   ```

   ```
   PYTHON_VERSION=3.11.0
   ```

   ```
   PORT=8000
   ```

3. **How to add**:
   - Click "Add Environment Variable"
   - Enter Key: `DATABASE_URL`
   - Enter Value: `postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres`
   - Click "Save"
   - Repeat for other variables

4. **Click "Save Changes"** at bottom

### Step 5: Deploy

**If updating existing service:**
- Go to "Manual Deploy" tab
- Select branch: `main`
- Click "Deploy latest commit"
- Wait 5-10 minutes for deployment

**If creating new service:**
- Click "Create Web Service"
- Wait 5-10 minutes for build and deployment

**If auto-deploy is enabled:**
- It will deploy automatically after you push to GitHub
- Just wait for deployment to complete!

---

## Part 3: Verify Deployment

### Check Logs

1. Go to Render Dashboard → Your Service → "Logs" tab
2. Look for these success messages:
   - ✅ `✅ Using Supabase PostgreSQL database`
   - ✅ `✅ Database manager initialized`
   - ✅ `🚀 Starting PharmaStock Web Application`
   - ✅ `Application startup complete`

### Test Your App

1. **Get your URL**:
   - Render Dashboard → Your Service
   - Copy the URL (e.g., `https://pharmastock-web.onrender.com`)

2. **Test Health Endpoint**:
   - Visit: `https://your-app.onrender.com/api/health`
   - Should show: `"database": {"type": "PostgreSQL", ...}`

3. **Test Main App**:
   - Visit: `https://your-app.onrender.com`
   - Should load login page or dashboard

---

## Troubleshooting

### "Using SQLite database" in logs
**Problem**: `DATABASE_URL` not set  
**Solution**: Add `DATABASE_URL` environment variable in Render

### Build fails
**Problem**: Missing dependencies  
**Solution**: Check `requirements.txt` exists and has all packages

### App doesn't start
**Problem**: Wrong start command  
**Solution**: Verify: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Database connection errors
**Problem**: Wrong `DATABASE_URL` format  
**Solution**: Verify connection string is URL-encoded correctly

---

## Quick Checklist

- [ ] Push code to GitHub (using GitHub Desktop or VS Code)
- [ ] Verify code appears on GitHub.com
- [ ] Go to Render Dashboard
- [ ] Find or create service
- [ ] Set `DATABASE_URL` environment variable
- [ ] Set `PYTHON_VERSION=3.11.0`
- [ ] Set `PORT=8000`
- [ ] Deploy (manual or auto)
- [ ] Check logs for Supabase connection
- [ ] Test app at Render URL

---

## Need Help?

If you get stuck at any step, let me know and I'll help you troubleshoot!

**Ready?** Start with Part 1 - Push to GitHub! 🚀

