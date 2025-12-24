# 🔧 Get Supabase Pooler Connection String

## ❌ Current Error

```
FATAL: Tenant or user not found
```

This means the connection string username format is incorrect. The auto-conversion code can't guess the correct format - you need the **actual pooler connection string** from Supabase.

## ✅ Solution: Get Pooler Connection String from Supabase Dashboard

### Step-by-Step Instructions:

1. **Go to Supabase Dashboard**
   - https://supabase.com/dashboard
   - Select your project

2. **Navigate to Database Settings**
   - Click **"Settings"** (gear icon) in left sidebar
   - Click **"Database"** in settings menu

3. **Find Connection Pooling Section**
   - Scroll down to **"Connection pooling"** section
   - You'll see different connection modes

4. **Select Connection Mode**
   - **"Session mode"** - Recommended for most apps
   - **"Transaction mode"** - Alternative option
   - Click on one of them

5. **Copy the Connection String**
   - You'll see a connection string that looks like:
     ```
     postgresql://postgres.REF:PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres
     ```
   - **Copy this EXACT string** (don't modify it)

6. **URL-Encode Special Characters in Password**
   - If your password has special characters, URL-encode them:
     - `?` → `%3F`
     - `!` → `%21`
     - `$` → `%24`
   - Replace the password part in the connection string

7. **Update DATABASE_URL in Render**
   - Go to Render Dashboard → Your Service → Environment
   - Edit `DATABASE_URL`
   - Paste the pooler connection string (with URL-encoded password)
   - Save

## 📋 Example

If Supabase shows:
```
postgresql://postgres.oagcmmkmypmwmeuodkym:PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

And your password is: `b?!HABE69$TwwSV`

Then URL-encode the password: `b%3F%21HABE69%24TwwSV`

Final connection string:
```
postgresql://postgres.oagcmmkmypmwmeuodkym:b%3F%21HABE69%24TwwSV@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

## ⚠️ Important Notes

- **DO NOT** use the direct connection string (`db.xxx.supabase.co`) - it only has IPv6
- **DO** use the pooler connection string (`pooler.supabase.com`) - it supports IPv4
- **DO** copy the username format exactly as shown in Supabase dashboard
- **DO** URL-encode special characters in the password

## ✅ After Updating

1. Render will auto-restart
2. Check logs - should see:
   - ✅ `✅ PostgreSQL connection pool created`
   - ✅ `✅ PostgreSQL database initialized`
   - ✅ No more "Tenant or user not found" errors

---

**Action Required**: Get the pooler connection string from Supabase Dashboard and update `DATABASE_URL` in Render

