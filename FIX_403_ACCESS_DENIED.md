# Fix Error 403: access_denied

## The Problem
You're getting "Error 403: access_denied" because:
- ✅ Redirect URI is now correct
- ❌ Your app is in "Testing" mode
- ❌ Your email is not added to the test users list

## The Solution

### Option 1: Add Your Email as Test User (Recommended for Development)

1. **Go to Google Cloud Console:**
   - Visit: https://console.cloud.google.com/
   - Select your project: **PharmastockApp**

2. **Navigate to OAuth Consent Screen:**
   - Go to **APIs & Services** → **OAuth consent screen**
   - You should see "Publishing status: Testing"

3. **Add Test Users:**
   - Scroll down to **"Test users"** section
   - Click **"+ ADD USERS"**
   - Add your email: `controleddrugsalesdaimamerudda@gmail.com`
   - Click **"ADD"**

4. **Save and Test:**
   - The changes take effect immediately
   - Go back to your admin page
   - Click "Get Authorization URL" again
   - It should work now!

### Option 2: Publish the App (For Production)

If you want anyone to be able to use the app:

1. **Go to OAuth Consent Screen:**
   - APIs & Services → OAuth consent screen

2. **Click "PUBLISH APP"**
   - This makes the app available to all users
   - Note: Google may require verification for sensitive scopes

3. **Warning:** Publishing requires:
   - App verification (if using sensitive scopes)
   - Privacy policy URL
   - Terms of service URL

## Quick Fix Steps (Do This Now)

1. Open: https://console.cloud.google.com/apis/credentials/consent
2. Scroll to "Test users" section
3. Click "+ ADD USERS"
4. Enter: `controleddrugsalesdaimamerudda@gmail.com`
5. Click "ADD"
6. Go back to your app and try authorization again

## Why This Happened

When an OAuth app is in "Testing" mode, only users added to the "Test users" list can authorize it. This is a security feature to prevent unauthorized access during development.

## Current Status

- ✅ Redirect URI: Correct (`http://localhost:8000/api/admin/drive/callback`)
- ✅ Client ID: Correct (`497673348686-evbo069r6n7m4en8q5hos0d5muf4j1ik.apps.googleusercontent.com`)
- ❌ Test User: Need to add your email

After adding your email as a test user, the authorization should work!

