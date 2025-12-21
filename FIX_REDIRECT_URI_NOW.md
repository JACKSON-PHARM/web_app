# ⚠️ URGENT: Fix Redirect URI Mismatch

## The Problem
Your Google Cloud Console has:
- **Current Redirect URI**: `http://localhost:8000/auth/callback` ❌

But your app needs:
- **Required Redirect URI**: `http://localhost:8000/api/admin/drive/callback` ✅

## The Fix (Do This Now)

### Step 1: Update Redirect URI in Google Cloud Console

1. In the Google Cloud Console page you have open:
   - Find the **"Authorized redirect URIs"** section
   - You currently have: `http://localhost:8000/auth/callback`

2. **Change it to:**
   ```
   http://localhost:8000/api/admin/drive/callback
   ```

3. **Steps:**
   - Click on the existing URI field: `http://localhost:8000/auth/callback`
   - Delete it or edit it
   - Type exactly: `http://localhost:8000/api/admin/drive/callback`
   - Click **"Save"** button at the bottom

### Step 2: Verify

Make sure:
- ✅ Protocol: `http://` (not https)
- ✅ Domain: `localhost` (not 127.0.0.1)
- ✅ Port: `8000`
- ✅ Path: `/api/admin/drive/callback` (exactly this, no trailing slash)

### Step 3: Wait and Test

- Wait 1-2 minutes for changes to propagate
- Go back to your admin page
- Click "Get Authorization URL" again
- It should work now!

## Why This Happened

The redirect URI must match **exactly** what your application sends to Google. Your app is configured to use `/api/admin/drive/callback`, but Google Cloud Console had `/auth/callback`.

## Current App Configuration

Your app is configured in `web_app/app/config.py`:
```python
GOOGLE_OAUTH_CALLBACK_URL: str = "http://localhost:8000/api/admin/drive/callback"
```

This is what Google Cloud Console must have!

