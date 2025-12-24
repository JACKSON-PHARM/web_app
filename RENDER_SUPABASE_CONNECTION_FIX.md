# 🔧 Fix: Supabase Connection from Render

## ❌ Current Error

```
connection to server at "db.oagcmmkmypmwmeuodkym.supabase.co" (IPv6 address), port 5432 failed: Network is unreachable
```

## 🔍 Problem

Render is trying to connect via IPv6 on port 5432 (direct connection), but Supabase requires **connection pooling** for external connections from platforms like Render.

## ✅ Solution: Use Connection Pooling Port

You need to change the port from `5432` to `6543` (Supabase's connection pooling port).

### Your Current Connection String:
```
postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres
```

### ✅ Correct Connection String (Use Port 6543):
```
postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:6543/postgres
```

**OR** use the pooler connection string from Supabase:

### Better Option: Use Supabase Pooler Connection String

1. Go to Supabase Dashboard → Your Project
2. Settings → Database
3. Scroll to "Connection pooling"
4. Select "Session mode" or "Transaction mode"
5. Copy the connection string (it will have port 6543 or use `pooler.supabase.com`)

The pooler connection string looks like:
```
postgresql://postgres.xxxxx:[PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

## 📋 Steps to Fix

1. **Go to Render Dashboard** → Your Service → Environment

2. **Find `DATABASE_URL`** and click to edit

3. **Change the port from 5432 to 6543**:
   - Old: `...supabase.co:5432/postgres`
   - New: `...supabase.co:6543/postgres`

4. **OR replace with pooler connection string** from Supabase Dashboard

5. **Save Changes** - Render will restart automatically

6. **Check Logs** - Should see:
   - ✅ `✅ PostgreSQL connection pool created`
   - ✅ `✅ PostgreSQL database initialized`

## 🔍 Why This Happens

- Port **5432** = Direct PostgreSQL connection (often blocked for external connections)
- Port **6543** = Connection pooling (required for external connections from Render, Heroku, etc.)

Supabase uses PgBouncer on port 6543 to handle connection pooling, which is required for serverless/cloud platforms.

## ✅ Expected Result

After changing to port 6543:
- ✅ Connection will succeed
- ✅ No more "Network is unreachable" errors
- ✅ Dashboard will load data from Supabase

---

**Action Required**: Update `DATABASE_URL` in Render to use port `6543` instead of `5432`

