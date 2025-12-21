# 🚀 Quick Deploy Guide - Get Your App Link in 10 Minutes

## Step 1: Deploy to Render.com (Free)

### 1. Sign Up for Render
1. Go to **https://render.com**
2. Click **"Get Started for Free"**
3. Sign up with your **GitHub account** (easiest way)

### 2. Create Web Service
1. In Render dashboard, click **"New +"** → **"Web Service"**
2. Connect your GitHub account if prompted
3. Select repository: **`pharmastock-app`** (or `JACKSON-PHARM/pharma-stock-app`)
4. Click **"Connect"**

### 3. Configure Settings

**IMPORTANT Settings:**
- **Name**: `pharmastock-web` (or your choice)
- **Root Directory**: `web_app` ⚠️ **MUST SET THIS!**
- **Branch**: `master` (or `main` if that's what you use)
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### 4. Persistent Disk (OPTIONAL - Free Tier)

**Note:** Render free tier doesn't support persistent disks. The app will work without it!

**How it works without disk:**
- Database is stored in temporary directory (`/tmp/pharmastock_cache`)
- Data is synced from/to Google Drive on startup/shutdown
- **Important:** Data will be lost on app restart, but will be restored from Google Drive

**If you upgrade to paid tier ($7/month):**
1. Scroll to **"Disks"** section
2. Click **"Create Disk"**
3. Set:
   - **Name**: `pharmastock-data`
   - **Mount Path**: `/app/cache` ⚠️ **Must be exact!**
   - **Size**: `10 GB`
4. Click **"Create Disk"**

### 5. Deploy!

1. Click **"Create Web Service"**
2. Wait 5-10 minutes for build
3. Watch the logs - you'll see it installing packages

### 6. Get Your Link! 🎉

Once deployment completes:
- Status will show **"Live"** (green dot)
- Your URL will be: **`https://pharmastock-web.onrender.com`**
- **Save this URL!** This is your app link!

---

## Step 2: Quick Test

1. Visit your Render URL
2. You should see the login page
3. Login with your admin credentials

---

## ⚠️ Important Notes

### Free Tier Limitations:
- App sleeps after 15 minutes of inactivity
- First request after sleep takes ~30 seconds to wake up
- This is normal for free tier

### To Keep App Always Awake:
- Upgrade to Render paid plan ($7/month)
- Or use a service like UptimeRobot to ping your URL every 10 minutes

---

## 🔧 If Something Goes Wrong

### Check Build Logs:
1. Render Dashboard → Your Service → **"Logs"** tab
2. Look for errors in red
3. Common fixes:
   - Make sure **Root Directory** is set to `web_app`
   - Verify **Start Command** is correct
   - Check that all files are pushed to GitHub

### Common Issues:

**"Module not found" error:**
- Check `requirements.txt` has all dependencies
- Rebuild the service

**"Database not found" error:**
- Make sure persistent disk is mounted at `/app/cache`
- Check disk has space

---

## ✅ You're Done!

Your app is now live at: **`https://pharmastock-web.onrender.com`**

Share this link with anyone who needs access!

---

## Next Steps (Optional):

1. **Configure Google Drive** (see DEPLOYMENT_GUIDE.md)
2. **Set up custom domain** (Render paid plan)
3. **Enable auto-deploy** (already enabled by default)

