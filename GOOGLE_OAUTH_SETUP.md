# Google OAuth2 Setup - Redirect URIs Guide

## Redirect URIs for PharmaStock Web Application

### Option 1: Out-of-Band (Recommended for Initial Setup)

**Use this for first-time authorization (simplest):**

```
urn:ietf:wg:oauth:2.0:oob
```

**How it works:**
- User visits authorization URL
- Copies authorization code manually
- Pastes code into application
- No callback URL needed

**When to use:**
- ✅ Initial setup and testing
- ✅ Desktop/server applications
- ✅ When you don't have a public URL yet

### Option 2: Local Development (For Testing)

**If running locally:**

```
http://localhost:8000/auth/callback
http://localhost:8000/oauth2callback
```

**When to use:**
- ✅ Testing OAuth flow locally
- ✅ Development environment
- ⚠️ Only works on your local machine

### Option 3: Production (After Deployment)

**After you deploy your app, use your production URL:**

```
https://your-domain.com/auth/callback
https://your-domain.com/oauth2callback
```

**Examples:**
- If using Google Cloud Run: `https://pharmastock-web-xxxxx.run.app/auth/callback`
- If using your own domain: `https://pharmastock.yourdomain.com/auth/callback`

## Recommended Setup

### For Initial Setup (Use This Now):

1. **In Google Cloud Console, add these redirect URIs:**

   ```
   urn:ietf:wg:oauth:2.0:oob
   http://localhost:8000/auth/callback
   ```

2. **The app will use `urn:ietf:wg:oauth:2.0:oob` by default**
   - This means you'll copy-paste the authorization code
   - No callback URL needed
   - Works immediately

### After Deployment:

1. **Add your production redirect URI:**
   ```
   https://your-production-url.com/auth/callback
   ```

2. **Update the app to use callback URL** (optional - can keep using oob)

## Current Implementation

The app currently uses **`urn:ietf:wg:oauth:2.0:oob`** which means:
- ✅ No redirect URI configuration needed initially
- ✅ Works immediately
- ✅ User copies code manually (one-time setup)

## Step-by-Step Setup

### In Google Cloud Console:

1. Go to **APIs & Services** → **Credentials**
2. Click on your OAuth 2.0 Client ID
3. Under **Authorized redirect URIs**, click **+ ADD URI**
4. Add these URIs (one at a time):

   ```
   urn:ietf:wg:oauth:2.0:oob
   ```

   (Optional for later):
   ```
   http://localhost:8000/auth/callback
   ```

5. Click **SAVE**

### First-Time Authorization:

1. Run the app: `python run.py`
2. App will show authorization URL
3. Visit URL in browser
4. Sign in with `controleddrugsalesdaimamerudda@gmail.com`
5. Copy the authorization code shown
6. Paste code when app prompts
7. Token saved automatically

## Important Notes

- **`urn:ietf:wg:oauth:2.0:oob`** is the simplest option - use this for now
- You only need to authorize **once** - token is saved
- After first authorization, app works automatically
- If token expires, app will refresh automatically
- No need to change redirect URI unless you want web-based callback

## Summary

**For now, just add:**
```
urn:ietf:wg:oauth:2.0:oob
```

This is the simplest option and works immediately. You can add callback URLs later if needed.

