# 📋 Render Configuration Summary

## Environment Variables to Set

Copy these exactly into Render Dashboard → Environment tab:

### 1. DATABASE_URL (REQUIRED - Most Important!)
```
DATABASE_URL=postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres
```

### 2. PYTHON_VERSION
```
PYTHON_VERSION=3.11.0
```

### 3. PORT
```
PORT=8000
```

---

## Service Configuration

### Build Command
```
pip install -r requirements.txt
```

### Start Command
```
uvicorn app.main:app --host 0.0.0.0 --port $PORT --timeout-keep-alive 300
```

### Root Directory
- Leave empty (if `web_app` is the root)
- Or set to: `web_app` (if code is in subfolder)

---

## What to Check After Deployment

### ✅ Success Indicators in Logs:
- `✅ Using Supabase PostgreSQL database`
- `✅ Database manager initialized`
- `🚀 Starting PharmaStock Web Application`
- `Application startup complete`

### ❌ Error Indicators:
- `Using SQLite database` → `DATABASE_URL` not set
- `Failed to connect` → Wrong connection string
- `Module not found` → Missing dependencies

---

## Quick Steps

1. **Push code to GitHub** (using GitHub Desktop or VS Code)
2. **Go to Render Dashboard** → Your Service
3. **Environment tab** → Add `DATABASE_URL`
4. **Save Changes**
5. **Deploy** (Manual Deploy → Deploy latest commit)
6. **Check Logs** for Supabase connection
7. **Test App** at your Render URL

---

## Your Render Services

Based on your history, you have:
- `web_app` service
- `pharma-stock-app` service

**Choose one to update**, or create a new one called `pharmastock-web`.

---

**Ready to configure?** Follow the steps in `PUSH_AND_DEPLOY.md`!

