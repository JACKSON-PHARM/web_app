# How to Start the Server

## Quick Start

1. **Open a terminal/command prompt**

2. **Navigate to web_app directory:**
   ```bash
   cd web_app
   ```

3. **Start the server:**
   ```bash
   python run.py
   ```

   OR:
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

4. **Wait for startup messages:**
   ```
   🚀 Starting PharmaStock Web Application
   ✅ Database manager initialized
   INFO:     Uvicorn running on http://0.0.0.0:8000
   ```

5. **Open your browser:**
   ```
   http://localhost:8000
   ```
   
   ⚠️ **IMPORTANT:** Do NOT use `http://0.0.0.0:8000` - that won't work in browsers!
   - ✅ Use: `http://localhost:8000` or `http://127.0.0.1:8000`
   - ❌ Don't use: `http://0.0.0.0:8000` (this is only for server binding, not browser access)

## If Server Won't Start

### Check for Port Conflicts
```bash
# Windows PowerShell
netstat -ano | findstr :8000
```

If port 8000 is in use, kill the process or change port in `app/config.py`.

### Check for Python Errors
Look for error messages in the terminal. Common issues:
- Missing dependencies: `pip install -r requirements.txt`
- Import errors: Check Python path
- Database errors: Check database file permissions

### Check Dependencies
```bash
cd web_app
pip install -r requirements.txt
```

## Troubleshooting

### "Address already in use"
- Port 8000 is already in use
- Solution: Kill the process using port 8000 or change port

### "Module not found"
- Missing Python dependencies
- Solution: `pip install -r requirements.txt`

### "Database error"
- Database file permissions issue
- Solution: Check `web_app/cache/` directory permissions

### Browser shows "This site can't be reached"
- Server isn't running
- Solution: Start the server first (see Quick Start)

### Browser shows blank page
- Check browser console (F12) for errors
- Check server terminal for error messages
- Verify static files are loading

