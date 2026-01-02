# 🔧 Fix Supabase Pooler Connection (Free Tier)

## ⚠️ CRITICAL: Free Tier Requires Pooler Connection

Supabase **free tier does NOT support direct connections**. You **MUST** use the **pooler connection string**.

## ❌ Current Problem

The error `could not translate host name "aws-1-eu-west-1.pooler.supabase.com"` suggests:
- The connection string might be using wrong region
- Or the connection string format is incorrect
- **Solution**: Get the EXACT pooler connection string from Supabase Dashboard

---

## ✅ Solution: Get Pooler Connection String from Supabase

### Step 1: Get Connection String from Supabase Dashboard

1. **Go to**: https://supabase.com/dashboard
2. **Select your project**
3. **Click**: Settings (gear icon) → **Database**
4. **Scroll down** to **"Connection pooling"** section
5. **Click**: **"Session mode"** (recommended) or **"Transaction mode"**
6. **Copy the connection string** shown

**It will look like:**
```
postgresql://postgres.oagcmmkmypmwmeuodkym:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

**Important Notes:**
- ✅ Username format: `postgres.REF` (NOT just `postgres`)
- ✅ Hostname: `pooler.supabase.com` (NOT `db.xxx.supabase.co`)
- ✅ Port: `6543` (NOT `5432`)
- ✅ Region: Check your Supabase project region (might be `us-east-1`, `eu-west-1`, etc.)

### Step 2: URL-Encode Password

If your password has special characters, you MUST URL-encode them:

| Character | URL Encoded |
|-----------|-------------|
| `?` | `%3F` |
| `!` | `%21` |
| `$` | `%24` |
| `@` | `%40` |
| `#` | `%23` |
| `%` | `%25` |

**Example:**
- Password: `b?!HABE69$TwwSV`
- URL-encoded: `b%3F%21HABE69%24TwwSV`

### Step 3: Build Final Connection String

Replace `[YOUR-PASSWORD]` in the connection string with your URL-encoded password.

**Example:**
```
postgresql://postgres.oagcmmkmypmwmeuodkym:b%3F%21HABE69%24TwwSV@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

### Step 4: Update DATABASE_URL in Render

1. **Go to**: https://dashboard.render.com
2. **Click** your service
3. **Go to**: **Environment** tab
4. **Find**: `DATABASE_URL`
5. **Click** to edit
6. **Paste** the pooler connection string (with URL-encoded password)
7. **Click**: **Save Changes**
8. **Wait** for Render to restart (automatic)

### Step 5: Verify Connection

After restart, check Render logs for:
- ✅ `✅ PostgreSQL connection pool created`
- ✅ `✅ Using Supabase PostgreSQL database`
- ✅ No DNS resolution errors
- ✅ No "Tenant or user not found" errors

---

## 🔍 Common Issues

### Issue 1: "Tenant or user not found"

**Cause**: Username format is wrong

**Fix**: 
- ❌ Wrong: `postgres` 
- ✅ Correct: `postgres.oagcmmkmypmwmeuodkym` (username.project_ref)

### Issue 2: "Could not translate host name"

**Cause**: Wrong region or hostname

**Fix**: 
- Get the EXACT connection string from Supabase Dashboard
- Don't guess the region - use what Supabase shows you

### Issue 3: "Network is unreachable" or IPv6 errors

**Cause**: Using direct connection instead of pooler

**Fix**: 
- ❌ Wrong: `db.oagcmmkmypmwmeuodkym.supabase.co`
- ✅ Correct: `pooler.supabase.com` or `aws-0-[REGION].pooler.supabase.com`

### Issue 4: Wrong Port

**Cause**: Using port 5432 (direct) instead of 6543 (pooler)

**Fix**: 
- ❌ Wrong: Port `5432`
- ✅ Correct: Port `6543`

---

## 📋 Connection String Format

### ✅ CORRECT Pooler Connection String Format:

```
postgresql://postgres.[PROJECT_REF]:[URL_ENCODED_PASSWORD]@[POOLER_HOSTNAME]:6543/postgres
```

**Components:**
- `postgres.[PROJECT_REF]` - Username with project reference
- `[URL_ENCODED_PASSWORD]` - Password with special characters encoded
- `[POOLER_HOSTNAME]` - Either:
  - `aws-0-[REGION].pooler.supabase.com` (region-specific)
  - `[PROJECT_REF].pooler.supabase.com` (project-specific)
- `6543` - Pooler port (NOT 5432)
- `postgres` - Database name

### ❌ WRONG Direct Connection String (Don't Use):

```
postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
```

**Why it's wrong:**
- Uses `postgres` (not `postgres.REF`)
- Uses `db.xxx.supabase.co` (not `pooler.supabase.com`)
- Uses port `5432` (not `6543`)
- Only supports IPv6 (free tier doesn't support IPv6)

---

## 🎯 Quick Checklist

- [ ] Got connection string from Supabase Dashboard → Settings → Database → Connection pooling
- [ ] Selected "Session mode" or "Transaction mode"
- [ ] Copied the EXACT connection string (don't modify it)
- [ ] URL-encoded password special characters
- [ ] Updated DATABASE_URL in Render with pooler connection string
- [ ] Verified connection string uses:
  - ✅ `postgres.[PROJECT_REF]` as username
  - ✅ `pooler.supabase.com` in hostname
  - ✅ Port `6543`
- [ ] Render restarted successfully
- [ ] Logs show successful connection

---

## 📝 Example: Complete Process

1. **Supabase shows:**
   ```
   postgresql://postgres.oagcmmkmypmwmeuodkym:PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres
   ```

2. **Your password:** `b?!HABE69$TwwSV`

3. **URL-encode password:** `b%3F%21HABE69%24TwwSV`

4. **Final connection string:**
   ```
   postgresql://postgres.oagcmmkmypmwmeuodkym:b%3F%21HABE69%24TwwSV@aws-0-us-east-1.pooler.supabase.com:6543/postgres
   ```

5. **Paste into Render** → Environment → DATABASE_URL

6. **Save** → Wait for restart → Verify logs

---

**Status**: ⚠️ **ACTION REQUIRED** - Get pooler connection string from Supabase Dashboard and update DATABASE_URL in Render

