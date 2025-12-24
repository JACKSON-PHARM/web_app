# 🔐 Render DATABASE_URL Setup

## Your Complete Connection String

Your Supabase connection details:
- **Host**: `db.oagcmmkmypmwmeuodkym.supabase.co`
- **Port**: `5432`
- **Database**: `postgres`
- **User**: `postgres`
- **Password**: `b?!HABE69$TwwSV` (contains special characters)

## ⚠️ Important: URL Encoding Required

Your password contains special characters (`?`, `!`, `$`) that must be URL-encoded in the connection string:

| Character | URL Encoded |
|-----------|-------------|
| `?` | `%3F` |
| `!` | `%21` |
| `$` | `%24` |

## ✅ Complete Connection String

**IMPORTANT**: Use port **6543** (connection pooling) instead of 5432 for Render!

Use this EXACT string in Render (password is URL-encoded, port 6543):

```
postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:6543/postgres
```

**Why port 6543?**
- Port 5432 = Direct connection (often blocked from Render)
- Port 6543 = Connection pooling (required for Render/external connections)

## 📋 Steps to Add to Render

1. **Go to Render Dashboard**
   - https://dashboard.render.com
   - Click on your service

2. **Go to Environment Tab**
   - Click "Environment" in left sidebar
   - Or: Settings → Environment

3. **Add Environment Variable**
   - Click "Add Environment Variable"
   - **Key**: `DATABASE_URL`
   - **Value**: Paste this exact string:
     ```
     postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres
     ```
   - Click "Save Changes"

4. **Wait for Restart**
   - Render will automatically restart
   - Check logs - should see: `✅ Using Supabase PostgreSQL database`

## ✅ Verification

After adding, check Render logs for:
- ✅ `✅ PostgreSQL connection pool created`
- ✅ `✅ PostgreSQL database initialized`
- ✅ `✅ Using Supabase PostgreSQL database`
- ✅ No more `DATABASE_URL environment variable is required` errors

## 🔒 Security Note

- Never commit this connection string to GitHub
- Keep it only in Render environment variables
- Consider rotating password periodically

---

**Copy this exact string to Render:**
```
postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres
```

