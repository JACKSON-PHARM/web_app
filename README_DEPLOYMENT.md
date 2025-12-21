# Quick Start: Deploy to Render.com (FREE)

## Step 1: Push Code to GitHub
```bash
cd web_app
git init
git add .
git commit -m "Initial commit"
# Create a new repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

## Step 2: Deploy on Render.com

1. **Sign up**: Go to https://render.com and sign up with GitHub

2. **Create Web Service**:
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Select your repo

3. **Configure**:
   - **Name**: `pharmastock-web`
   - **Root Directory**: `web_app` (if your web app is in a subdirectory)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

4. **Add Persistent Disk** (for database):
   - Go to "Disks" tab
   - Click "Create Disk"
   - Name: `pharmastock-data`
   - Mount Path: `/app/cache`
   - Size: 10GB

5. **Deploy**: Click "Create Web Service"

6. **Get Your URL**: After deployment (5-10 min), you'll get a URL like:
   ```
   https://pharmastock-web.onrender.com
   ```

## Step 3: Configure Google Drive

1. **Update OAuth Redirect URI**:
   - Go to Google Cloud Console → APIs & Services → Credentials
   - Edit your OAuth 2.0 Client ID
   - Add redirect URI: `https://your-app-name.onrender.com/api/admin/drive/callback`

2. **Upload Credentials**:
   - In Render dashboard → Environment
   - Add environment variable (or upload file to persistent disk):
     ```
     GOOGLE_CREDENTIALS_JSON=<paste your google_credentials.json content>
     ```

## Step 4: Access Your App

1. Visit your Render URL
2. Login with admin credentials
3. Go to Admin page → Authorize Google Drive
4. Upload initial database

## Share with Users

Simply share your Render URL with your users! They can access the app from any browser.

## Important Notes

- **Free Tier**: App sleeps after 15 min of inactivity (first request takes ~30 sec to wake up)
- **Database**: Stored on persistent disk + synced to Google Drive
- **Multiple Users**: All users share the same database (synced via Google Drive)

## Troubleshooting

- Check logs: Render Dashboard → Your Service → Logs
- Verify environment variables are set
- Check Google Drive OAuth redirect URI matches your Render URL

