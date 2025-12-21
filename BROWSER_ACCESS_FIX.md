# Browser Access Fix

## The Problem

You're trying to access `http://0.0.0.0:8000/` in your browser, but this **won't work**.

The error `ERR_ADDRESS_INVALID` means the browser can't connect to `0.0.0.0` because it's not a valid address for browsers.

## The Solution

**Use `localhost` instead of `0.0.0.0`:**

### ✅ Correct Browser Address:
```
http://localhost:8000
```

OR

```
http://127.0.0.1:8000
```

### ❌ Wrong Browser Address:
```
http://0.0.0.0:8000  ← This won't work!
```

## Why?

- **`0.0.0.0`** is a special address that means "listen on all network interfaces" - it's used by the **server** to bind to all available network interfaces
- **`localhost`** or **`127.0.0.1`** is the address your **browser** uses to connect to services running on your own computer

## Quick Steps:

1. **Make sure your server is running:**
   ```bash
   cd web_app
   python run.py
   ```

2. **Look for this message:**
   ```
   INFO:     Uvicorn running on http://0.0.0.0:8000
   ```
   (This is normal - the server binds to 0.0.0.0, but you access it via localhost)

3. **Open your browser and go to:**
   ```
   http://localhost:8000
   ```

4. **You should see the login page!**

## Still Not Working?

### Check if server is running:
```bash
# Windows PowerShell
netstat -ano | findstr :8000
```

You should see:
```
TCP    0.0.0.0:8000           0.0.0.0:0              LISTENING
```

### Test if server responds:
```bash
# PowerShell
Invoke-WebRequest -Uri http://localhost:8000 -UseBasicParsing
```

### Check firewall:
- Windows Firewall might be blocking port 8000
- Temporarily disable to test

### Try different browser:
- Chrome
- Firefox
- Edge
- Or try incognito/private mode

## Summary

**Server binds to:** `0.0.0.0:8000` ✅ (This is correct for the server)
**Browser connects to:** `localhost:8000` ✅ (This is what you type in browser)

