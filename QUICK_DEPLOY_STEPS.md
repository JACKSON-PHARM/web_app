# 🚀 Quick Deployment Steps - GitHub → Render

## Step 1: Push to GitHub First ✅

**You MUST push to GitHub first** - Render deploys from GitHub, not directly from your computer.

### Check Current Status
```powershell
cd C:\PharmaStockApp\web_app
git status
```

### If Git Repository Not Initialized
```powershell
# Initialize git (if not already done)
git init

# Add all files
git add .

# Commit your changes
git commit -m "Supabase migration complete - ready for deployment"
```

### Push to GitHub
```powershell
# Add remote (if not already added)
git remote add origin https://github.com/JACKSON-PHARM/pharma-stock-app.git

# Or if remote already exists, just push
git push -u origin main
```

**If you get authentication errors:**
- Use GitHub Personal Access Token instead of password
- Create token: GitHub → Settings → Developer settings → Personal access tokens → Generate new token
- Use token as password when prompted

---

## Step 2: Deploy on Render

### Option A: First Time Setup (New Service)

1. **Go to Render Dashboard**
   - Visit https://dashboard.render.com
   - Sign in with GitHub (if not already signed in)

2. **Create New Web Service**
   - Click "New +" → "Web Service"
   - Select your repository: `JACKSON-PHARM/pharma-stock-app`
   - Click "Connect"

3. **Configure Service**
   - **Name**: `pharmastock-web` (or your preferred name)
   - **Root Directory**: `web_app` (important!)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --timeout-keep-alive 300`

4. **Set Environment Variables** (CRITICAL!)
   - Click "Environment" tab
   - Add these variables:
     ```
     DATABASE_URL=postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres
     PYTHON_VERSION=3.11.0
     PORT=8000
     ```
   - **Important:** `DATABASE_URL` is REQUIRED for Supabase!

5. **Deploy**
   - Click "Create Web Service"
   - Wait for build to complete (5-10 minutes)
   - Check logs for: "✅ Using Supabase PostgreSQL database"

### Option B: Update Existing Service

1. **Go to Render Dashboard**
   - Select your existing service: `pharmastock-web`

2. **Set Environment Variable** (if not already set)
   - Go to "Environment" tab
   - Add: `DATABASE_URL=postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres`
   - Click "Save Changes"

3. **Manual Deploy** (if auto-deploy is off)
   - Go to "Manual Deploy" tab
   - Select branch: `main`
   - Click "Deploy latest commit"

4. **Or Auto-Deploy** (if enabled)
   - Render will automatically deploy when you push to GitHub
   - Just push your code and wait!

---

## Step 3: Verify Deployment

### Check Deployment Logs
1. Go to Render Dashboard → Your Service → Logs
2. Look for:
   - ✅ `✅ Using Supabase PostgreSQL database`
   - ✅ `✅ Database manager initialized`
   - ✅ `🚀 Starting PharmaStock Web Application`
   - ❌ No errors about database connection

### Test Your App
1. Visit your Render URL: `https://pharmastock-web.onrender.com`
2. Check health endpoint: `https://pharmastock-web.onrender.com/api/health`
3. Should see: `"database": {"type": "PostgreSQL", ...}`

### Test Features
- [ ] Dashboard loads
- [ ] Stock view works
- [ ] Data refresh works
- [ ] Procurement bot works

---

## Troubleshooting

### "Using SQLite database" in logs
**Problem:** `DATABASE_URL` not set  
**Solution:** Add `DATABASE_URL` environment variable in Render dashboard

### Build fails
**Problem:** Missing dependencies or wrong Python version  
**Solution:** Check `requirements.txt` and set `PYTHON_VERSION=3.11.0`

### App doesn't start
**Problem:** Wrong start command or port  
**Solution:** Verify start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Database connection errors
**Problem:** Wrong `DATABASE_URL` format  
**Solution:** Verify connection string is URL-encoded correctly

---

## Quick Reference

### Git Commands
```powershell
cd C:\PharmaStockApp\web_app
git add .
git commit -m "Your commit message"
git push origin main
```

### Render Environment Variables
```
DATABASE_URL=postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres
PYTHON_VERSION=3.11.0
PORT=8000
```

### Render Service Settings
- **Root Directory**: `web_app`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --timeout-keep-alive 300`

---

## Next Steps After Deployment

1. ✅ Verify app loads successfully
2. ✅ Test all features
3. ✅ Configure credentials in Settings
4. ✅ Run initial data refresh
5. ✅ Share URL with users!

---

**Remember:** Always push to GitHub first, then Render will deploy automatically (if auto-deploy is enabled)!

