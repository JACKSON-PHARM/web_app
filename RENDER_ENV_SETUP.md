# 🔧 Render Environment Variables Setup

## ⚠️ CRITICAL: Missing DATABASE_URL on Render

The error logs show:
```
ValueError: DATABASE_URL environment variable is required.
```

## ✅ Quick Fix Steps

### 1. Get Your Supabase Connection String

**Option A: Direct Connection (for development)**
1. Go to Supabase Dashboard → Your Project
2. Settings → Database
3. Scroll to "Connection string" → "URI"
4. Copy the connection string (looks like):
   ```
   postgresql://postgres.xxxxx:[PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
   ```

**Option B: Connection Pooling (recommended for production)**
1. Same location as above
2. Use the "Connection pooling" → "Session mode" connection string
3. This is better for production apps

### 2. Add to Render

1. **Go to Render Dashboard**
   - https://dashboard.render.com
   - Click on your service (web-app-c2ws)

2. **Navigate to Environment Tab**
   - Click "Environment" in the left sidebar
   - Or go to: Settings → Environment

3. **Add Environment Variable**
   - Click "Add Environment Variable"
   - **Key**: `DATABASE_URL`
   - **Value**: Paste your Supabase connection string
   - Click "Save Changes"

4. **Wait for Restart**
   - Render will automatically restart your service
   - Watch the logs to confirm it starts successfully

### 3. Verify It Works

After restart, check:
- ✅ Render logs show no `DATABASE_URL` errors
- ✅ Dashboard loads branches
- ✅ Sync status works
- ✅ Priority items load

## 📋 Required Environment Variables

Make sure these are set on Render:

| Variable | Description | Where to Get It |
|----------|-------------|-----------------|
| `DATABASE_URL` | **REQUIRED** - Supabase PostgreSQL connection string | Supabase Dashboard → Settings → Database |
| `SECRET_KEY` | JWT token secret (any random string) | Generate: `openssl rand -hex 32` |
| `ALGORITHM` | JWT algorithm (optional, defaults to HS256) | Usually `HS256` |

## 🔍 How to Check Current Environment Variables

1. Go to Render Dashboard → Your Service
2. Click "Environment" tab
3. You'll see all current environment variables
4. Make sure `DATABASE_URL` is listed

## ⚠️ Common Issues

### Issue: "DATABASE_URL not found"
**Solution**: Add it in Render Environment tab

### Issue: "Connection refused" or "timeout"
**Solution**: 
- Check Supabase project is active
- Verify connection string is correct
- Try connection pooling string instead

### Issue: "Authentication failed"
**Solution**:
- Check password in connection string is correct
- Regenerate password in Supabase if needed

## 🎯 After Setting DATABASE_URL

Once `DATABASE_URL` is set:
1. Render will auto-restart
2. Check logs - should see: `✅ Using Supabase PostgreSQL database`
3. Dashboard should work!

---

**Status**: ⚠️ Waiting for DATABASE_URL to be set on Render
**Action**: Add DATABASE_URL environment variable in Render dashboard

