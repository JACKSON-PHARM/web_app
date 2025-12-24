# DATABASE_URL Setup Guide

## Your Supabase Connection String

```
postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres
```

**Note:** The password is URL-encoded:
- `?` → `%3F`
- `!` → `%21`
- `$` → `%24`

---

## Option 1: Local Development (Windows PowerShell)

### Temporary (Current Session Only)
```powershell
$env:DATABASE_URL = "postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres"
```

### Permanent (User Environment Variable)
1. Open PowerShell as Administrator
2. Run:
```powershell
[System.Environment]::SetEnvironmentVariable('DATABASE_URL', 'postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres', 'User')
```

3. Restart PowerShell/VS Code for changes to take effect

### Using .env File (Recommended for Development)
1. Create `.env` file in `web_app` folder:
```powershell
cd C:\PharmaStockApp\web_app
New-Item -Path .env -ItemType File
```

2. Add this line to `.env`:
```
DATABASE_URL=postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres
```

3. The app will automatically load it (pydantic-settings reads .env files)

---

## Option 2: Render Deployment

### Steps:
1. Go to [Render Dashboard](https://dashboard.render.com)
2. Select your service (`web_app`)
3. Click **"Environment"** tab (left sidebar)
4. Click **"Add Environment Variable"**
5. Enter:
   - **Key**: `DATABASE_URL`
   - **Value**: `postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres`
6. Click **"Save Changes"**
7. Render will automatically redeploy

### Alternative: Using render.yaml
Add to `web_app/render.yaml`:
```yaml
services:
  - type: web
    name: web_app
    envVars:
      - key: DATABASE_URL
        value: postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres
```

---

## Verify Setup

### Check if DATABASE_URL is Set
```powershell
# PowerShell
echo $env:DATABASE_URL

# Or test in Python
python -c "import os; print('DATABASE_URL:', os.getenv('DATABASE_URL'))"
```

### Test Connection
```powershell
cd C:\PharmaStockApp\web_app
python scripts/test_connection.py "postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres"
```

### Start App and Check Logs
```powershell
cd C:\PharmaStockApp\web_app
python -m uvicorn app.main:app --reload
```

Look for:
- ✅ `"Using Supabase PostgreSQL database"` - Success!
- ⚠️ `"Using SQLite database"` - DATABASE_URL not set

---

## Troubleshooting

### Issue: "DATABASE_URL: None"
**Solution:** Environment variable not set. Use one of the methods above.

### Issue: "Failed to connect to Supabase"
**Possible causes:**
1. **Wrong password encoding** - Make sure special characters are URL-encoded
2. **Network/firewall** - Check if you can reach Supabase
3. **Supabase paused** - Free tier pauses after inactivity

**Fix:** 
- Verify connection string in Supabase dashboard
- Check Supabase project status
- Try connection test script

### Issue: "Falling back to SQLite"
**Solution:** DATABASE_URL is not being read. Check:
1. Environment variable is set correctly
2. Restarted terminal/IDE after setting
3. `.env` file exists and has correct format

---

## Quick Start (Local)

```powershell
# 1. Navigate to web_app
cd C:\PharmaStockApp\web_app

# 2. Set DATABASE_URL (temporary)
$env:DATABASE_URL = "postgresql://postgres:b%3F%21HABE69%24TwwSV@db.oagcmmkmypmwmeuodkym.supabase.co:5432/postgres"

# 3. Test connection
python scripts/test_connection.py $env:DATABASE_URL

# 4. Start app
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Security Note

⚠️ **Never commit `.env` file or connection strings to Git!**

The `.env` file should be in `.gitignore`:
```
.env
*.env
```

Your connection string contains your database password - keep it secure!

