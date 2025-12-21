# Google OAuth2 Configuration - Step by Step

## Current Issue
You're seeing: **"Invalid Origin: URIs must not contain a path or end with '/'."**

This is because **Authorized JavaScript origins** must be domain-only (no paths).

## Correct Configuration

### Step 1: Authorized JavaScript origins
**Remove the path!** Use only:

```
http://localhost:8000
```

**NOT:**
- ❌ `http://localhost:8000/auth/callback` (has path - WRONG)
- ❌ `http://localhost:8000/` (ends with / - WRONG)

**YES:**
- ✅ `http://localhost:8000` (domain only - CORRECT)

### Step 2: Authorized redirect URIs
Add these redirect URIs (one at a time):

**Primary (for manual code entry):**
```
urn:ietf:wg:oauth:2.0:oob
```

**Optional (for local testing with callback):**
```
http://localhost:8000/auth/callback
```

## Complete Setup Instructions

### In Google Cloud Console:

1. **Authorized JavaScript origins:**
   - Click in the field
   - Enter: `http://localhost:8000`
   - Click **+ Add URI**
   - ✅ No error should appear

2. **Authorized redirect URIs:**
   - Click **+ Add URI** button
   - Enter: `urn:ietf:wg:oauth:2.0:oob`
   - Click **+ Add URI** again
   - Enter: `http://localhost:8000/auth/callback` (optional)
   - Click **SAVE**

### After Saving:

1. **Download credentials:**
   - Click **DOWNLOAD JSON** button
   - Save file as `google_credentials.json`
   - Place it in `web_app/` directory

2. **Run the app:**
   ```bash
   cd web_app
   python run.py
   ```

3. **Authorize (first time only):**
   - App will show authorization URL
   - Visit URL in browser
   - Sign in with `controleddrugsalesdaimamerudda@gmail.com`
   - Copy authorization code
   - Paste code when app prompts
   - Token saved automatically

## Summary

**Authorized JavaScript origins:**
```
http://localhost:8000
```

**Authorized redirect URIs:**
```
urn:ietf:wg:oauth:2.0:oob
http://localhost:8000/auth/callback
```

After saving, download the JSON file and save as `google_credentials.json` in the `web_app/` folder.

