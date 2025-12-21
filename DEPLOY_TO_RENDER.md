# 🚀 Complete Guide: Deploy PharmaStock App to Render.com

This guide will walk you through deploying your PharmaStock web app to Render.com step by step.

---

## 📋 Prerequisites

Before starting, make sure you have:
- ✅ A GitHub account (free)
- ✅ Your code ready in the `web_app` folder
- ✅ Google Cloud Console access (for Google Drive integration)

---

## Step 1: Prepare Your Code for GitHub

### 1.1 Initialize Git Repository

Open PowerShell/Terminal in your project root (`C:\PharmaStockApp`) and run:

```bash
cd web_app
git init
git add .
git commit -m "Initial commit - Ready for deployment"
```

### 1.2 Create GitHub Repository

1. Go to https://github.com and sign in
2. Click the **"+"** icon → **"New repository"**
3. Repository name: `pharmastock-web` (or your preferred name)
4. Description: "PharmaStock Inventory Management Web Application"
5. Choose **Private** (recommended) or Public
6. **DO NOT** initialize with README, .gitignore, or license (we already have files)
7. Click **"Create repository"**

### 1.3 Push Code to GitHub

After creating the repository, GitHub will show you commands. Run these in your terminal:

```bash
# Add your GitHub repository as remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/pharmastock-web.git

# Push code to GitHub
git branch -M main
git push -u origin main
```

**Note:** You'll be prompted for your GitHub username and password (or use a Personal Access Token).

---

## Step 2: Deploy to Render.com

### 2.1 Sign Up for Render

1. Go to **https://render.com**
2. Click **"Get Started for Free"**
3. Sign up with your **GitHub account** (recommended - easier integration)
4. Authorize Render to access your GitHub repositories

### 2.2 Create New Web Service

1. In Render dashboard, click **"New +"** button (top right)
2. Select **"Web Service"**
3. Connect your GitHub account if not already connected
4. Find and select your repository: `pharmastock-web` (or whatever you named it)
5. Click **"Connect"**

### 2.3 Configure Web Service

Fill in the following settings:

