# Verify Redirect URI Configuration

## Current Configuration

**In your code (`web_app/app/config.py`):**
```python
GOOGLE_OAUTH_CALLBACK_URL: str = "http://localhost:8000/api/admin/drive/callback"
```

**In Google Cloud Console (from your screenshot):**
```
http://localhost:8000/api/admin/drive/callback
```

✅ **These match exactly!**

## How to Verify What URL is Actually Being Sent

1. **Check Server Logs** - When you click "Get Authorization URL", look for:
   ```
   🔵 Using redirect URI: http://localhost:8000/api/admin/drive/callback
   🔵 Flow redirect_uri: http://localhost:8000/api/admin/drive/callback
   🔵 Full authorization URL: https://accounts.google.com/o/oauth2/v2/auth?...
   ```

2. **Inspect the Authorization URL** - Copy the authorization URL and check the `redirect_uri` parameter:
   - The URL will look like: `https://accounts.google.com/o/oauth2/v2/auth?redirect_uri=...&...`
   - Decode the `redirect_uri` parameter (it's URL-encoded)
   - It should be: `http://localhost:8000/api/admin/drive/callback`

3. **Common Issues:**

   **Issue 1: Trailing Slash**
   - ❌ Wrong: `http://localhost:8000/api/admin/drive/callback/`
   - ✅ Correct: `http://localhost:8000/api/admin/drive/callback`

   **Issue 2: HTTPS vs HTTP**
   - ❌ Wrong: `https://localhost:8000/api/admin/drive/callback`
   - ✅ Correct: `http://localhost:8000/api/admin/drive/callback` (for localhost)

   **Issue 3: Port Mismatch**
   - ❌ Wrong: `http://localhost:8080/api/admin/drive/callback`
   - ✅ Correct: `http://localhost:8000/api/admin/drive/callback`

   **Issue 4: Path Mismatch**
   - ❌ Wrong: `http://localhost:8000/api/drive/callback`
   - ✅ Correct: `http://localhost:8000/api/admin/drive/callback`

## Debugging Steps

1. **Get the authorization URL** from the admin page
2. **Copy the full URL** from the server logs or the response
3. **Paste it in a text editor** and look for `redirect_uri=`
4. **Decode the URL** (it's URL-encoded) - you can use an online URL decoder
5. **Compare** the decoded `redirect_uri` with what's in Google Cloud Console

## Quick Test

Run this in your terminal to see what redirect URI is configured:
```bash
cd web_app
python -c "from app.config import settings; print('Callback URL:', settings.GOOGLE_OAUTH_CALLBACK_URL)"
```

Expected output:
```
Callback URL: http://localhost:8000/api/admin/drive/callback
```

## If URLs Don't Match

If the redirect URI in the authorization URL doesn't match Google Cloud Console:

1. **Check `web_app/app/config.py`** - Make sure `GOOGLE_OAUTH_CALLBACK_URL` is correct
2. **Restart the server** - Configuration changes require a restart
3. **Check for environment variables** - If you have a `.env` file, it might override the config
4. **Check the credentials JSON file** - Some OAuth libraries read redirect URIs from the credentials file

## Next Steps

After verifying the redirect URI matches:
1. Make sure Privacy Policy and Terms of Service URLs are added in OAuth Consent Screen
2. Make sure your email is added as a test user (if app is in Testing mode)
3. Try the authorization flow again
4. Watch server logs for detailed error messages

