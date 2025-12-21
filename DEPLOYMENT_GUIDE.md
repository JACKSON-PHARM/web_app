# Deployment Guide for PharmaStock Web App

This guide will help you deploy the PharmaStock Web App to the cloud for free using Render.com.

## Prerequisites

1. A GitHub account (free)
2. A Render.com account (free tier available)
3. Google Cloud Console setup (for Google Drive integration)

## Step 1: Prepare Your Code

1. Make sure all your code is committed to a Git repository
2. Push your code to GitHub (create a private repo if needed)

## Step 2: Deploy to Render.com (Free Tier)

### Option A: Using Render Dashboard

1. **Sign up/Login to Render**
   - Go to https://render.com
   - Sign up with your GitHub account (free)

2. **Create a New Web Service**
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Select the repository containing your web app

3. **Configure the Service**
   - **Name**: `pharmastock-web` (or your preferred name)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Root Directory**: `web_app` (if your web app is in a subdirectory)

4. **Environment Variables**
   Add these environment variables in Render dashboard:
   ```
   PYTHON_VERSION=3.11.0
   PORT=8000
   ```

5. **Persistent Disk (for Database)**
   - Go to "Disks" tab
   - Create a new disk named `pharmastock-data`
   - Mount path: `/app/cache`
   - Size: 10GB (free tier allows up to 10GB)

6. **Deploy**
   - Click "Create Web Service"
   - Render will automatically build and deploy your app
   - Wait for deployment to complete (5-10 minutes)

7. **Get Your URL**
   - Once deployed, you'll get a URL like: `https://pharmastock-web.onrender.com`
   - Share this URL with your users!

### Option B: Using Render.yaml (Recommended)

1. **Push render.yaml to your repo**
   - The `render.yaml` file is already created in `web_app/`
   - Commit and push it to GitHub

2. **Deploy via Render Dashboard**
   - Go to Render Dashboard
   - Click "New +" → "Blueprint"
   - Connect your GitHub repo
   - Render will automatically detect `render.yaml` and configure everything

## Step 3: Configure Google Drive Integration

1. **Update OAuth Redirect URI**
   - Go to Google Cloud Console
   - Navigate to APIs & Services → Credentials
   - Edit your OAuth 2.0 Client ID
   - Add your Render URL to Authorized redirect URIs:
     ```
     https://your-app-name.onrender.com/api/admin/drive/callback
     ```

2. **Upload Credentials**
   - In Render dashboard, go to your service → Environment
   - Add environment variable:
     ```
     GOOGLE_CREDENTIALS_JSON=<paste your google_credentials.json content>
     ```
   - Or upload `google_credentials.json` file to Render's persistent disk

## Step 4: Initial Setup

1. **Access Your App**
   - Visit your Render URL
   - Login with admin credentials

2. **Authorize Google Drive**
   - Go to Admin page
   - Click "Authorize Google Drive"
   - Complete OAuth flow
   - Upload initial database

3. **Test the App**
   - Verify dashboard loads
   - Test data refresh
   - Verify Google Drive sync works

## Alternative Free Hosting Options

### Railway.app (Free Tier Available)
1. Sign up at https://railway.app
2. Connect GitHub repo
3. Deploy automatically
4. Similar setup to Render

### Fly.io (Free Tier Available)
1. Sign up at https://fly.io
2. Install Fly CLI: `curl -L https://fly.io/install.sh | sh`
3. Run: `fly launch`
4. Follow prompts

### PythonAnywhere (Free Tier Available)
1. Sign up at https://www.pythonanywhere.com
2. Upload your code via web interface
3. Configure WSGI file
4. Deploy

## Important Notes

1. **Free Tier Limitations**
   - Render free tier: App sleeps after 15 minutes of inactivity
   - First request after sleep takes ~30 seconds to wake up
   - Consider upgrading to paid plan for production use

2. **Database Storage**
   - Database is stored on persistent disk
   - Also synced to Google Drive for backup
   - Multiple users will share the same database

3. **Security**
   - Use strong admin passwords
   - Keep Google credentials secure
   - Regularly backup database to Google Drive

4. **Scaling**
   - Free tier supports limited concurrent users
   - For production, consider paid plans

## Troubleshooting

### App Not Starting
- Check Render logs: Dashboard → Your Service → Logs
- Verify all environment variables are set
- Check that `requirements.txt` is correct

### Google Drive Not Working
- Verify redirect URI matches Render URL
- Check that credentials are properly uploaded
- Review logs for OAuth errors

### Database Issues
- Ensure persistent disk is mounted correctly
- Check disk space usage
- Verify Google Drive sync is working

## Support

For issues, check:
- Render documentation: https://render.com/docs
- Application logs in Render dashboard
- Google Cloud Console for OAuth issues

