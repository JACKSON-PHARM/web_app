# 🚀 Quick Start Guide

## ✅ Step 1: Verify Setup

Your credentials file is at: `web_app/google_credentials.json` ✅

## ✅ Step 2: Install Dependencies

```bash
cd web_app
pip install -r requirements.txt
```

## ✅ Step 3: Start the Server

```bash
python run.py
```

**Expected output:**
```
🚀 Starting PharmaStock Web Application
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## ✅ Step 4: Open Browser

Visit: **http://localhost:8000**

## ✅ Step 5: First-Time Setup (One-Time Only)

### A. Login
- Email: `controleddrugsalesdaimamerudda@gmail.com` (auto-admin)
- Click "Login"

### B. Authorize Google Drive (One-Time)
1. Go to **Admin** page → http://localhost:8000/admin
2. Click **"Get Authorization URL"** button
3. Copy the `authorization_url` from the response
4. Open it in your browser
5. Sign in with `controleddrugsalesdaimamerudda@gmail.com`
6. Click **"Allow"**
7. You'll be redirected back - should see "✅ Authorization Successful!"

### C. Configure API Credentials
1. Go to **Settings** → http://localhost:8000/settings
2. Enter **NILA** credentials → Test → Save
3. Enter **DAIMA** credentials → Test → Save

### D. First Data Refresh
1. Go to **Dashboard** → http://localhost:8000/dashboard
2. Click **"Refresh All Data"**
3. Enter credentials when prompted (or leave empty if saved)
4. Wait for completion
5. Data should appear!

## ✅ Step 6: Verify Everything Works

- [ ] ✅ Can login
- [ ] ✅ Google Drive authorized
- [ ] ✅ Credentials saved
- [ ] ✅ Refresh works
- [ ] ✅ Dashboard shows data
- [ ] ✅ Tables populated

## 🎉 Success!

Your web application is running!

## 📝 Important URLs

- **Login:** http://localhost:8000
- **Dashboard:** http://localhost:8000/dashboard
- **Settings:** http://localhost:8000/settings
- **Admin:** http://localhost:8000/admin
- **Get Auth URL:** http://localhost:8000/api/admin/drive/authorize

## 🔧 Troubleshooting

**"Google credentials file not found"**
- Make sure `google_credentials.json` is in `web_app/` folder

**"Email not licensed"**
- The admin email is auto-licensed
- Add other emails via Admin panel

**"Google Drive not authenticated"**
- Visit `/api/admin/drive/authorize` and complete OAuth

**"Database not found"**
- Trigger a refresh - it will create the database

## 📚 Next Steps

- Add more licensed emails via Admin panel
- Configure auto-refresh interval
- Deploy to production (see DEPLOYMENT.md)
