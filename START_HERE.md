# 🚀 START HERE - Quick Setup & Test

## ✅ Step 1: Verify Credentials File

Your credentials file should be at: `web_app/google_credentials.json`

**Check:**
```powershell
cd web_app
dir google_credentials.json
```

If it exists, you're good! If not, it was copied automatically.

## ✅ Step 2: Install Dependencies

```bash
cd web_app
pip install -r requirements.txt
```

## ✅ Step 3: Start the Application

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

## ✅ Step 5: First-Time Setup

### A. Login
- Email: `controleddrugsalesdaimamerudda@gmail.com` (auto-licensed as admin)
- Click "Login"

### B. Authorize Google Drive
1. Go to **Admin** page (or visit: http://localhost:8000/admin)
2. Click **"Get Authorization URL"** button
3. Copy the URL shown
4. Visit it in browser
5. Sign in with `controleddrugsalesdaimamerudda@gmail.com`
6. Click **"Allow"**
7. You'll be redirected back - should see "Authorization Successful!"

### C. Configure Credentials
1. Go to **Settings**
2. Enter NILA username/password → Test → Save
3. Enter DAIMA username/password → Test → Save

### D. Refresh Data
1. Go to **Dashboard**
2. Click **"Refresh All Data"**
3. Enter credentials when prompted
4. Wait for refresh to complete
5. Data should appear!

## ✅ Step 6: Verify It Works

- [ ] Can login
- [ ] Google Drive authorized
- [ ] Credentials saved
- [ ] Refresh works
- [ ] Dashboard shows data

## 🎉 Success!

Your web application is now running! 

**Next:** Add more licensed emails and deploy to production.

## 📚 More Help

- `TESTING_GUIDE.md` - Detailed testing steps
- `QUICK_START.md` - Quick reference
- `DEPLOYMENT.md` - Production deployment

