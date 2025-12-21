# Check OAuth Configuration - Troubleshooting Guide

## If Authorization is Failing Silently

### Step 1: Check Server Logs
**Most Important!** Look at your terminal/console where FastAPI is running. You should see:
- `🔵 Callback received - Code: ...`
- `🔄 Exchanging authorization code for token...`
- `✅ Token received, saving credentials...`
- OR error messages

### Step 2: Check Google Cloud Console OAuth Consent Screen

1. **Go to:** https://console.cloud.google.com/apis/credentials/consent
2. **Check these settings:**

   **App Information:**
   - App name: `PharmaStockAPP` (or whatever you named it)
   - User support email: Your email
   - App logo: (optional but recommended)

   **App Domain:**
   - Application home page: `http://localhost:8000` (or your domain)
   - Privacy Policy link: **REQUIRED** - Add a URL (can be a placeholder)
   - Terms of Service link: **REQUIRED** - Add a URL (can be a placeholder)
   - Authorized domains: Add `localhost` (for testing)

   **Scopes:**
   - Make sure `https://www.googleapis.com/auth/drive` is added

   **Test Users:**
   - If app is in "Testing" mode, add: `controleddrugsalesdaimamerudda@gmail.com`

### Step 3: Check OAuth Client Configuration

1. **Go to:** https://console.cloud.google.com/apis/credentials
2. **Click on your OAuth 2.0 Client ID**
3. **Verify:**

   **Authorized JavaScript origins:**
   ```
   http://localhost:8000
   ```

   **Authorized redirect URIs:**
   ```
   http://localhost:8000/api/admin/drive/callback
   ```
   ⚠️ **MUST MATCH EXACTLY** - no trailing slash, correct path

### Step 4: Common Issues

#### Issue 1: Missing Privacy Policy / Terms of Service
**Symptom:** Consent screen shows warning about missing Privacy Policy
**Fix:** 
- Go to OAuth Consent Screen
- Add Privacy Policy URL (can be `http://localhost:8000/privacy` as placeholder)
- Add Terms of Service URL (can be `http://localhost:8000/terms` as placeholder)
- Save and wait 1-2 minutes

#### Issue 2: App in Testing Mode
**Symptom:** Getting "access_denied" error
**Fix:**
- Go to OAuth Consent Screen
- Scroll to "Test users"
- Click "+ ADD USERS"
- Add: `controleddrugsalesdaimamerudda@gmail.com`
- Save

#### Issue 3: Redirect URI Mismatch
**Symptom:** Getting "redirect_uri_mismatch" error
**Fix:**
- Check redirect URI in Google Cloud Console
- Must be exactly: `http://localhost:8000/api/admin/drive/callback`
- No trailing slash, correct protocol (http not https for localhost)

#### Issue 4: Callback Not Reaching Server
**Symptom:** Clicking "Continue" does nothing, no server logs
**Fix:**
- Check if server is running on port 8000
- Check firewall/antivirus blocking localhost:8000
- Try accessing `http://localhost:8000/api/admin/drive/callback?code=test` manually
- Check browser console (F12) for errors

### Step 5: After Clicking "Continue"

1. **Watch server logs** - You should see callback messages
2. **Check browser** - Should redirect to success/error page
3. **If stuck:** Check browser console (F12) for JavaScript errors
4. **If error page:** Read the error message carefully

### Step 6: Verify Token Was Saved

After successful authorization, check:
- File: `web_app/google_token.json` should exist
- File: `web_app/oauth_flow_state.json` should be deleted (cleaned up)

### Debugging Commands

Check if token file exists:
```bash
cd web_app
python -c "import os; print('Token:', os.path.exists('../google_token.json'))"
```

Check flow state:
```bash
cd web_app
python -c "import os; print('Flow state:', os.path.exists('oauth_flow_state.json'))"
```

## Quick Checklist

- [ ] Privacy Policy URL added in OAuth Consent Screen
- [ ] Terms of Service URL added in OAuth Consent Screen
- [ ] Test user email added (if in Testing mode)
- [ ] Redirect URI matches exactly: `http://localhost:8000/api/admin/drive/callback`
- [ ] Server is running and accessible
- [ ] Checked server logs for errors
- [ ] Checked browser console (F12) for errors

## Still Not Working?

1. **Check server terminal** - Look for error messages
2. **Check browser console** (F12) - Look for network errors
3. **Try in incognito/private window** - Rule out browser extensions
4. **Check if callback URL is accessible** - Try visiting it directly
5. **Verify credentials file exists** - `web_app/google_credentials.json`

