# Fix Google OAuth Redirect URI Mismatch Error

## Error
`Error 400: redirect_uri_mismatch`

This error occurs when the redirect URI in your Google Cloud Console doesn't match what the application is sending.

## Solution

### Step 1: Go to Google Cloud Console
1. Visit: https://console.cloud.google.com/
2. Select your project (or create one if needed)

### Step 2: Navigate to OAuth Consent Screen
1. Go to **APIs & Services** → **OAuth consent screen**
2. Make sure your app is configured

### Step 3: Add Authorized Redirect URI
1. Go to **APIs & Services** → **Credentials**
2. Find your OAuth 2.0 Client ID (the one you're using for this app)
3. Click **Edit** (pencil icon)
4. Scroll down to **Authorized redirect URIs**
5. Click **+ ADD URI**
6. Add exactly this URI:
   ```
   http://localhost:8000/api/admin/drive/callback
   ```
7. Click **SAVE**

### Step 4: Verify
- Make sure there are no trailing spaces
- Make sure it's exactly: `http://localhost:8000/api/admin/drive/callback`
- The protocol must be `http://` (not `https://`) for localhost
- The port must be `8000` (or change it in `web_app/app/config.py` if you use a different port)

### Step 5: Test Again
1. Go back to your admin page
2. Click "Get Authorization URL"
3. Complete the authorization flow

## Important Notes

- **For Production**: When deploying to a production server, you'll need to add the production redirect URI as well (e.g., `https://yourdomain.com/api/admin/drive/callback`)
- **Multiple URIs**: You can add multiple redirect URIs - one for localhost and one for production
- **Wait Time**: Changes may take a few minutes to propagate

## Current Configuration

The application is configured to use:
- **Redirect URI**: `http://localhost:8000/api/admin/drive/callback`
- **Config File**: `web_app/app/config.py` (line 16)

If you need to change the port or domain, update `GOOGLE_OAUTH_CALLBACK_URL` in `web_app/app/config.py`.