#### Basic Settings:
- **Name**: `pharmastock-web` (or your preferred name)
- **Region**: Choose closest to your users (e.g., `Oregon (US West)`)
- **Branch**: `main` (or `master` if that's your default branch)

#### Build & Deploy:
- **Root Directory**: `web_app` ⚠️ **IMPORTANT: Set this!**
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

#### Advanced Settings (click "Advanced"):
- **Auto-Deploy**: `Yes` (deploys automatically when you push to GitHub)

### 2.4 Add Persistent Disk (for Database)

**⚠️ CRITICAL:** Without this, your database will be lost on every deployment!

1. Scroll down to **"Disks"** section
2. Click **"Create Disk"**
3. Configure:
   - **Name**: `pharmastock-data`
   - **Mount Path**: `/app/cache` ⚠️ **Must match this exactly!**
   - **Size**: `10 GB` (free tier allows up to 10GB)
4. Click **"Create Disk"**

### 2.5 Environment Variables (Optional - Can add later)

You can add these now or later in the Environment tab:

- `PYTHON_VERSION`: `3.11.0`
- `PORT`: `8000` (Render sets this automatically, but good to have)

### 2.6 Deploy!

1. Review all settings
2. Click **"Create Web Service"**
3. Render will start building your app (this takes 5-10 minutes)
4. Watch the build logs - you'll see it installing dependencies

---

## Step 3: Get Your App URL

After deployment completes:

1. You'll see a **"Live"** status with a green dot
2. Your app URL will be: `https://pharmastock-web.onrender.com` (or your custom name)
3. **Save this URL** - you'll need it for Google Drive configuration!

---

## Step 4: Configure Google Drive Integration

### 4.1 Update OAuth Redirect URI

1. Go to **Google Cloud Console**: https://console.cloud.google.com
2. Select your project
3. Navigate to **APIs & Services** → **Credentials**
4. Click on your **OAuth 2.0 Client ID**
5. Under **"Authorized redirect URIs"**, click **"Add URI"**
6. Add: `https://pharmastock-web.onrender.com/api/admin/drive/callback`
   - ⚠️ Replace `pharmastock-web` with your actual Render app name
7. Click **"Save"**

### 4.2 Upload Google Credentials to Render

You have two options:

#### Option A: Environment Variable (Recommended)

1. In Render dashboard → Your service → **"Environment"** tab
2. Click **"Add Environment Variable"**
3. Key: `GOOGLE_CREDENTIALS_JSON`
4. Value: Copy the entire contents of your `web_app/google_credentials.json` file
   - Open the file in a text editor
   - Copy everything (including all the `{` and `}`)
   - Paste into the Value field
5. Click **"Save Changes"**

#### Option B: Upload to Persistent Disk

1. SSH into your Render service (if available)
2. Or use Render's Shell feature to upload the file
3. Place it at `/app/cache/google_credentials.json`

---

## Step 5: Initial Setup

### 5.1 Access Your App

1. Visit your Render URL: `https://pharmastock-web.onrender.com`
2. You should see the login page
3. Login with your admin credentials (the ones you created locally)

### 5.2 Authorize Google Drive

1. After logging in, go to **"Admin"** tab
2. Click **"Authorize Google Drive"**
3. Complete the OAuth flow
4. You should see "Google Drive authorized successfully"

### 5.3 Upload Initial Database

1. In Admin page, click **"Upload Database"**
2. Select your local `pharma_stock.db` file
3. Wait for upload to complete
4. Your database is now synced to Google Drive!

---

## Step 6: Test Everything

### 6.1 Test Basic Functionality

- ✅ Login works
- ✅ Dashboard loads
- ✅ Stock view loads
- ✅ Data refresh works
- ✅ Google Drive sync works

### 6.2 Test from Different Browser/Device

- Open your Render URL on your phone or another computer
- Login and verify everything works
- This confirms your app is truly accessible from anywhere!

---

## 🎉 You're Live!

Your app is now deployed and accessible at: `https://pharmastock-web.onrender.com`

**Share this URL with your users** - they can access it from any browser, anywhere!

---

## 📝 Important Notes

### Free Tier Limitations

- **Sleep Mode**: App sleeps after 15 minutes of inactivity
- **Wake Time**: First request after sleep takes ~30 seconds
- **Solution**: Consider upgrading to paid plan ($7/month) for always-on service

### Database Storage

- Database is stored on **persistent disk** (`/app/cache/pharma_stock.db`)
- Also synced to **Google Drive** for backup
- Multiple users share the same database (synced via Google Drive)

### Updating Your App

Whenever you make changes:

1. Commit changes: `git add . && git commit -m "Your changes"`
2. Push to GitHub: `git push origin main`
3. Render will **automatically deploy** the new version!

---

## 🔧 Troubleshooting

### App Won't Start

**Check Build Logs:**
1. Render Dashboard → Your Service → **"Logs"** tab
2. Look for errors in red
3. Common issues:
   - Missing dependencies in `requirements.txt`
   - Wrong root directory (should be `web_app`)
   - Wrong start command

### Database Not Persisting

**Check Disk Mount:**
1. Render Dashboard → Your Service → **"Disks"** tab
2. Verify disk is mounted at `/app/cache`
3. Check disk has available space

### Google Drive Not Working

**Check OAuth Configuration:**
1. ✅ Verify redirect URI in Google Cloud Console matches your Render URL exactly
   - Should be: `https://YOUR-APP-NAME.onrender.com/api/admin/drive/callback`
2. ✅ Check `GOOGLE_CREDENTIALS_JSON` environment variable is set in Render
   - Go to Render Dashboard → Your Service → Environment tab
   - Verify the variable exists and contains valid JSON
3. ✅ Check Render logs for OAuth errors
   - Look for "redirect_uri_mismatch" or "access_denied" errors
4. ✅ Verify the app detected Render environment
   - Check logs for: "🌐 Detected Render environment. Using callback URL: ..."

### App Takes Forever to Load

**First Request After Sleep:**
- This is normal on free tier
- First request wakes up the app (~30 seconds)
- Subsequent requests are fast

**Solution:** Upgrade to paid plan for always-on service

---

## 🆘 Need Help?

- **Render Documentation**: https://render.com/docs
- **Render Support**: https://render.com/docs/support
- **Check Logs**: Render Dashboard → Your Service → Logs tab

---

## ✅ Deployment Checklist

- [ ] Code pushed to GitHub
- [ ] Render account created
- [ ] Web service created with correct settings
- [ ] Persistent disk added (`/app/cache`, 10GB)
- [ ] App deployed successfully
- [ ] Google Drive redirect URI updated
- [ ] Google credentials uploaded to Render
- [ ] App accessible via Render URL
- [ ] Login works
- [ ] Google Drive authorized
- [ ] Database uploaded
- [ ] Tested from different device/browser

---

**🎊 Congratulations! Your app is now live on the internet!**

