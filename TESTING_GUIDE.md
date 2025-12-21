# Testing Guide - PharmaStock Web Application

## Step 1: Verify Credentials File

✅ **Credentials file should be at:** `web_app/google_credentials.json`

Check if it exists:
```bash
cd web_app
dir google_credentials.json
```

If missing, copy from Downloads:
```powershell
Copy-Item "C:\Users\Envy\Downloads\client_secret_497673348686-evbo069r6n7m4en8q5hos0d5muf4j1ik.apps.googleusercontent.com.json" -Destination "google_credentials.json"
```

## Step 2: Install Dependencies

```bash
cd web_app
pip install -r requirements.txt
```

## Step 3: Start the Application

```bash
python run.py
```

Or:
```bash
python -m app.main
```

You should see:
```
🚀 Starting PharmaStock Web Application
INFO:     Started server process
INFO:     Waiting for application startup.
⚠️ Google Drive not authenticated - authorization required
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## Step 4: Access the Application

Open browser: **http://localhost:8000**

## Step 5: First-Time Setup

### 5.1: Login

1. You'll see the login page
2. Enter your email (must be licensed)
3. Click "Login"

**Note:** The admin email (`controleddrugsalesdaimamerudda@gmail.com`) is automatically licensed.

### 5.2: Authorize Google Drive

1. After login, go to **Admin** page (or visit: http://localhost:8000/admin)
2. Click **"Get Authorization URL"** or visit: http://localhost:8000/api/admin/drive/authorize
3. Copy the `authorization_url` from the response
4. Visit that URL in your browser
5. Sign in with `controleddrugsalesdaimamerudda@gmail.com`
6. Click **"Allow"** to authorize
7. You'll be redirected back to the app
8. Should see "Authorization Successful!"

### 5.3: Configure Credentials

1. Go to **Settings** page
2. Enter NILA credentials:
   - Username: (your NILA username)
   - Password: (your NILA password)
   - Click **"Test Connection"**
3. Enter DAIMA credentials:
   - Username: (your DAIMA username)
   - Password: (your DAIMA password)
   - Click **"Test Connection"**
4. Click **"Save All Settings"**

### 5.4: Trigger First Data Refresh

1. Go to **Dashboard**
2. Click **"Refresh All Data"**
3. Enter credentials when prompted:
   - NILA username/password (or leave empty)
   - DAIMA username/password (or leave empty)
4. Click OK
5. Wait for refresh to complete
6. Data should appear in tables

## Step 6: Verify Everything Works

### Check Dashboard
- ✅ New Arrivals table shows data
- ✅ Priority Items table shows data
- ✅ Tables are populated

### Check Google Drive
1. Go to Admin → **"Google Drive Info"**
2. Should show database exists, size, modified time
3. Click **"Sync Database from Drive"** to test download

### Check Auto-Refresh
1. Go to Dashboard
2. Check **"Last refresh"** status
3. Wait for auto-refresh interval (default: 60 minutes)
4. Or trigger manual refresh

## Common Issues & Solutions

### "Google credentials file not found"
- **Solution:** Copy `google_credentials.json` to `web_app/` folder

### "Email not licensed"
- **Solution:** Add email to `license_db.json`:
  ```json
  {
    "licensed_emails": ["your-email@example.com"],
    "admin_emails": ["controleddrugsalesdaimamerudda@gmail.com"]
  }
  ```

### "Google Drive not authenticated"
- **Solution:** Visit `/api/admin/drive/authorize` and complete OAuth flow

### "Database not found"
- **Solution:** Trigger a refresh - it will create the database

### Refresh not working
- **Solution:** Check credentials in Settings, verify API URLs are correct

## Testing Checklist

- [ ] Application starts without errors
- [ ] Can login with licensed email
- [ ] Google Drive authorization works
- [ ] Can configure NILA/DAIMA credentials
- [ ] Can trigger manual refresh
- [ ] Dashboard shows data
- [ ] Google Drive sync works
- [ ] Auto-refresh scheduler running

## Next Steps After Testing

1. **Add more licensed emails** via Admin panel
2. **Deploy to production** (see DEPLOYMENT.md)
3. **Configure production redirect URIs** in Google Console
4. **Set up SSL/HTTPS** for production
5. **Share URL with clients**

## Quick Test Commands

```bash
# Check if app is running
curl http://localhost:8000/health

# Test login (replace email)
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "controleddrugsalesdaimamerudda@gmail.com"}'

# Get authorization URL (after login, use token)
curl http://localhost:8000/api/admin/drive/authorize \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Transition from Desktop to Web

### What Changed:
- ✅ **No .exe needed** - Just run Python server
- ✅ **Browser access** - Users access via URL
- ✅ **Google Drive storage** - Database in cloud
- ✅ **Shared data** - Everyone sees same database
- ✅ **Auto-refresh** - Scheduled updates

### What Stayed the Same:
- ✅ **All features** - Dashboard, stock view, etc.
- ✅ **Same data** - Database schema unchanged
- ✅ **Same fetchers** - All data sources work
- ✅ **Same credentials** - NILA/DAIMA API access

### Benefits:
- ✅ **No installation** - Just browser
- ✅ **Always updated** - Auto-refresh
- ✅ **Multi-user** - Shared database
- ✅ **Easy updates** - Deploy new version

