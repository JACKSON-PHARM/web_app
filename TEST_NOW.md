# 🧪 TEST YOUR WEB APP NOW

## ✅ What's Been Set Up

1. ✅ **Credentials file copied** → `web_app/google_credentials.json`
2. ✅ **OAuth callback flow** → Web application compatible
3. ✅ **Admin authorization button** → Added to admin panel
4. ✅ **All code updated** → Ready for testing

## 🚀 Quick Test Steps

### Step 1: Start the Server

```bash
cd web_app
python run.py
```

**Expected output:**
```
🚀 Starting PharmaStock Web Application
⚠️ Google Drive not authenticated - authorization required
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 2: Open Browser

Visit: **http://localhost:8000**

### Step 3: Login

- Email: `controleddrugsalesdaimamerudda@gmail.com`
- Click "Login"

### Step 4: Authorize Google Drive (FIRST TIME ONLY)

1. Go to **Admin** page: http://localhost:8000/admin
2. Click **"Get Authorization URL"** button
3. A new window will open with Google OAuth
4. Sign in with `controleddrugsalesdaimamerudda@gmail.com`
5. Click **"Allow"** to authorize
6. You'll be redirected back → Should see "✅ Authorization Successful!"
7. Close the success window

### Step 5: Configure Credentials

1. Go to **Settings**: http://localhost:8000/settings
2. Enter **NILA** username/password → Test → Save
3. Enter **DAIMA** username/password → Test → Save

### Step 6: Refresh Data

1. Go to **Dashboard**: http://localhost:8000/dashboard
2. Click **"Refresh All Data"**
3. Enter credentials (or leave empty if saved)
4. Wait for completion
5. Data should appear!

## ✅ Verification Checklist

- [ ] Server starts without errors
- [ ] Can login with admin email
- [ ] Admin panel loads
- [ ] "Get Authorization URL" button works
- [ ] Google OAuth opens in new window
- [ ] Can authorize successfully
- [ ] Redirects back to success page
- [ ] Can configure NILA/DAIMA credentials
- [ ] Can trigger refresh
- [ ] Dashboard shows data

## 🔧 Troubleshooting

### "Google credentials file not found"
- ✅ Already fixed - file is at `web_app/google_credentials.json`

### "Invalid Redirect URI"
- Make sure in Google Cloud Console:
  - **Authorized JavaScript origins:** `http://localhost:8000`
  - **Authorized redirect URIs:** `http://localhost:8000/api/admin/drive/callback`

### "Email not licensed"
- Admin email is auto-licensed
- Add other emails via Admin panel

### "Google Drive not authenticated"
- Visit Admin → Click "Get Authorization URL"
- Complete OAuth flow

## 📝 Important URLs

- **App:** http://localhost:8000
- **Dashboard:** http://localhost:8000/dashboard
- **Admin:** http://localhost:8000/admin
- **Settings:** http://localhost:8000/settings
- **Auth URL API:** http://localhost:8000/api/admin/drive/authorize

## 🎉 Success Indicators

✅ Server runs without errors  
✅ Can login  
✅ Google Drive authorized  
✅ Credentials saved  
✅ Refresh works  
✅ Dashboard populated  

## 📚 Next Steps After Testing

1. Add more licensed emails via Admin panel
2. Test auto-refresh (runs every 60 minutes)
3. Deploy to production (update redirect URIs)
4. Share with clients

---

**Ready to test?** Run `python run.py` in the `web_app` folder!

