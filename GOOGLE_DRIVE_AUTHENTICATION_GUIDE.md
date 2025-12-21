# Google Drive Authentication Guide

## How Often Does Authentication Happen?

### **Answer: Only ONCE (or very rarely)**

Once you successfully authorize Google Drive access, you should **NEVER need to authorize again** unless:

1. **You revoke access** in your Google Account settings
2. **The refresh token expires** (very rare - Google refresh tokens typically last indefinitely)
3. **The token file is deleted** (`google_token.json`)
4. **You change the OAuth scopes** in your app

### How It Works

1. **First Time Authorization:**
   - Click "Get Authorization URL"
   - Authorize on Google consent screen
   - Token is saved to `google_token.json`
   - **This is the ONLY time you need to do this manually**

2. **Automatic Token Refresh:**
   - Access tokens expire after 1 hour
   - Refresh tokens are used automatically to get new access tokens
   - This happens **automatically in the background** - you don't need to do anything
   - The app handles this automatically when you use Google Drive features

3. **When You Use Google Drive:**
   - The app checks if the token is valid
   - If expired, it automatically refreshes using the refresh token
   - No user interaction needed!

## Why Is It Getting Stuck?

If the consent screen is stuck after clicking "Continue", it could be:

1. **Callback URL not working** - Check server logs
2. **Flow state lost** - The fix I just made should handle this
3. **Network/firewall issue** - Blocking the callback
4. **Browser blocking redirect** - Try a different browser

## Troubleshooting Stuck Authorization

### Step 1: Check Server Logs
Look at your terminal/console where the FastAPI server is running. You should see:
- `Received authorization code, completing authorization...`
- `✅ Authorization completed successfully`

If you see errors, that's the issue.

### Step 2: Check Browser Console
Open browser DevTools (F12) → Console tab
- Look for any JavaScript errors
- Check Network tab for the callback request

### Step 3: Verify Callback URL
Make sure the callback URL in Google Cloud Console is exactly:
```
http://localhost:8000/api/admin/drive/callback
```

### Step 4: Try Again
1. Close the consent screen tab
2. Go back to Admin page
3. Click "Get Authorization URL" again
4. Complete authorization

## After Successful Authorization

Once authorized:
- ✅ Token is saved to `web_app/google_token.json`
- ✅ You'll see "✅ Connected" status in Admin panel
- ✅ Database sync will work automatically
- ✅ No more authorization needed!

## Manual Token Refresh (If Needed)

If tokens somehow get corrupted, you can:
1. Delete `web_app/google_token.json`
2. Go to Admin page
3. Click "Get Authorization URL" again
4. Re-authorize (this is rare - should only happen once)

## Summary

- **First time:** Authorize once manually
- **After that:** Automatic token refresh - no user action needed
- **Frequency:** Should only authorize ONCE, then it works forever (or until you revoke access)

