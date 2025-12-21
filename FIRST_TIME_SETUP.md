# 🚀 First-Time Setup Guide

## Step 1: Start the Application

```bash
cd web_app
python run.py
```

## Step 2: Create Your Admin Account

1. Open browser: **http://localhost:8000**

2. You'll see a **"First Time Setup"** notice

3. Fill in the registration form:
   - **Your Name:** Enter your name (e.g., "John Doe")
   - **Email Address:** Enter your email (e.g., "admin@example.com")

4. Click **"Create Admin Account"**

5. You'll be automatically logged in and redirected to the dashboard

## Step 3: Create User Accounts (After Login)

Once you're logged in as admin:

1. Go to **Admin** page: http://localhost:8000/admin

2. In the **"License Management"** section:
   - Enter the user's email address
   - Click **"Add License"**

3. The user can now login with their email address

## Step 4: Authorize Google Drive

1. Go to **Admin** page
2. Click **"Get Authorization URL"**
3. Complete OAuth in the new window
4. You'll be redirected back automatically

## Step 5: Configure API Credentials

1. Go to **Settings** page
2. Enter **NILA** credentials → Test → Save
3. Enter **DAIMA** credentials → Test → Save

## Step 6: Refresh Data

1. Go to **Dashboard**
2. Click **"Refresh All Data"**
3. Wait for completion
4. Data should appear!

## ✅ You're All Set!

- ✅ Admin account created
- ✅ Google Drive authorized
- ✅ Credentials configured
- ✅ Data refreshed

## 📝 Notes

- **First admin:** Created during first-time setup
- **Additional users:** Created by admin via Admin panel
- **User login:** Users login with their email (no password needed)
- **Admin access:** Only admins can add/remove users

## 🔒 Security

- Only licensed emails can login
- Admin emails have full access
- Regular users have limited access
- All access is logged

