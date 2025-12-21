# Check Server Status - Troubleshooting Guide

## Your OAuth Authorization Succeeded! ✅

The fact that "PharmaStockAPP" appears in your Google Account means the OAuth flow completed successfully. The token file exists at:
```
C:\PharmaStockApp\web_app\google_token.json
```

## If the App Won't Render After Restart

### Step 1: Check if Server is Running

Open a terminal and run:
```bash
cd web_app
python run.py
```

Or:
```bash
cd web_app
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Look for:**
- `🚀 Starting PharmaStock Web Application`
- `✅ Database manager initialized`
- `INFO:     Uvicorn running on http://0.0.0.0:8000`

### Step 2: Check for Startup Errors

Watch the terminal output for:
- ❌ Error messages
- ⚠️ Warning messages
- 🔴 Red text indicating failures

**Common startup errors:**
- Database connection issues
- Google Drive authentication errors
- Missing dependencies
- Port 8000 already in use

### Step 3: Verify Browser Connection

1. **Make sure server is running** (see Step 1)
2. **Open browser** and go to: `http://localhost:8000`
3. **Check browser console** (F12 → Console tab) for errors
4. **Check Network tab** (F12 → Network) to see if requests are failing

### Step 4: Check Port Conflicts

If port 8000 is already in use:
```bash
# Windows PowerShell
netstat -ano | findstr :8000
```

If something is using port 8000, either:
- Stop that process
- Change port in `web_app/app/config.py`:
  ```python
  PORT: int = 8001  # Change to different port
  ```

### Step 5: Check Token File Permissions

The token file should be readable. Try:
```bash
cd web_app
python -c "import json; f = open('google_token.json'); data = json.load(f); print('Token loaded successfully'); f.close()"
```

### Step 6: Check Logs for Specific Errors

Look for these in your terminal:
- `❌ Error completing authorization`
- `⚠️ Google Drive not authenticated`
- `❌ Database manager initialization failed`
- `ERROR: Application startup failed`

## Quick Fixes

### Fix 1: Clear Browser Cache
- Press `Ctrl + Shift + Delete`
- Clear cached images and files
- Try accessing `http://localhost:8000` again

### Fix 2: Try Incognito/Private Window
- Open browser in incognito/private mode
- Go to `http://localhost:8000`
- This rules out browser extensions interfering

### Fix 3: Check Firewall/Antivirus
- Windows Firewall might be blocking port 8000
- Antivirus might be blocking the connection
- Temporarily disable to test

### Fix 4: Verify Server is Actually Running
```bash
# In a new terminal, test if server responds
curl http://localhost:8000
# Or use PowerShell:
Invoke-WebRequest -Uri http://localhost:8000
```

## What to Share for Help

If still stuck, share:
1. **Full terminal output** from starting the server
2. **Browser console errors** (F12 → Console)
3. **Network tab errors** (F12 → Network)
4. **Any error messages** you see

