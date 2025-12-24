# 🚨 URGENT: Update DATABASE_URL in Render

## ❌ Current Problem

Your `DATABASE_URL` in Render is still using the **direct connection string**:
```
db.oagcmmkmypmwmeuodkym.supabase.co
```

This **ONLY supports IPv6**, but Supabase free tier **doesn't support IPv6**!

## ✅ Solution: Update DATABASE_URL NOW

### Step 1: Get Pooler Connection String from Supabase

1. **Go to**: https://supabase.com/dashboard
2. **Select your project**
3. **Click**: Settings (gear icon) → Database
4. **Scroll down** to "Connection pooling" section
5. **Click**: "Session mode" (or "Transaction mode")
6. **Copy** the connection string shown

It will look like:
```
postgresql://postgres.oagcmmkmypmwmeuodkym:PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

### Step 2: URL-Encode Password

If your password has special characters, encode them:
- `?` → `%3F`
- `!` → `%21`
- `$` → `%24`

Example: `b?!HABE69$TwwSV` → `b%3F%21HABE69%24TwwSV`

### Step 3: Update in Render

1. **Go to**: https://dashboard.render.com
2. **Click** your service
3. **Click**: Environment (left sidebar)
4. **Find**: `DATABASE_URL`
5. **Click** to edit
6. **Replace** with the pooler connection string (with URL-encoded password)
7. **Save**

### Step 4: Wait for Restart

- Render will automatically restart
- Check logs - should see: `✅ PostgreSQL connection pool created`

## 🔍 How to Verify

**Current (WRONG)** - Has this:
```
db.oagcmmkmypmwmeuodkym.supabase.co
```

**Correct (RIGHT)** - Should have this:
```
pooler.supabase.com
```
OR
```
aws-0-us-east-1.pooler.supabase.com
```

## ⚠️ Important

- **DO NOT** use connection string with `db.xxx.supabase.co` ❌
- **DO** use connection string with `pooler.supabase.com` ✅
- The pooler connection string is **different** from the direct connection string

---

**ACTION REQUIRED**: Update `DATABASE_URL` in Render with pooler connection string from Supabase Dashboard

