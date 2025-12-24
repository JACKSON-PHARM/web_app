# 🚀 Deploy to Render - Step by Step

## ✅ Code is on GitHub - Now Configure Render!

Your code is successfully pushed to GitHub. Now let's deploy it on Render.

---

## Step 1: Go to Render Dashboard

1. **Open**: https://dashboard.render.com
2. **Sign in** with GitHub (if not already signed in)

---

## Step 2: Choose Your Service

You have two options:

### Option A: Update Existing Service (Recommended)

1. **Find your existing service**:
   - Look for: `web_app` or `pharma-stock-app`
   - Click on it to open

2. **Set Environment Variable** (CRITICAL!):
   - Go to **"Environment"** tab
   - Click **"Add Environment Variable"**
   - **Key**: `DATABASE_URL`
   - **Value**: `postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres`
   - Click **"Save"**
   - Click **"Save Changes"** at bottom

3. **Add Other Variables** (if not already set):
   - `PYTHON_VERSION` = `3.11.0`
   - `PORT` = `8000`

4. **Deploy**:
   - Go to **"Manual Deploy"** tab
   - Select branch: `main`
   - Click **"Deploy latest commit"**
   - Wait 5-10 minutes for deployment

### Option B: Create New Service

1. **Click "New +"** → **"Web Service"**

2. **Connect Repository**:
   - Select: `JACKSON-PHARM/web_app`
   - Click **"Connect"**

3. **Configure Service**:
   - **Name**: `pharmastock-web` (or your preferred name)
   - **Root Directory**: Leave empty (or `web_app` if code is in subfolder)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --timeout-keep-alive 300`

4. **Set Environment Variables** (CRITICAL!):
   - Click **"Add Environment Variable"**
   - **Key**: `DATABASE_URL`
   - **Value**: `postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres`
   - Click **"Save"**
   - Add: `PYTHON_VERSION` = `3.11.0`
   - Add: `PORT` = `8000`

5. **Create Service**:
   - Click **"Create Web Service"**
   - Wait 5-10 minutes for build and deployment

---

## Step 3: Verify Deployment

### Check Logs

1. Go to your service → **"Logs"** tab
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

## ⚠️ Important Notes

### If You See "Using SQLite database" in Logs
- **Problem**: `DATABASE_URL` environment variable not set
- **Solution**: Go to Environment tab and add `DATABASE_URL`

### If Build Fails
- Check that `requirements.txt` exists
- Verify Python version is set to `3.11.0`

### If App Doesn't Start
- Check start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Verify `PORT` environment variable is set

---

## Quick Checklist

- [ ] Go to Render Dashboard
- [ ] Find or create service
- [ ] Set `DATABASE_URL` environment variable (MOST IMPORTANT!)
- [ ] Set `PYTHON_VERSION=3.11.0`
- [ ] Set `PORT=8000`
- [ ] Deploy (manual or auto)
- [ ] Check logs for Supabase connection
- [ ] Test app at Render URL

---

## Next Steps After Deployment

1. ✅ Test dashboard
2. ✅ Test stock view
3. ✅ Configure credentials in Settings
4. ✅ Run data refresh
5. ✅ Test procurement bot

---

**Ready?** Go to Render Dashboard now and set that `DATABASE_URL`! 🚀

